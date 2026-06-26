# -*- coding: utf-8 -*-
import os, sys, sqlite3

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

QWENPAW_HOME = os.environ.get('QWENPAW_HOME', os.path.join(os.path.expanduser('~'), '.qwenpaw'))
CHATDB_DIR = os.environ.get('CHATDB_DIR', os.path.join(QWENPAW_HOME, 'chatdb'))
DB_PATH = os.path.join(CHATDB_DIR, 'chat.db')

print('QWENPAW_HOME:', QWENPAW_HOME)
print('CHATDB_DIR:', CHATDB_DIR)
print('DB_PATH:', DB_PATH)
print('ChatDB exists:', os.path.isdir(CHATDB_DIR))

try:
    conn = sqlite3.connect(DB_PATH)
    conn.execute('create table if not exists test (id int)')
    conn.execute('insert into test values (1)')
    print('SQLite OK:', conn.execute('select * from test').fetchall())
    conn.close()
    os.remove(DB_PATH)
except Exception as e:
    print('ERROR:', e)
