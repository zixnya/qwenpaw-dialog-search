# -*- coding: utf-8 -*-
"""提取sgfas相关对话"""
import json, sys, os, glob
sys.stdout.reconfigure(encoding='utf-8')

# 7CMyfm 工作区下的所有对话
dialog_dir = r'C:\Users\Administrator\.qwenpaw\workspaces\7CMyfm\dialog'
keywords = ['sgfas', '施工方案', '方案系统', '一日一案']

for fpath in sorted(glob.glob(os.path.join(dialog_dir, '*.jsonl'))):
    date = os.path.basename(fpath)[:10]
    with open(fpath, encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    
    # 先扫描有哪些消息跟sgfas相关
    session_msgs = {}
    for line in lines:
        try:
            d = json.loads(line)
        except:
            continue
        content = d.get('content', '')
        if isinstance(content, list):
            content = ' '.join(c.get('text','') for c in content if isinstance(c, dict))
        text = str(content)[:500]
        for kw in keywords:
            if kw in text.lower() or kw in text:
                sid = d.get('session_id', d.get('sessionId', '?'))
                if sid not in session_msgs:
                    session_msgs[sid] = []
                session_msgs[sid].append({
                    'role': d.get('role','?'),
                    'content': text[:300],
                    'ts': d.get('timestamp','?')
                })
                break
    
    if session_msgs:
        print(f'\n{"="*60}')
        print(f'📅 {date} — 找到 {len(session_msgs)} 个相关会话')
        print('='*60)
        for sid, msgs in session_msgs.items():
            print(f'\n--- 会话 {sid[:20]}... ({len(msgs)} 条相关消息) ---')
            for m in msgs[:8]:  # 最多8条
                role_mark = '👤' if m['role'] == 'user' else '🤖'
                print(f'  {role_mark} [{m["role"]}] {m["content"][:200]}')
            if len(msgs) > 8:
                print(f'  ... 还有 {len(msgs)-8} 条')
