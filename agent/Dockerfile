# Agent 执行面（每台 GPU 服务器）。
#
# 容器化部署需满足：
#   1. 宿主机安装 NVIDIA Container Toolkit，运行加 `--gpus all`（compose 已配）；
#   2. 挂载共享模型存储（NFS）到 /mnt/models；
#   3. 挂载 llama.cpp 二进制到 LLAMA_CPP_BIN_DIR（llama-server / llama-quantize）。
#
# P0 阶段推荐 Agent 在 GPU 节点裸机运行（见 README），容器化属可选方案。

FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
