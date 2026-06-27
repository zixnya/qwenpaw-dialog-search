# 🐾 QwenPaw 历史对话全文搜索 Skill

Created by 一懒众衫小 — 随便用，记得留个名就行

将 QwenPaw 所有工作区的历史对话自动导入 **SQLite + FTS5** 全文索引，实现秒级检索。**零依赖、跨平台**，Linux / macOS / Windows 均可运行。

## 一分钟上手

```bash
# 1. 下载
git clone https://github.com/zixnya/qwenpaw-dialog-search.git
cd qwenpaw-dialog-search

# 2. 全量导入（读取 QwenPaw 所有历史对话）
python3 import.py

# 3. 搜索试试
python3 search.py "树莓派"
python3 search.py "GitHub 令牌"
python3 search.py --stats     # 看概览
python3 search.py --log       # 看导入日志
```

## 架构

```
QwenPaw → dialog/*.jsonl（不改不动）
    ↓
import.py（定时/手动扫描）
    ↓
chat.db（SQLite + FTS5） ← search.py（只读查询）
```

- **完全独立**：不修改 QwenPaw 任何文件
- **增量同步**：只读新增行，每次 <0.05 秒
- **全文检索**：FTS5 实时索引，中文搜索秒出

## 配置

通过环境变量配置路径，无需修改代码：

```bash
export QWENPAW_HOME="/path/to/.qwenpaw"    # QwenPaw 安装目录（默认 ~/.qwenpaw）
export CHATDB_DIR="/path/to/chatdb"         # 数据目录（默认 $QWENPAW_HOME/chatdb）
```

## 定时自动同步

| 平台 | 方式 |
|:----|:-----|
| Linux | `crontab -e` → `*/5 * * * * python3 /path/to/import.py` |
| macOS | launchd plist（详见 SKILL.md） |
| Windows | 任务计划程序（详见 SKILL.md） |

## 触发词

在 QwenPaw 中直接说 **「历史对话 + 关键词」** 即可搜索历史记录：

> 历史对话 树莓派
> 历史对话，查GitHub令牌
> 历史对话 备份铁律

## 技术栈

| 组件 | 说明 |
|:----|:------|
| 数据库 | SQLite + FTS5 全文索引 |
| 语言 | Python 3 标准库（零第三方依赖） |
| 系统 | Linux / macOS / Windows |
| 数据量 | 实测 1 万+ 消息，2.48 秒全量导入 |

## 文件说明

| 文件 | 作用 |
|:----|:------|
| `SKILL.md` | QwenPaw Skill 完整文档（含设计原理、表结构、边缘处理） |
| `import.py` | 全量/增量导入脚本 |
| `search.py` | 搜索脚本（支持 --stats / --log / 关键词） |

## License

MIT
