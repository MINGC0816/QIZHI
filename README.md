# 企业员工知识问答智能体（V1）

基于**本地文档**（PDF / Word / Markdown）的 RAG + LangChain Agent，对接内网 vLLM（Qwen）。第一版全员同一知识库，**不做权限隔离**。

## 架构

```
上传 → data/raw
重建索引 → 解析分块 → Embedding(CPU) → Chroma
员工提问 → Agent（search_knowledge / list_documents）→ 内网 LLM → 带来源回答
```

## 快速开始

1. 连上 VPN，确认内网模型可用：

```bash
curl http://10.60.40.130:12333/v1/models
```

2. 安装依赖（建议在仓库根目录 `.venv`）：

```bash
cd agent_study
.\.venv\Scripts\pip install -e .\enterprise_kb_agent   # Windows
# 或
.venv/bin/pip install -e ./enterprise_kb_agent         # Linux/macOS
```

3. 配置环境变量：

```bash
cd enterprise_kb_agent
cp .env.example .env
# 按需修改 VLLM_* 与 EMBEDDING_MODEL_PATH
```

4. 一键启动（前后端同一终端，Ctrl+C 同时停止并释放端口）：

```bash
# Windows（PowerShell / CMD 均可）
.\start.bat
# 或直接
.\start.ps1

# Linux / macOS
chmod +x start.sh
./start.sh
```

启动后访问：

| 入口 | 地址 |
|------|------|
| 员工问答 | http://127.0.0.1:3000 |
| 知识库管理 | http://127.0.0.1:3000/admin |
| API 文档 | http://127.0.0.1:8002/docs |

默认端口：API `8002`，Web `3000`（可用环境变量 `API_PORT` / `WEB_PORT` 改 Linux 端）。

## 使用说明

**两个前端页面**

- `/`：员工问答（左侧历史会话，右侧对话）
- `/admin`：知识库管理（上传、重建索引、原文/切片预览）

**文档入库流程**

1. 管理页「上传文档」→ 文件保存到 `data/raw/`（此时**不会**跑 Embedding）
2. 点击「重建索引」→ 解析 / 分块 / Embedding / 写入 Chroma
3. 问答时 Agent 仅做向量检索，不再重新解析整份文档

**可选：命令行批量入库**

```bash
# 将文件放到 data/raw/ 后
python scripts/ingest_folder.py

# 或入库 samples/ 示例制度
python scripts/ingest_folder.py --samples
```

**会话存储**

- 对话内容：LangGraph SqliteSaver（`data/db/kb_agent.db`）
- 会话列表：同库 `chat_threads` 表
- 浏览器仅存当前 `thread_id`（localStorage）

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET/POST/DELETE | `/api/v1/threads...` | 会话 |
| POST | `/api/v1/chat` | 知识问答 |
| GET | `/api/v1/admin/documents` | 文档列表 |
| POST | `/api/v1/admin/upload` | 上传到 raw |
| POST | `/api/v1/admin/ingest` | 重建索引 |
| GET | `/api/v1/admin/documents/{file}/preview` | 原文预览 |
| GET | `/api/v1/admin/documents/{file}/chunks` | 切片预览 |

（另保留无 `/admin` 前缀的兼容路径：`/api/v1/upload`、`/ingest`、`/documents`）

## 目录

```
enterprise_kb_agent/
  start.bat / start.ps1 / start.sh   # 启动（Win 用 bat/ps1，Linux 用 sh）
  .env.example
  pyproject.toml
  README.md
  samples/               # 示例制度 Markdown
  scripts/
    ingest_folder.py     # 命令行批量入库
  data/
    raw/                 # 上传的原始文档
    chroma/              # 向量库
    db/                  # 会话 SQLite
    logs/                # 运行日志 app.log / error.log
  src/
    config.py / llm.py / logging_config.py
    ingest/              # 解析、分块、入库
    rag/                 # Embedding、Chroma、检索
    agent/               # 工具与 Agent
    api/                 # FastAPI
    sessions/            # 会话元数据
  web/                   # Next.js + Ant Design 前端
```

## 日志

运行日志目录：`data/logs/`

| 文件 | 内容 |
|------|------|
| `app.log` | 常规运行日志（请求、上传、入库、问答） |
| `error.log` | 仅 ERROR 及以上 |

单文件约 5MB，最多保留 5 个滚动备份。级别可通过 `.env` 的 `LOG_LEVEL` 调整（默认 `INFO`）。

启动脚本产生的 uvicorn 标准输出仍在 `data/api.*.log`（Windows）或 `data/api.log`（Linux）。

## 注意

- vLLM 需开启 `--enable-auto-tool-choice` 与 `--tool-call-parser`（如 `qwen3_xml`），否则 Agent 工具调用会失败。
- Embedding 默认使用项目内 **`models/bge-small-zh-v1.5`**（CPU 加载）。权重约 90MB，默认不提交 Git；缺失时见 `models/README.md`。
- 离线部署请保证 `models/bge-small-zh-v1.5` 目录完整，或把 `EMBEDDING_MODEL_PATH` 改为其他本地绝对路径。
- V1 **不支持扫描版 PDF**（需可复制文本的 PDF）；扫描件会提示「无可提取文本」。
- 启动后 API 日志在 `data/api.out.log` / `data/api.err.log`（Windows）或 `data/api.log`（Linux）。

更完整的技术栈与架构说明见：[docs/项目技术分析.md](./docs/项目技术分析.md)。
