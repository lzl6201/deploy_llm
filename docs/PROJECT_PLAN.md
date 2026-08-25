# 大模型部署平台 — 项目计划文档

> 版本：v0.1 ｜ 日期：2026-08-25 ｜ 状态：已评审

## 1. 项目概述

### 1.1 目标

构建一个 Web 化的大语言模型（LLM）部署与调度平台，统一管理内网多台 GPU 服务器，实现：

- **一键部署**：选择模型 + 目标服务器，自动生成并执行部署方案。
- **压榨显卡性能**：根据服务器配置与显存，自动给出最佳并行策略、并发参数与量化档位。
- **多机多卡**：支持单机单卡、单机多卡、多机多卡（内网）三种部署形态。
- **模型量化**：支持在线量化与预量化模型导入，量化前后显存/吞吐联动推荐。
- **可插拔**：引擎（vLLM/SGLang/TGI/llama.cpp）、部署形态（Docker/裸金属）均可配置切换。

### 1.2 范围

| 维度 | 范围 |
|---|---|
| 硬件 | NVIDIA GPU（当前），架构预留国产卡/AMD 适配 |
| 引擎 | vLLM（主力）、SGLang、TGI、llama.cpp，可插拔 |
| 模型类型 | 仅大语言模型（Chat/Completion） |
| 部署形态 | 每机独立实例 + 负载均衡；跨机张量并行（IB/RDMA 可选） |
| 量化 | 在线量化（AWQ/GPTQ/GGUF）+ 预量化导入（AWQ/GPTQ/FP8/GGUF） |
| 规模 | 1–20 台服务器 |
| 模型存储 | 内网共享存储（NFS/S3） |

### 1.3 非目标（YAGNI）

- 不支持多模态/图像生成模型（架构预留扩展点）。
- 不做 GPU 虚拟化（MIG/时间片）与计费系统。
- 不内置模型训练/微调功能。

---

## 2. 需求分析

### 2.1 功能需求

| 编号 | 需求 | 优先级 |
|---|---|---|
| F1 | 节点注册、心跳、GPU 状态采集（利用率/显存/温度/功耗） | P0 |
| F2 | 模型仓库：导入、版本管理、存储路径登记 | P0 |
| F3 | 一键部署：选模型 + 选节点 → 生成方案 → 执行 → 健康检查 → 对外服务 | P0 |
| F4 | 引擎可插拔：vLLM/SGLang/TGI/llama.cpp 适配层 | P1 |
| F5 | 自动推荐：根据 GPU/显存/模型规模给出并行度、量化、并发 | P1 |
| F6 | 单机多卡张量并行（TP） | P1 |
| F7 | 多机独立实例 + 网关负载均衡 | P1 |
| F8 | 在线量化任务（AWQ/GPTQ/GGUF）+ 预量化导入 | P2 |
| F9 | 跨机张量并行（IB/RDMA） | P2 |
| F10 | 监控聚合 + 告警（OOM/高温/宕机） | P2 |
| F11 | 认证鉴权（RBAC） | P2 |

### 2.2 非功能需求

- **性能**：节点状态采集周期 ≤ 5s；部署请求秒级下发；网关转发 P99 额外延迟 < 10ms。
- **可靠性**：Agent 断线重连；部署任务失败可重试；控制面状态持久化。
- **可扩展**：新增引擎/新增硬件只需实现适配器接口，不改核心逻辑。
- **安全**：Master-Agent 双向 Token；内网部署；可选 HTTPS。

---

## 3. 总体架构

### 3.1 两段式 Master-Agent

```
┌─────────────────────────── 控制面 Master（管理节点） ───────────────────────────┐
│  Web UI (Vue3) ──► FastAPI 后端 ──► 任务调度 / 模型仓库 / 推荐引擎 / 量化服务     │
│  监控聚合 (Prometheus+Grafana)    认证鉴权 (RBAC)                                │
└──────────────┬──────────────────────────────────────────┬──────────────────────┘
               │ HTTPS / WebSocket / Token（心跳+下发指令）  │
      ┌────────┴─────────┐                       ┌─────────┴────────┐
      │ Agent（节点1）      │ ...                   │ Agent（节点N）      │
      │ nvidia-smi 采集    │                       │ 引擎生命周期管理    │
      │ Docker / 裸金属    │                       │ 量化任务执行        │
      └───────────────────┘                       └───────────────────┘
```

**职责边界**

- **Master**：不直接操作 GPU，只负责编排、调度、推荐、监控聚合与 API 出口。
- **Agent**：部署在每台 GPU 服务器，是唯一与本地 GPU/进程/容器交互的执行者。

### 3.2 部署数据流

```
选模型 → 推荐引擎出方案(引擎/并行/量化/并发) → 调度器选空闲节点
  → 下发 Agent → Agent 拉权重(NFS 共享) → 启动引擎(Docker/裸金属)
  → 健康检查(重试 N 次) → 注册到网关/LB → 对外提供 OpenAI 兼容接口
  → 监控指标回传 → 停止/重启/扩缩容
```

---

## 4. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy | ML 生态契合，异步高并发，类型清晰 |
| 前端 | Vue 3 + Element Plus + ECharts | 管理后台成熟，图表强，中文生态好 |
| 数据库 | MySQL 8 / PostgreSQL | 1–20 台规模足够；存节点/模型/部署/任务状态 |
| 缓存/队列 | Redis | 任务队列 + 心跳状态缓存 + 分布式锁 |
| 监控 | Prometheus + Grafana | GPU/引擎指标标准方案 |
| Agent | Python + pynvml/nvidia-smi | 统一语言，采集与执行一体 |
| 通信 | REST + WebSocket | 心跳/指标用 WS，指令下发用 REST |
| 部署 | Docker + docker-compose（可切换裸金属） | 隔离性与可移植性 |

---

## 5. 核心模块设计

### 5.1 节点与 GPU 管理（NodeManager）

- Agent 启动后向 Master 注册（携带 hostname/IP/GPU 清单/驱动版本/CUDA 版本/互联类型）。
- 周期性心跳 + GPU 实时指标推送。
- 节点状态机：`online / offline / degraded`（单卡故障时降级）。
- GPU 状态机：`idle / in_use / reserved / fault`。
- 采集项：显存总量/已用、利用率、温度、功耗、进程占用、NVLink 拓扑、PCIe/IB 互联。

### 5.2 模型仓库（ModelRegistry）

- 模型登记：名称、参数量、原始 dtype、上下文长度、存储路径（NFS/S3）、来源（本地/HF/ModelScope）。
- 版本管理：同一模型可有多个量化版本（原始、FP8、AWQ-INT4、GGUF-Q4...），每个版本独立可部署。
- 不搬权重：多机共享 NFS/S3 同一份权重，Agent 直接挂载加载。

### 5.3 引擎适配层（EngineAdapter，可插拔核心）

统一接口：

```python
class EngineAdapter(ABC):
    name: str
    def supported_parallelism(self) -> list[str]: ...      # 支持 TP/PP/多机
    def supported_quantization(self) -> list[str]: ...      # 支持的量化格式
    def build_launch_config(self, req: DeployRequest) -> LaunchConfig: ...
    def health_check(self, endpoint: str) -> bool: ...
    def collect_metrics(self, endpoint: str) -> dict: ...
```

实现：`VllmAdapter`（默认）、`SglangAdapter`、`TgiAdapter`、`LlamaCppAdapter`。

- 引擎通过**注册表**按名称发现，配置驱动，新增引擎零侵入。
- 量化格式与引擎能力矩阵：AWQ/GPTQ/FP8 → vLLM/SGLang；GGUF → llama.cpp。

### 5.4 自动部署推荐引擎（RecommendEngine）

**输入**：GPU 数量/单卡显存/算力(sm)/互联类型；模型参数量/dtype/上下文长度；目标 QPS/时延。

**显存估算公式**：

```
显存占用 ≈ 参数量 × 每参数字节(dtype)            # 权重
         + 层数 × 隐藏维度 × 上下文长度 × 字节     # KV Cache
         + 激活/中间状态开销（经验系数 1.2~1.5）
```

**决策规则（优先级从高到低）**：

1. 权重放得下单卡 → 单卡部署，按剩余显存反推最大并发/批次。
2. 放不下 → 单机内 TP（2/4/8 卡）。
3. 单机仍放不下 → 若检测到 IB/RDMA 才允许跨机 TP，否则提示量化。
4. 提升量化档位（BF16→FP8→INT8→AWQ-INT4）→ 重新估算。
5. 多机多卡 → 默认每机独立实例 + 网关负载均衡；跨机 TP 作为可选方案。

**输出**：推荐引擎 + 并行度 + 量化档位 + 单实例并发 + 预估显存/吞吐，附候选方案对比。

> 规则引擎先行；接口预留 `recommend()` 可升级为基于历史运行数据的 ML 模型。

### 5.5 量化服务（QuantizeService）

- **在线量化**：提交任务 → 调度到空闲 GPU 节点 → 执行 AutoAWQ / AutoGPTQ / llama.cpp-GGUF → 产物写 NFS/S3 → 登记为新模型版本 → 回填推荐引擎（量化后显存下降）。
- **预量化导入**：HF / ModelScope / 本地路径导入 AWQ/GPTQ/FP8/GGUF。
- 任务状态机：`pending → running → succeeded / failed`，进度可查，失败可重试。
- 量化档位：BF16/FP16（不量化）、FP8、INT8、AWQ-INT4、GPTQ、GGUF（Q2/Q4/Q5/Q8）。

### 5.6 任务调度与部署生命周期（Scheduler）

- **放置策略**：按推荐方案的显存需求 + GPU 空闲度做贪心/打分放置；支持指定节点。
- **部署状态机**：`pending → pulling → launching → health_checking → running / failed → stopping → stopped`。
- **生命周期操作**：deploy / stop / restart / scale（增减副本）。
- **Agent 执行**：Docker 模式（容器编排）或裸金属模式（conda/venv + 进程管理，如 supervisor/systemd）。

### 5.7 网关与负载均衡（Gateway，可选组件）

- 对外暴露 OpenAI 兼容接口（`/v1/chat/completions` 等）。
- 后端为多个健康实例，按最少连接/加权轮询分发；实例健康检查剔除不健康后端。
- 每机独立实例模式下是核心；跨机 TP 模式下直连引擎端点。

### 5.8 监控告警（Monitor）

- **指标源**：Agent 采集 nvidia-smi + 引擎 metrics（vLLM `/metrics`）。
- **聚合**：Prometheus 拉取 Agent `/metrics`；Grafana 看板。
- **告警规则**：GPU 显存 > 95%、温度 > 85℃、实例心跳丢失、引擎 OOM、GPU 利用率异常低（浪费提示）。

> **实现说明**：当前落地为 Master 内置的有状态告警引擎（`app/services/monitor.py`），基于 Agent 心跳采集的 GPU 指标 + 部署状态周期评估；以 `dedup_key` 去重、条件解除后自动 `resolved`，暴露 `/api/monitor/*`（总览/告警列表/确认）与前端「监控告警」页。Prometheus/Grafana 作为后续可选的可观测性增强（时序指标持久化 + 看板），未阻塞 P0/P1/P2 交付。

### 5.9 认证与安全（Auth）

- Master-Agent 双向 Token（注册时签发，心跳校验）。
- 用户 RBAC：`admin（管理员）/ operator（运维）/ viewer（只读）`。
- 内网部署，可选 HTTPS（自签或内部 CA）。

---

## 6. 数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| `users` | id, username, password_hash, role | RBAC |
| `servers` | id, hostname, ip, token, status, driver, cuda, interconnect, last_seen | 节点 |
| `gpus` | id, server_id, index, name, vram_total, sm, status | 单卡 |
| `gpu_metrics` | id, gpu_id, ts, util, vram_used, temp, power | 时序（可存 Redis/TSDB） |
| `models` | id, name, params, dtype, context_len, base_storage_path, source | 模型主体 |
| `model_versions` | id, model_id, version, quantization, storage_path, size | 量化/版本 |
| `quantize_jobs` | id, model_version_id, method, node_id, status, progress, error | 量化任务 |
| `deployments` | id, model_version_id, engine, node_id, gpu_ids, tp_size, pp_size, status, endpoint | 运行实例 |
| `deploy_tasks` | id, deployment_id, action, status, detail | 操作审计 |

---

## 7. API 设计（节选）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 |
| GET | `/api/servers` | 节点列表 |
| POST | `/api/servers/{id}/register` | Agent 注册 |
| GET | `/api/servers/{id}/gpus` | 节点 GPU 清单 + 实时指标 |
| GET/POST | `/api/models` | 模型仓库 |
| POST | `/api/models/{id}/quantize` | 提交量化任务 |
| POST | `/api/recommend` | 自动推荐部署方案 |
| POST | `/api/deployments` | 创建部署 |
| POST | `/api/deployments/{id}/stop` | 停止部署 |
| GET | `/api/deployments/{id}/metrics` | 实例指标 |
| GET | `/api/engines` | 可用引擎与能力矩阵 |
| WS | `/ws/agent` | Agent 心跳/指令通道 |

---

## 8. 目录结构

```
deploy_llm/
├── docs/
│   └── PROJECT_PLAN.md
├── master/                       # 控制面后端
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── config.py             # 配置（env 驱动）
│   │   ├── db/                   # 数据库会话/迁移
│   │   ├── models/               # SQLAlchemy ORM
│   │   ├── schemas/              # Pydantic 模型
│   │   ├── api/                  # 路由层
│   │   ├── services/             # 业务层
│   │   │   ├── node_manager.py
│   │   │   ├── scheduler.py
│   │   │   ├── recommend_engine.py
│   │   │   ├── quantize_service.py
│   │   │   └── engine/
│   │   │       ├── base.py       # EngineAdapter 接口
│   │   │       ├── vllm.py
│   │   │       ├── sglang.py
│   │   │       ├── tgi.py
│   │   │       └── llamacpp.py
│   ├── requirements.txt
│   └── Dockerfile
├── agent/                        # 执行面
│   ├── main.py                   # Agent 入口
│   ├── gpu_collector.py          # nvidia-smi/pynvml 采集
│   ├── engine_runner.py          # 引擎启动/停止/健康检查
│   ├── config.py
│   └── requirements.txt
├── frontend/                     # Vue3 前端
│   ├── src/
│   │   ├── views/                # 节点/模型/部署/量化/监控页
│   │   ├── api/                  # Axios 封装
│   │   └── ...
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## 9. 分阶段实施计划

| 阶段 | 内容 | 交付物 | 验收标准 |
|---|---|---|---|
| **P0 基础骨架** | Master-Agent 通信、节点/GPU 管理、单机单卡 vLLM 部署闭环 | 后端 + Agent + 最小前端 | 能注册节点、看到 GPU、一键部署一个模型并对话 |
| **P1 并行与调度** | 单机多卡 TP、多机独立实例 + 网关 LB、调度器 | 并行部署 + 网关 | 多卡/多机部署可用，请求被正确分发 |
| **P2 推荐与量化** | 显存估算、自动推荐、在线量化 + 预量化导入 | 推荐引擎 + 量化服务 | 输入模型与目标能给出合理方案；量化产物可部署 |
| **P3 完善** | 跨机 TP（IB/RDMA）、监控告警、RBAC、多引擎扩展（SGLang/TGI/llama.cpp） | 完整平台 | 20 台规模稳定运行，告警与权限生效 |

---

## 10. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 跨机 TP 性能差（内网无 IB） | 多机大模型慢 | 默认每机独立实例；跨机 TP 仅在检测到 RDMA 时启用，并在 UI 强提示 |
| 显存估算偏差导致 OOM | 部署失败 | 预留经验系数；启动失败自动降级量化档位重试 |
| 引擎参数差异大 | 适配成本高 | 适配层只抽象生命周期，参数透传 + 模板化 |
| 量化耗时/占卡 | 与推理争抢资源 | 量化任务单独调度，优先级低于在线推理 |
| Agent 断连 | 状态失真 | 心跳超时标记 offline，重连后全量对账 |
| 多版本权重管理混乱 | 部署错版本 | 模型-版本二级结构，部署锁定 version |

---

## 11. 测试策略

- **单元测试**：推荐引擎显存估算公式、引擎适配器参数生成、状态机转换。
- **集成测试**：Agent 注册 → 心跳 → 部署 → 健康检查 → 停止 全链路（mock 或真实单卡）。
- **性能测试**：网关转发延迟、20 节点心跳聚合压力、指标采集开销。
- **验收测试**：按 P0–P3 各阶段验收标准逐项验证。

---

## 12. 里程碑

| 里程碑 | 目标日期 | 状态 |
|---|---|---|
| M1 P0 完成（单机单卡闭环） | 待定 | 已完成 |
| M2 P1 完成（并行 + 调度） | 待定 | 已完成（调度器 + 网关 LB + 副本扩缩 + 跨机 TP 门控） |
| M3 P2 完成（推荐 + 量化） | 待定 | 部分完成（推荐 + 在线/预量化导入 + Docker 编排；跨机 TP 多节点编排待 IB 硬件） |
| M4 P3 完成（完整平台） | 待定 | 部分完成（监控告警已实现；RBAC + 多引擎 SGLang/TGI 待做） |

---

> 本文档为项目开发基准。后续实现中如发现设计与实际冲突，将同步回更本文档并注明变更原因。
