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
- [x] Web 前端（Vue3：节点总览 / 模型仓库 / 智能推荐 / 一键部署 / 部署管理 / 模型量化 / 监控告警）
- [x] 反向推荐（按节点显卡列出可部署模型）
- [x] HuggingFace 模型发现 + 下载（走 hf-mirror 国内镜像，进度条 + 完成后自动注册）
- [x] 调度器：按显存需求 + GPU 空闲度自动选节点（支持指定节点，GGUF 解析结果进程内缓存）
- [x] 部署生命周期：停止 / 重启（`stopping → stopped → pending` 状态机 + `DeployTask` 意图）
- [x] 网关负载均衡：OpenAI 兼容 `/v1/*` 按模型名分发到多副本（轮询 + 失败冷却 + SSE 透传）
- [x] 副本扩缩：`scale` 一键增减同模型版本的运行实例数
- [x] 预量化导入：FP8 / AWQ / GPTQ 等已量化模型登记
- [x] Docker 编排：部署指定 `container_image` 后 Agent 走 `docker run`（否则裸金属 subprocess）
- [x] 跨机 TP 门控：Agent 检测 NVLink/IB 互联，调度器在无 RDMA 时拦截跨机张量并行
- [ ] 跨机张量并行 TP 多节点编排（Ray 集群，需 IB/RDMA 硬件）（P3）
- [x] 监控聚合 + 告警（心跳丢失/显存过高/温度过高/利用率低/部署 OOM，`open→resolved` 生命周期 + 去重）
- [ ] 认证鉴权 RBAC（P2）

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
| POST | `/api/models/prequantized` | 预量化导入（FP8/AWQ/GPTQ，显式登记元数据） |
| POST | `/api/models/{id}/versions` | 新增版本 |
| GET | `/api/fs/roots` | 文件浏览器白名单根目录 |
| GET | `/api/fs/list?path=` | 目录列表 |
| GET | `/api/fs/inspect?path=` | 解析 GGUF 元数据 |
| POST | `/api/recommend` | 通用推荐（显式参数） |
| POST | `/api/recommend/plan` | 推荐（按版本 + 节点，服务端解析） |
| GET | `/api/recommend/models?server_id=` | 反向推荐（按节点显卡列出可部署模型） |
| POST | `/api/deployments` | 创建部署（`server_id`/`engine` 可省略，自动选节点并按格式解析引擎） |
| POST | `/api/deployments/place` | 放置预览：返回按分数降序的候选节点 |
| GET | `/api/deployments/pending` | Agent 拉取待部署任务 |
| GET | `/api/deployments/stopping` | Agent 拉取待停止的部署 |
| POST | `/api/deployments/{id}/stop` | 停止部署（置 `stopping`，Agent 杀进程后回传 `stopped`） |
| POST | `/api/deployments/{id}/restart` | 重启部署（`stopping`→`stopped`→自动重新 `pending` 拉起） |
| POST | `/api/deployments/{id}/status` | Agent 回传部署状态（`running`/`failed`/`stopped` + endpoint） |
| POST | `/api/deployments/{id}/scale` | 副本扩缩（调整同 model_version+engine 的实例数） |
| GET | `/v1/models` | 网关：列出可对外服务的模型 |
| POST | `/v1/chat/completions` | 网关：OpenAI 兼容对话（按 `model` 分发 + SSE 透传） |
| POST | `/v1/completions` | 网关：OpenAI 兼容补全 |
| POST | `/api/quantize` | 创建量化任务 |
| GET | `/api/quantize/pending` | Agent 拉取待量化任务 |
| GET | `/api/hf/search?query=` | 搜索 HuggingFace 模型（hf-mirror） |
| GET | `/api/hf/orgs` | GGUF 组织快捷入口 |
| GET | `/api/hf/org/{org}` | 组织模型列表 |
| GET | `/api/hf/models/{repo_id}/files` | 仓库文件列表 |
| POST | `/api/hf/download` | 创建 HF 下载任务 |
| GET | `/api/hf/downloads` | 下载任务列表（含进度） |
| GET | `/api/monitor/overview` | 监控总览（节点/GPU/显存/运行实例/告警统计） |
| GET | `/api/monitor/alerts?open_only=` | 告警列表（支持只看未处理） |
| POST | `/api/monitor/alerts/{id}/ack` | 确认/处理告警（置 `resolved`） |
| GET | `/api/engines` | 引擎能力矩阵 |

### 部署生命周期

部署状态机：`pending → running/failed → stopping → stopped`，重启在 `stopped` 后自动回到 `pending` 重新拉起。

- **创建**：`POST /api/deployments` 落库为 `pending`，Agent 轮询 `/pending` 拉起进程，健康检查通过后回传 `running`（含 endpoint）。
- **停止**：`POST /api/deployments/{id}/stop` 置 `stopping`，Agent 杀进程后回传 `stopped`。
- **重启**：`POST /api/deployments/{id}/restart` 复用 `stopping → stopped` 流程，Master 收到 `stopped` 后自动重新置 `pending` 并新增 deploy 任务（`pending`/`stopping` 状态下重启返回 409）。
- 停止/重启意图用 `DeployTask`（`action=stop/restart`）落库，Agent 无需感知重启差异。

### 网关与副本

- **服务 = 模型名**：网关把「同一模型名的所有 `running` 实例」视为后端池，对外暴露 OpenAI 兼容接口（`/v1/chat/completions`、`/v1/completions`、`/v1/models`），客户端传 `model` 字段即路由到对应池。
- **分发策略**：轮询（round-robin）；代理失败的后端进入 10s 冷却，冷却期内不参与分发，避免打到不健康实例。
- **副本扩缩**：`POST /api/deployments/{id}/scale` 传 `{replicas: N}`，将「同 model_version + engine」的实例数调整到 N（增则自动放置并克隆端口，减则停止最新副本）。配合网关即可对单模型做多副本水平扩展。

### 部署形态（裸金属 / Docker）

部署创建时可传 `container_image`（或通过 `VLLM_CONTAINER_IMAGE` / `LLAMA_CPP_CONTAINER_IMAGE` 环境变量设置默认值）：

- **裸金属**（默认）：Agent 在本机 subprocess 启动引擎（`resolve_command` 解析 `{LLAMA_CPP_BIN}` 占位符）。
- **Docker**：Agent 执行 `docker run -d --gpus all -p {port}:{port} -e K=V ... {image} {command}`，引擎命令原样透传为容器 CMD。模型存储需由镜像/挂载保证容器内可见（NFS）。

### 跨机张量并行（IB/RDMA）

- Agent 采集时自动检测互联类型（`pcie` / `nvlink` / `ib`），写入 `Server.interconnect`。
- 调度器在 `tp_size` 超过单节点 GPU 数、且集群无 `ib`/`nvlink` 互联节点时，返回明确错误提示降级（降并行度或量化），避免在无 RDMA 下强行跨机 TP。
- 多节点 Ray 编排（`--worker-use-ray` + RAY_ADDRESS 启动脚手架已预留）需 IB/RDMA 硬件，列为 P3。

### HuggingFace 模型发现与下载

- 模型仓库页内置「HuggingFace」标签，支持关键词搜索与 GGUF 组织（`bartowski` / `TheBloke` / `ggml-org` / `lmstudio-community`）快捷浏览。
- 下载走国内镜像 `hf-mirror.com`，Master 直连镜像（`trust_env=False`，绕过本机失效代理），后台线程流式下载 + 进度回写；完成后 GGUF 自动解析并注册为模型版本。
- 环境变量：`HF_ENDPOINT`（默认 `https://hf-mirror.com`）、`HF_TOKEN`（可选，gated 模型）、`HF_DOWNLOAD_DIR`（默认与 `MODEL_STORAGE_BASE` 一致）。

### 监控告警

- Master 后台线程按 `ALERT_POLL_INTERVAL` 周期评估告警规则（心跳丢失 / 显存过高 / 温度过高 / 利用率低 / 部署 OOM 与失败），以 `dedup_key` 去重，条件解除后自动 `resolved`。
- 阈值环境变量：`HEARTBEAT_TIMEOUT`（默认 30s）、`VRAM_ALERT_PCT`（95）、`TEMP_ALERT_C`（85）、`GPU_IDLE_PCT`（5）。
