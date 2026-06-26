#!/usr/bin/env python3
"""
QwenPaw 对话搜索脚本
用法：
  python search.py <关键词>         搜索对话
  python search.py --stats          查看数据库概览
  python search.py --log            查看导入日志

环境变量：
  CHATDB_DIR       chatdb 目录路径（默认 ~/.qwenpaw/chatdb）
  QWENPAW_HOME     QwenPaw 主目录（默认 ~/.qwenpaw）
"""
import sqlite3
import sys
import json
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

QWENPAW_HOME = os.environ.get("QWENPAW_HOME", os.path.expanduser("~/.qwenpaw"))
CHATDB_DIR = os.environ.get("CHATDB_DIR", os.path.join(QWENPAW_HOME, "chatdb"))
DB_PATH = os.path.join(CHATDB_DIR, "chat.db")
LOG_PATH = os.path.join(CHATDB_DIR, "import.log")

def search(query, limit=10, workspace=None, agent=None, channel=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 构建查询
    conditions = ["m.content_text MATCH ?"]
    params = [query]
    
    if workspace:
        conditions.append("c.workspace_id = ?")
        params.append(workspace)
    if agent:
        conditions.append("c.agent_id = ?")
        params.append(agent)
    if channel:
        conditions.append("c.channel_id = ?")
        params.append(channel)
    
    where = " AND ".join(conditions)
    
    # 先查 FTS 拿到 rowid 列表
    fts_rows = conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?",
        (query,)
    ).fetchall()
    
    if not fts_rows:
        conn.close()
        return []
    
    rowids = [r[0] for r in fts_rows]
    
    sql = """
        SELECT m.id, m.role, m.name, m.content_text, m.timestamp,
               c.title as conv_title, c.workspace_id, c.agent_id, c.channel_id
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE m.rowid IN ({})
    """
    placeholders = ','.join(['?'] * len(rowids))
    sql = sql.format(placeholders)
    
    filter_clauses = []
    params = rowids[:]
    
    if workspace:
        filter_clauses.append("c.workspace_id = ?")
        params.append(workspace)
    if agent:
        filter_clauses.append("c.agent_id = ?")
        params.append(agent)
    if channel:
        filter_clauses.append("c.channel_id = ?")
        params.append(channel)
    
    if filter_clauses:
        sql += " AND " + " AND ".join(filter_clauses)
    
    sql += " ORDER BY m.timestamp DESC LIMIT ?"
    params.append(limit)
    
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def show_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    print("📊 数据库概览")
    print("━" * 40)
    
    ws = conn.execute("SELECT id, name FROM workspaces").fetchall()
    for w in ws:
        count = conn.execute("SELECT COUNT(*) as n FROM conversations WHERE workspace_id=?", (w['id'],)).fetchone()
        print(f"  工作区 [{w['id']}]: {count['n']} 个会话")
    
    ag = conn.execute("SELECT id, name FROM agents").fetchall()
    for a in ag:
        count = conn.execute("SELECT COUNT(*) as n FROM conversations WHERE agent_id=?", (a['id'],)).fetchone()
        print(f"  Agent [{a['name']}]: {count['n']} 个会话")
    
    ch = conn.execute("SELECT id, name FROM channels").fetchall()
    for c in ch:
        count = conn.execute("SELECT COUNT(*) as n FROM conversations WHERE channel_id=?", (c['id'],)).fetchone()
        print(f"  通道 [{c['name']}]: {count['n']} 个会话")
    
    total_msg = conn.execute("SELECT COUNT(*) as n FROM messages").fetchone()
    total_conv = conn.execute("SELECT COUNT(*) as n FROM conversations").fetchone()
    print(f"\n  总计: {total_conv['n']} 个会话, {total_msg['n']} 条消息")
    conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] == '--stats':
        show_stats()
        sys.exit(0)
    
    if sys.argv[1] == '--log':
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, encoding='utf-8') as f:
                lines = f.readlines()
            # 显示最近 20 条
            for line in lines[-20:]:
                print(line.rstrip())
            print(f"\n共 {len(lines)} 条记录")
        else:
            print("日志文件不存在")
        sys.exit(0)
    
    query = sys.argv[1]
    rows = search(query, limit=8)
    
    if not rows:
        print(f"❌ 没找到包含「{query}」的内容")
        sys.exit(0)
    
    print(f"🔍 搜索「{query}」- 找到 {len(rows)} 条结果\n")
    
    for r in rows:
        print(f"━━ {r['timestamp'][:19]} ━━ {r['channel_id']} ━━ {r['conv_title']}")
        print(f"  [{r['role']}] {r['name']}")
        # 截取关键词附近
        txt = r['content_text']
        idx = txt.lower().find(query.lower())
        if idx > 0:
            start = max(0, idx - 40)
            end = min(len(txt), idx + len(query) + 40)
            snippet = txt[start:end]
            if start > 0: snippet = '...' + snippet
            if end < len(txt): snippet += '...'
        else:
            snippet = txt[:120]
        print(f"  {snippet}")
        print()
