#!/usr/bin/env python3
"""
QwenPaw 对话全量/增量导入脚本
扫描所有 workspace/*/dialog/*.jsonl → 写入 SQLite + FTS5
"""

import sqlite3
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# === 配置（支持环境变量覆盖） ===
# 优先级：命令行参数 > 环境变量 > 默认值
QWENPAW_HOME = os.environ.get("QWENPAW_HOME", os.path.join(os.path.expanduser("~"), ".qwenpaw"))
CHATDB_DIR = os.environ.get("CHATDB_DIR", os.path.join(QWENPAW_HOME, "chatdb"))

WORKSPACES_DIR = os.environ.get("QWENPAW_WORKSPACES",
                                os.path.join(QWENPAW_HOME, "workspaces"))
DB_PATH = os.path.join(CHATDB_DIR, "chat.db")
STATE_PATH = os.path.join(CHATDB_DIR, "import_state.json")
LOG_PATH = os.path.join(CHATDB_DIR, "import.log")
GAP_THRESHOLD = 1800  # 30分钟

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT
);
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, workspace_id TEXT NOT NULL REFERENCES workspaces(id)
);
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    agent_id TEXT REFERENCES agents(id), channel_id TEXT REFERENCES channels(id),
    title TEXT, start_time TEXT NOT NULL, end_time TEXT,
    msg_count INTEGER DEFAULT 0, source_file TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL, name TEXT, content_text TEXT,
    content_raw TEXT, timestamp TEXT NOT NULL, metadata TEXT,
    PRIMARY KEY (id, conversation_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content_text, role, name, conversation_id UNINDEXED
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_time ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_conv_time ON conversations(start_time);
CREATE INDEX IF NOT EXISTS idx_conv_workspace ON conversations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_conv_agent ON conversations(agent_id);
CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel_id);
"""


def extract_text(content_list):
    if not content_list or not isinstance(content_list, list):
        return ""
    texts = []
    for item in content_list:
        if not isinstance(item, dict):
            continue
        t = item.get('type', '')
        if t == 'text':
            texts.append(item.get('text', ''))
        elif t == 'thinking':
            texts.append(f"[思考] {item.get('text', '')}")
        elif t == 'tool_call':
            inp = item.get('input', {})
            inp_str = json.dumps(inp, ensure_ascii=False)[:200] if isinstance(inp, (dict,list)) else str(inp)[:200]
            texts.append(f"[工具: {item.get('name','?')}] {inp_str}")
        elif t == 'tool_result':
            out = item.get('output', '')
            out_str = str(out)[:500] if out else ''
            texts.append(f"[工具结果] {out_str}")
    return '\n'.join(texts)


def get_agent_name_from_json(ws_path):
    agent_json = os.path.join(ws_path, "agent.json")
    if os.path.exists(agent_json):
        try:
            with open(agent_json, encoding='utf-8') as f:
                data = json.load(f)
            return data.get('name', 'Default Agent')
        except:
            pass
    return "Default Agent"


def import_all():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # 历史数据导入关外键检查
    conn.executescript(SCHEMA)

    state = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            state = json.load(f)

    # 默认通道
    conn.execute("INSERT OR IGNORE INTO channels (id, name, type) VALUES (?, ?, ?)",
                 ("unknown", "unknown", "unknown"))
    conn.execute("INSERT OR IGNORE INTO channels (id, name, type) VALUES (?, ?, ?)",
                 ("wechat", "wechat", "im"))
    conn.execute("INSERT OR IGNORE INTO channels (id, name, type) VALUES (?, ?, ?)",
                 ("dingtalk", "dingtalk", "im"))


    total_new_msgs = 0
    total_new_convs = 0
    conv_seq = [0]  # 用 list 做可变的计数器

    for ws_name in sorted(os.listdir(WORKSPACES_DIR)):
        ws_path = os.path.join(WORKSPACES_DIR, ws_name)
        dialog_dir = os.path.join(ws_path, "dialog")
        if not os.path.isdir(ws_path) or not os.path.isdir(dialog_dir):
            continue

        # 工作区
        conn.execute("INSERT OR IGNORE INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
                     (ws_name, ws_name, datetime.now().isoformat()))

        # Agent
        agent_name = get_agent_name_from_json(ws_path)
        agent_id = ws_name
        conn.execute("INSERT OR IGNORE INTO agents (id, name, workspace_id) VALUES (?, ?, ?)",
                     (agent_id, agent_name, ws_name))

        dialog_files = sorted([f for f in os.listdir(dialog_dir) if f.endswith('.jsonl')])

        for filename in dialog_files:
            filepath = os.path.join(dialog_dir, filename)
            file_key = f"{ws_name}/{filename}"
            entry = state.get(file_key, {})
            last_pos = entry.get("pos", 0)
            last_mtime = entry.get("mtime", 0)

            cur_mtime = os.path.getmtime(filepath)
            if cur_mtime <= last_mtime and last_pos > 0:
                continue

            # 读新行
            new_lines = []
            with open(filepath, 'r', encoding='utf-8') as f:
                if last_pos > 0:
                    f.seek(last_pos)
                for line in f:
                    line = line.strip()
                    if line:
                        new_lines.append(line)
                new_pos = f.tell()

            if not new_lines:
                state[file_key] = {"pos": last_pos if last_pos > 0 else 0, "mtime": cur_mtime}
                continue

            # 解析
            msgs = []
            for line in new_lines:
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if not msgs:
                state[file_key] = {"pos": new_pos, "mtime": cur_mtime}
                continue

            msgs.sort(key=lambda m: m.get('timestamp', ''))

            # 按时间间隔切分会话
            conv_start = 0
            for i in range(1, len(msgs) + 1):
                is_new = False
                if i == len(msgs):
                    is_new = True
                else:
                    try:
                        t_prev = datetime.fromisoformat(msgs[i-1].get('timestamp', ''))
                        t_cur = datetime.fromisoformat(msgs[i].get('timestamp', ''))
                        gap = (t_cur - t_prev).total_seconds()
                        if gap > GAP_THRESHOLD:
                            is_new = True
                    except:
                        pass

                if is_new:
                    batch = msgs[conv_start:i]
                    if batch:
                        ok = save_conversation(conn, ws_name, agent_id,
                                               "unknown", filename, batch, conv_seq)
                        if ok:
                            total_new_convs += 1
                            total_new_msgs += len(batch)
                    conv_start = i

            state[file_key] = {"pos": new_pos, "mtime": cur_mtime}

    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

    conn.commit()
    conn.close()
    return total_new_msgs, total_new_convs


def save_conversation(conn, workspace_id, agent_id, channel_id, source_file, msgs, seq_counter):
    if not msgs:
        return False

    start_time = msgs[0].get('timestamp', '')
    end_time = msgs[-1].get('timestamp', '')

    seq_counter[0] += 1
    ts_part = start_time[:19].replace(' ', '_').replace(':', '').replace('-', '')
    conv_id = f"conv_{ts_part}_{seq_counter[0]}"

    # 标题
    title = ""
    for m in msgs:
        if m.get('role') == 'user':
            c = m.get('content', [])
            if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get('type') == 'text':
                title = c[0].get('text', '')[:80]
                break
    if not title:
        title = f"会话 {start_time[:16]}"

    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, workspace_id, agent_id, channel_id, title, start_time, end_time, msg_count, source_file) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conv_id, workspace_id, agent_id, channel_id, title,
         start_time, end_time, len(msgs), source_file)
    )

    for msg in msgs:
        msg_id = msg.get('id', '')
        if not msg_id:
            continue
        role = msg.get('role', '')
        name = msg.get('name', '')
        content_list = msg.get('content', [])
        content_text = extract_text(content_list)
        content_raw = json.dumps(content_list, ensure_ascii=False)
        timestamp = msg.get('timestamp', '')
        metadata = json.dumps(msg.get('metadata', {}), ensure_ascii=False)

        try:
            conn.execute(
                "INSERT OR IGNORE INTO messages "
                "(id, conversation_id, role, name, content_text, content_raw, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (msg_id, conv_id, role, name, content_text, content_raw, timestamp, metadata)
            )
            # FTS5
            if content_text.strip():
                row = conn.execute("SELECT rowid FROM messages WHERE id=? AND conversation_id=?",
                                  (msg_id, conv_id)).fetchone()
                if row:
                    conn.execute(
                        "INSERT OR IGNORE INTO messages_fts "
                        "(rowid, content_text, role, name, conversation_id) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (row[0], content_text, role, name, conv_id)
                    )
        except Exception as e:
            print(f"  跳过消息 {msg_id}: {e}")
            continue

    return True


if __name__ == '__main__':
    start = time.time()
    err = None
    try:
        msg_count, conv_count = import_all()
    except Exception as e:
        msg_count, conv_count = 0, 0
        err = traceback.format_exc()
        print(err, file=sys.stderr)
    
    elapsed = time.time() - start
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 写日志
    log_dir = os.path.dirname(LOG_PATH)
    os.makedirs(log_dir, exist_ok=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        if err:
            f.write(f"[{ts}] ❌ FAIL | msg={msg_count} conv={conv_count} | {elapsed:.2f}s\n")
            f.write(f"  {err}\n")
        else:
            f.write(f"[{ts}] ✅ OK | msg={msg_count} conv={conv_count} | {elapsed:.2f}s\n")
    
    print(f"OK: Import done: {msg_count} msgs, {conv_count} convs")
    print(f"    Elapsed: {elapsed:.2f}s")
    if err:
        sys.exit(1)
