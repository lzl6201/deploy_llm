# 大模型部署平台

Web 化的大语言模型（LLM）部署与调度平台，统一管理内网多台 NVIDIA GPU 服务器，实现一键部署、显卡性能压榨、自动推荐部署方案与模型量化。

> 项目计划文档见 [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)。

## 当前进度

- [x] Master 控制面后端（FastAPI + SQLAlchemy）
- [x] 可插拔引擎适配层（vLLM / llama.cpp / Ollama）
- [x] GGUF 元数据解析器（自动识别架构/参数量/量化档位/上下文）
- [x] 文件系统浏览器（白名单 + 目录穿越防护）
- [x] 显存感知推荐引擎 v2（权重 + KV cache + 开销估算，量化/引擎/并行度感知）
- [x] GGUF 在线量化（llama-quantize，产物自动注册为新版本）
- [x] Agent 执行面（GPU 采集 + 注册 + 心跳 + 部署/量化指令轮询，绕过系统代理）
- [x] Web 前端（Vue3：节点总览 / 模型仓库 / 智能推荐 / 一键部署 / 部署管理 / 模型量化）
- [x] 反向推荐（按节点显卡列出可部署模型）
- [x] HuggingFace 模型发现 + 下载（走 hf-mirror 国内镜像，进度条 + 完成后自动注册）
- [ ] 多卡 TP / 多机负载均衡（P1）
- [ ] 预量化导入 + Docker 编排（P2）

## 目录结构

```
deploy_llm/
├── docs/PROJECT_PLAN.md      # 项目计划文档
├── master/                   # 控制面后端（FastAPI）
│   └── app/
│       ├── main.py           # 入口
│       ├── config.py         # 配置（env 驱动）
│       ├── db/               # 数据库会话
│       ├── models/           # SQLAlchemy ORM
│       ├── schemas/          # Pydantic 模型
│       ├── api/              # 路由层
│       └── services/         # 业务层（节点管理/推荐/引擎适配）
├── agent/                    # 执行面（每台 GPU 服务器部署）
├── frontend/                 # Web 前端（Vue3 + Element Plus）
└── docker-compose.yml
```

## 快速开始

### 1. 启动控制面 Master

```bash
cd master
pip install -r requirements.txt
export AGENT_AUTH_TOKEN=change-me-agent-token                 # 与 Agent 保持一致
export ALLOWED_FS_ROOTS=/mnt/models                          # 文件浏览器白名单根目录
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

默认使用 SQLite（`deploy_llm.db`），生产可设 `DATABASE_URL` 切到 MySQL/PostgreSQL。

### 2. 启动 Agent（在每台 GPU 服务器上）

```bash
cd agent
pip install -r requirements.txt
export MASTER_URL=http://<master-ip>:8000
export AGENT_AUTH_TOKEN=change-me-agent-token
export LLAMA_CPP_BIN_DIR=/path/to/llama.cpp/build/bin        # 本机 llama-server / llama-quantize
python main.py
```

Agent 启动后会自动注册并每 5s 上报 GPU 状态（与 Master 直连，绕过系统代理）。

### 3. 导入 GGUF 模型并一键部署

```bash
# 导入 GGUF：自动解析架构 / 参数量 / 量化档位 / 上下文
curl -X POST http://localhost:8000/api/models/import \
  -H 'Content-Type: application/json' \
  -d '{"path":"/mnt/models/Qwen3.8-27B-UD-Q3_K_XL.gguf","version":"v1"}'

# 智能推荐（按模型版本 + 目标节点，服务端解析 GGUF 元数据）
curl -X POST http://localhost:8000/api/recommend/plan \
  -H 'Content-Type: application/json' \
  -d '{"model_version_id":1,"server_id":1}'

# 创建部署（llama.cpp 引擎，Agent 拉取后启动 llama-server）
curl -X POST http://localhost:8000/api/deployments \
  -H 'Content-Type: application/json' \
  -d '{"name":"qwen-demo","model_version_id":1,"server_id":1,"engine":"llama.cpp","gpu_ids":[0],"tp_size":1,"port":8001,"max_model_len":8192}'

# 在线量化（llama-quantize，完成后自动注册为新版本）
curl -X POST http://localhost:8000/api/quantize \
  -H 'Content-Type: application/json' \
  -d '{"model_version_id":1,"target_quant":"Q4_K_M","server_id":1}'
```

### 4. 启动 Web 前端

```bash
cd frontend
npm install        # 已通过项目 .npmrc 指向 npmmirror 并绕过失效代理
npm run dev        # http://localhost:5173 ，/api 自动代理到后端 8000
```

### 5. 自动推荐

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H 'Content-Type: application/json' \
  -d '{"model_params_b":70,"quantization":"none","gpus":[{"vram_total_mb":81920},{"vram_total_mb":81920}]}'
```

## 容器化部署（Docker Compose）

控制面 Master 与前端无状态，适合容器化；Agent 因需直连 GPU 与 llama.cpp 二进制，P0 阶段推荐在 GPU 节点裸机运行。

```bash
# 构建并启动 Master + 前端（前端 8080 端口已反向代理 /api 到 master）
docker compose up -d master frontend

# 可选：容器化 Agent（需 NVIDIA Container Toolkit，Linux GPU 节点）
MASTER_URL=http://<master-host>:8000 \
LLAMA_CPP_BIN_DIR=/opt/llama.cpp/bin \
docker compose --profile agent up -d agent
```

| 服务 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| master | `ghcr.io/lzl6201/deploy_llm/master` | 8000 | 控制面后端 |
| frontend | `ghcr.io/lzl6201/deploy_llm/frontend` | 8080→80 | Nginx 托管静态资源 + 代理 `/api` |
| agent | `ghcr.io/lzl6201/deploy_llm/agent` | host 网络 | 可选，需 GPU + llama.cpp 挂载 |

## CI/CD 流水线

GitHub Actions 已内置两套流水线：

- **CI**（`.github/workflows/ci.yml`）：push/PR 到 `main` 时触发，做 Python 语法编译检查（master/agent）+ 前端 `npm run build`。
- **Build & Push**（`.github/workflows/build.yml`）：push 到 `main` 或打 `v*` tag 时触发，构建三镜像并推送到 GHCR（`ghcr.io/lzl6201/deploy_llm/*`），`main` 分支额外打 `latest` 标签。

首次接入：

```bash
git init
git remote add origin git@github.com:lzl6201/deploy_llm.git
git add .
git commit -m "chore: ci/cd + docker packaging"
git push -u origin main
```

推送后即自动跑 CI；镜像推送到 GHCR 需仓库对 GitHub Actions 开放 `packages: write`（本仓库 workflow 已通过 `permissions` 声明）。生产节点可直接 `docker compose pull && docker compose up -d` 拉取最新镜像。

> **节点集成方式选型**：当前阶段采用「Master/前端容器化 + Agent 裸机」的轻量方案，Master-Agent 通过 HTTP 心跳解耦，任意节点只需跑 Agent 脚本即可接入，无需引入 K8s 的运维复杂度。待节点规模上量（如 >20 台、需要滚动发布/自愈/自动扩缩容）时，可平滑迁移：Agent 已有 `launch_config.container_image` 扩展点（`engine_runner.py`），届时将 subprocess 启动改为 K8s Job/DaemonSet 编排即可，控制面 API 无需改动。

## 常用 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/servers/register` | Agent 注册 |
| POST | `/api/servers/{id}/heartbeat` | 心跳 + GPU 指标 |
| GET | `/api/servers` | 节点列表 |
| GET | `/api/servers/{id}/gpus` | 节点 GPU 清单 |
| GET/POST | `/api/models` | 模型仓库 |
| POST | `/api/models/import` | 导入 GGUF（自动解析元数据） |
| POST | `/api/models/{id}/versions` | 新增版本 |
| GET | `/api/fs/roots` | 文件浏览器白名单根目录 |
| GET | `/api/fs/list?path=` | 目录列表 |
| GET | `/api/fs/inspect?path=` | 解析 GGUF 元数据 |
| POST | `/api/recommend` | 通用推荐（显式参数） |
| POST | `/api/recommend/plan` | 推荐（按版本 + 节点，服务端解析） |
| GET | `/api/recommend/models?server_id=` | 反向推荐（按节点显卡列出可部署模型） |
| POST | `/api/deployments` | 创建部署 |
| GET | `/api/deployments/pending` | Agent 拉取待部署任务 |
| POST | `/api/quantize` | 创建量化任务 |
| GET | `/api/quantize/pending` | Agent 拉取待量化任务 |
| GET | `/api/hf/search?query=` | 搜索 HuggingFace 模型（hf-mirror） |
| GET | `/api/hf/orgs` | GGUF 组织快捷入口 |
| GET | `/api/hf/org/{org}` | 组织模型列表 |
| GET | `/api/hf/models/{repo_id}/files` | 仓库文件列表 |
| POST | `/api/hf/download` | 创建 HF 下载任务 |
| GET | `/api/hf/downloads` | 下载任务列表（含进度） |
| GET | `/api/engines` | 引擎能力矩阵 |
