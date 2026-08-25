from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), unique=True, index=True)
    ip = Column(String(64))
    token = Column(String(255))
    driver = Column(String(64))
    cuda = Column(String(64))
    interconnect = Column(String(64), default="pcie")  # pcie / nvlink / ib
    total_gpus = Column(Integer, default=0)
    status = Column(String(32), default="offline")  # online / offline / degraded
    source = Column(String(32), default="agent")  # agent / manual
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    gpus = relationship("GPU", back_populates="server", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="server")


class GPU(Base):
    __tablename__ = "gpus"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"))
    index = Column(Integer)
    name = Column(String(128))
    vram_total_mb = Column(Integer)
    vram_used_mb = Column(Integer, default=0)
    utilization = Column(Float, default=0.0)
    temperature = Column(Float, default=0.0)
    power_w = Column(Float, default=0.0)
    sm = Column(String(32))
    status = Column(String(32), default="idle")  # idle / in_use / reserved / fault

    server = relationship("Server", back_populates="gpus")


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    params_b = Column(Float)  # 参数量（十亿）
    architecture = Column(String(64), default="")  # qwen35 / llama / ...
    dtype = Column(String(32), default="bf16")  # 基础精度（未量化前的权重精度）
    format = Column(String(32), default="safetensors")  # gguf / safetensors / ollama
    context_len = Column(Integer, default=4096)
    base_storage_path = Column(String(512))
    source = Column(String(64), default="local")  # local / hf / modelscope
    created_at = Column(DateTime, default=datetime.utcnow)

    versions = relationship(
        "ModelVersion", back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"))
    version = Column(String(64))
    quantization = Column(String(32), default="none")  # 压缩档位：Q3_K_L / FP8 / AWQ-INT4 / none
    dtype = Column(String(32), default="bf16")  # 基础精度：F16 / F32 / BF16
    format = Column(String(32), default="safetensors")  # gguf / safetensors / ollama
    architecture = Column(String(64), default="")
    gguf_file_type = Column(Integer, default=0)
    storage_path = Column(String(512))
    size_gb = Column(Float)
    file_size_mb = Column(Integer, default=0)  # 实际文件大小（GGUF 用于精确显存估算）

    model = relationship("Model", back_populates="versions")
    deployments = relationship("Deployment", back_populates="model_version")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    model_version_id = Column(Integer, ForeignKey("model_versions.id"))
    engine = Column(String(32), default="vllm")
    format = Column(String(32), default="safetensors")  # 引擎路由依据（gguf→llama.cpp）
    server_id = Column(Integer, ForeignKey("servers.id"))
    gpu_ids = Column(JSON, default=list)  # [0, 1, 2, 3]
    tp_size = Column(Integer, default=1)
    pp_size = Column(Integer, default=1)
    quant = Column(String(32), default="none")
    max_model_len = Column(Integer, default=4096)
    port = Column(Integer, default=8000)
    extra = Column(JSON, default=dict)
    container_image = Column(String(255))  # 非空则 Agent 走 Docker 编排，否则裸金属
    status = Column(String(32), default="pending")
    endpoint = Column(String(255))
    last_error = Column(Text)  # 最近一次失败原因（用于 OOM 等告警）
    created_at = Column(DateTime, default=datetime.utcnow)

    server = relationship("Server", back_populates="deployments")
    model_version = relationship("ModelVersion", back_populates="deployments")


class QuantizeJob(Base):
    __tablename__ = "quantize_jobs"

    id = Column(Integer, primary_key=True, index=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"))
    method = Column(String(32), default="llama-quantize")  # llama-quantize / awq / gptq
    target_quant = Column(String(32))  # 目标量化档位，如 Q4_K_M
    server_id = Column(Integer)
    source_path = Column(String(512))
    target_path = Column(String(512))
    status = Column(String(32), default="pending")  # pending / running / done / failed
    progress = Column(Float, default=0.0)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class DownloadJob(Base):
    __tablename__ = "download_jobs"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(String(255))
    filename = Column(String(512))
    dest_path = Column(String(512))
    size_bytes = Column(Integer, default=0)
    downloaded_bytes = Column(Integer, default=0)
    status = Column(String(32), default="pending")  # pending / running / done / failed
    progress = Column(Float, default=0.0)
    error = Column(Text)
    model_version_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeployTask(Base):
    __tablename__ = "deploy_tasks"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"))
    action = Column(String(32))  # deploy / stop / restart
    status = Column(String(32), default="pending")
    detail = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(32), default="viewer")  # admin / operator / viewer


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, nullable=True)  # 关联节点；全局告警可为空
    dedup_key = Column(String(128), index=True)  # 去重键，如 "gpu_vram_high:1:0"
    type = Column(String(64))  # heartbeat_lost / gpu_vram_high / gpu_temp_high / deploy_oom / gpu_idle
    severity = Column(String(16), default="warning")  # critical / warning / info
    message = Column(Text)
    status = Column(String(16), default="open")  # open / resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
