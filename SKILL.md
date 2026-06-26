---
description: Use this skill when 用户输入"历史对话"指令。从 SQLite + FTS5 数据库中搜索 QwenPaw 历史对话记录，返回匹配结果。支持多工作区、多 Agent、多通道对话检索。零依赖，纯 Python 标准库实现。
name: 对话搜索-v1
---

# 对话搜索 — QwenPaw 历史对话全文检索

将 QwenPaw 所有工作区的历史对话自动导入 SQLite + FTS5 全文索引，支持快速检索历史对话。完全独立于 QwenPaw 服务运行，零额外依赖。

---

## 触发条件

用户输入「历史对话」时触发。格式：

```
历史对话 <搜索词>
历史对话 <搜索词>，筛选条件
```

### 示例

| 用户输入 | 行为 |
|:---------|:-----|
| "历史对话 树莓派" | 全文搜索含"树莓派"的消息 |
| "历史对话 GitHub 令牌" | 全文搜索含"GitHub 令牌"的消息 |
| "历史对话，查SFA" | 搜索含"SFA"的消息（逗号自动忽略） |

### 反向过滤

- 用户说「上网搜」「查一下」「Google」时 → 不走历史搜索，走浏览器
- 用户说「翻记录」「找找以前」而不是「历史对话」→ 按需判断，但优先响应「历史对话」

---

## 架构概览

```
QwenPaw 服务  →  写 dialog/*.jsonl（不改不动）
    ↓
import.py（定时/手动）  →  扫描所有 workspace 增量导入
    ↓
chat.db（SQLite + FTS5）  ←  只读查询
    ↓
search.py  ←  我调，返回结果
```

### 原则

- **完全独立**：不与 QwenPaw 服务耦合
- **零依赖**：只使用 Python 标准库（sqlite3、json、os、sys、time、datetime）
- **跨平台**：Linux / macOS / Windows 均可运行
- **只读不写**：搜索不修改数据库，导入只追加不删除

---

## 安装配置

### 文件清单

| 文件 | 说明 |
|:----|:------|
| `chatdb/chat.db` | SQLite 数据库（自动生成） |
| `chatdb/import.py` | 增量导入脚本 |
| `chatdb/search.py` | 搜索脚本 |
| `chatdb/import_state.json` | 文件位置跟踪（自动维护） |
| `chatdb/import.log` | 执行日志（自动追加） |

### 第一步：确定 QwenPaw 工作区路径

在不同操作系统上，QwenPaw 的默认配置目录不同：

| 系统 | 默认路径 |
|:----|:---------|
| Linux | `/root/.qwenpaw/workspaces/` |
| macOS | `/Users/<用户名>/.qwenpaw/workspaces/` |
| Windows | `C:\Users\<用户名>\.qwenpaw\workspaces\` |

如果 QwenPaw 安装路径不是默认路径，先找到 `workspaces/` 目录的位置。

### 第二步：放置脚本

将 `chatdb/` 目录放到任意位置，建议放在 QwenPaw 配置目录下：

```bash
# Linux/macOS 示例
cp -r chatdb/ ~/.qwenpaw/chatdb/

# Windows 示例（PowerShell）
Copy-Item -Recurse chatdb\ $env:USERPROFILE\.qwenpaw\chatdb\
```

### 第三步：配置

配置通过**环境变量**完成，无需修改代码：

```bash
# Linux/macOS - 在 shell 配置文件中加入
export QWENPAW_HOME="/root/.qwenpaw"           # QwenPaw 主目录
export QWENPAW_WORKSPACES="/root/.qwenpaw/workspaces"  # 工作区目录（覆盖默认）
export CHATDB_DIR="/root/.qwenpaw/chatdb"       # chatdb 数据目录

# Windows (PowerShell)
$env:QWENPAW_HOME = "$env:USERPROFILE\.qwenpaw"
$env:QWENPAW_WORKSPACES = "$env:USERPROFILE\.qwenpaw\workspaces"
$env:CHATDB_DIR = "$env:USERPROFILE\.qwenpaw\chatdb"
```

**如果不设环境变量**，脚本会自动按默认路径查找：
- Linux: `/root/.qwenpaw/`
- macOS/Windows: `~/.qwenpaw/`（当前用户的 home 目录）

**设置完验证**：
```bash
python3 import.py  # 看有没有报错
```

### 第四步：全量导入

```bash
# Linux/macOS
python3 /path/to/chatdb/import.py

# Windows
python C:\path\to\chatdb\import.py
```

首次导入会读取所有历史对话文件，创建 SQLite 数据库和 FTS5 全文索引。

### 第五步：配置定时任务（可选）

增量导入支持三种方式：

#### Linux — crontab

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每 5 分钟执行一次）
*/5 * * * * /usr/bin/python3 /path/to/chatdb/import.py
```

#### macOS — launchd

创建 plist 文件 `~/Library/LaunchAgents/com.qwenpaw.chatdb.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.qwenpaw.chatdb</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/chatdb/import.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/chatdb_import.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/chatdb_import.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.qwenpaw.chatdb.plist
```

#### Windows — 任务计划程序

```powershell
# PowerShell（管理员）
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\chatdb\import.py"
$trigger = New-ScheduledTaskTrigger -Once -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "QwenPaw ChatDB Import" -Action $action -Trigger $trigger -RunLevel Highest
```

### 第六步：验证

```bash
# 查看数据库概览
python3 /path/to/chatdb/search.py --stats

# 查看导入日志
python3 /path/to/chatdb/search.py --log

# 测试搜索
python3 /path/to/chatdb/search.py "测试"
```

---

## 标准化指令工作流

当用户说「历史对话」时：

### 第一步：解析搜索词

从用户输入中提取搜索关键词：

```
"历史对话 树莓派"       → 关键词：树莓派
"历史对话，查树莓派"     → 关键词：查树莓派（逗号自动忽略）
"历史对话 备份铁律"      → 关键词：备份铁律
```

### 第二步：执行搜索

```bash
python3 /path/to/chatdb/search.py "<关键词>"
```

注意：Linux/macOS 用 `python3`，Windows 用 `python` 或 `py`。

### 第三步：返回结果

按以下格式输出：

```
🔍 历史对话「树莓派」— 找到 N 条结果

━━ 时间 ━━ 通道 ━━ 会话标题
  [角色] 发送者
  匹配内容片段...
```

### 第四步：无结果时

```
❌ 历史对话中没找到「xxx」相关记录
```

---

## 搜索脚本用法

```bash
# 搜索历史对话
python3 search.py <关键词>

# 查看数据库概览
python3 search.py --stats

# 查看导入日志（最近 20 条）
python3 search.py --log
```

### 输出格式示例

```
🔍 搜索「树莓派」- 找到 8 条结果

━━ 2026-06-13 09:05:16 ━━ unknown ━━ 今天的定时任务没触发吗
  [assistant] Default Agent
  服务端需要常开设备上运行（树莓派、NAS、Docker 容器等）。

━━ 2026-06-12 23:37:53 ━━ unknown ━━ 树莓派装IIAB推荐什么规模
  [system] system
  [工具结果] 问: 树莓派装IIAB推荐什么规模...
```

---

## 数据库表结构

### workspaces — 工作区
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| id | TEXT PK | 工作区 ID（如 `default`） |
| name | TEXT | 名称 |
| created_at | TEXT | 创建时间 |

### agents — Agent
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| id | TEXT PK | Agent ID |
| name | TEXT | 名称 |
| workspace_id | TEXT FK | 归属工作区 |

### channels — 通道
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| id | TEXT PK | 通道 ID |
| name | TEXT | 名称 |
| type | TEXT | 类型（`im`、`api`） |

### conversations — 会话
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| id | TEXT PK | 会话 ID |
| workspace_id | TEXT FK | 工作区 |
| agent_id | TEXT FK | Agent |
| channel_id | TEXT FK | 通道 |
| title | TEXT | 标题 |
| start_time | TEXT | 开始时间 |
| end_time | TEXT | 结束时间 |
| msg_count | INTEGER | 消息数 |
| source_file | TEXT | 来源文件 |

### messages — 消息
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| id | TEXT | 消息 ID |
| conversation_id | TEXT FK | 归属会话 |
| role | TEXT | user/assistant/system |
| name | TEXT | 发送者 |
| content_text | TEXT | 纯文本（FTS5 索引） |
| content_raw | TEXT | 原始 JSON |
| timestamp | TEXT | 时间戳 |
| metadata | TEXT | 元数据 |
| PK | | (id, conversation_id) |

### messages_fts（虚拟表）
FTS5 全文索引，索引 `content_text`、`role`、`name` 字段。

---

## 核心逻辑说明

### 会话分组

原始 dialog/*.jsonl 是平铺消息流，按时间间隔自动切分会话。

**规则**：连续消息间隔 > 30 分钟 → 新会话

### 增量导入

`import_state.json` 记录每个文件的读取位置。每次运行：
1. 检查文件 mtime → 未变则跳过
2. 从上次位置读取新行
3. 解析 → 分组 → 入库
4. 更新位置

### 内容提取

| content type | 提取结果 |
|:-------------|:---------|
| text | 直接取文本 |
| thinking | `[思考]xxx` |
| tool_call | `[工具: 名称]输入` |
| tool_result | `[工具结果]输出` |

---

## 质量红线

- 搜索结果必须包含原文片段，不改写、不概括
- 只返回匹配「历史对话」触发词的结果，不擅自检索其他数据
- 导入脚本不修改 QwenPaw 原始对话文件（只读不写）
- 发现无结果时如实告知，不编造
- 多关键词搜索用空格分隔，不用模糊匹配

---

## 边缘预案

| 场景 | 处理方式 |
|:----|:---------|
| 数据库不存在 | 提示「还没导入过，先跑一次 import.py」 |
| 搜索无结果 | 如实告知，不编造 |
| 导入脚本报错 | 查看 import.log 定位原因，常见：路径不对、权限不足 |
| 对话文件超大 | 正常处理，Python 内存足够 |
| 中文搜索不准确 | FTS5 默认分词将中文按单字索引，精确短语搜索效果好于单个字 |
| 多工作区 | 自动扫描，每个工作区独立建表记录 |
| 跨平台路径 | import.py 使用 pathlib.Path 或 os.path.join 处理路径分隔符 |

---

## Windows 兼容说明（v2 新增）

> v1 在 Linux/macOS 上开发验证，v2 补充 Windows 全平台兼容。
> 以下三条是 Windows 上跑必须注意的差异，原 Linux/macOS 流程不变。

### ① 首次运行前的环境检查

```powershell
# Windows（PowerShell / cmd）
python --version                  # 确保已安装 Python 3.8+
pip list 2>nul | findstr sqlite3  # SQLite 已内置，无需安装
```

### ② 路径自动检测（无需设环境变量）

v2 默认路径从 Linux 硬编码 `/root/.qwenpaw` 改为跨平台 `~/.qwenpaw`（通过 `os.path.expanduser("~")` 获取），Windows 下会自动解析为 `C:\Users\<用户名>\.qwenpaw`。三种方式任选：

```powershell
# 方式一：不设任何变量，直接跑（自动检测）
python import.py

# 方式二：设环境变量（覆盖默认）
set QWENPAW_HOME=C:\Users\Administrator\.qwenpaw
set QWENPAW_WORKSPACES=C:\Users\Administrator\.qwenpaw\workspaces
set CHATDB_DIR=C:\Users\Administrator\.qwenpaw\chatdb
python import.py

# 方式三：注册为定期任务（每5分钟增量导入）
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\Users\Administrator\.qwenpaw\chatdb\import.py"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "QwenPaw ChatDB Import" -Action $action -Trigger $trigger -RunLevel Highest -Force
```

### ③ 编码注意事项

Windows 下 cmd/PowerShell 默认使用 GBK 编码，对话文件为 UTF-8，有以下注意事项：

- 如果控制台出现乱码，先运行 `chcp 65001` 切换到 UTF-8 代码页
- 搜索脚本输出中的 emoji（🔍📊✅❌）在旧版 Windows 终端可能显示为方框，不影响功能
- 所有文件读写操作均已指定 `encoding='utf-8'`，与 Linux/macOS 一致

### ④ 脚本差异汇总

与原版 v1 相比，v2 仅修改了以下内容（不影响 Linux/macOS）：

| 文件 | 修改内容 | 原因 |
|:----|:---------|:-----|
| `import.py` | `QWENPAW_HOME` 默认值改为 `os.path.expanduser("~")` | Linux 硬编码路径在 Windows 无效 |
| `import.py` | 所有 `open()` 加上 `encoding='utf-8'` | Windows 默认 GBK 导致 UTF-8 文件读取崩溃 |
| `import.py` | 底部 `print()` 去掉 emoji，日志文件保留 emoji | Windows 控制台 GBK 无法输出 emoji |
| `search.py` | 顶部添加 `sys.stdout.reconfigure(encoding='utf-8')` | 同上 |
| `search.py` | `open(LOG_PATH)` 加上 `encoding='utf-8'` | 同上 |

> 以上修改全部可追溯，无功能删减，无逻辑重构。

