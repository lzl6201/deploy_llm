"""模型仓库注册：解析 GGUF 并登记 Model + ModelVersion。

本地导入（`api/models.py::import_model`）与 HF 下载完成（`downloader.py`）
共用此逻辑，避免重复。同名模型已存在时追加新版本（不同量化档位），
而非报错。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.orm import Model, ModelVersion
from app.services.gguf import GGUFError, parse_gguf


def register_gguf(
    db: Session, path: str, version: str = "v1", source: str = "huggingface"
) -> Model:
    """解析 GGUF 文件并登记模型；已存在同名模型则追加版本。"""
    info = parse_gguf(path)

    model = db.query(Model).filter(Model.name == info.name).first()
    if model is None:
        model = Model(
            name=info.name,
            params_b=info.params_b,
            architecture=info.architecture,
            dtype="F16",
            format="gguf",
            context_len=info.context_len,
            base_storage_path=info.path,
            source=source,
        )
        db.add(model)
        db.flush()

    exists = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_id == model.id, ModelVersion.storage_path == info.path)
        .first()
    )
    if exists is None:
        mv = ModelVersion(
            model_id=model.id,
            version=version,
            quantization=info.file_type_label or "none",
            dtype="F16",
            format="gguf",
            architecture=info.architecture,
            gguf_file_type=info.file_type,
            storage_path=info.path,
            size_gb=round(info.file_size_bytes / (1024**3), 3),
            file_size_mb=int(info.file_size_bytes // (1024 * 1024)),
        )
        db.add(mv)

    db.commit()
    db.refresh(model)
    return model


def register_prequantized(
    db: Session,
    name: str,
    params_b: float,
    storage_path: str,
    quantization: str = "none",
    dtype: str = "bf16",
    version: str = "v1",
    format: str = "safetensors",
    architecture: str = "",
    context_len: int = 4096,
    size_gb: float | None = None,
    source: str = "local",
) -> Model:
    """登记已量化模型（FP8/AWQ/GPTQ 等）。同名模型追加版本。"""
    model = db.query(Model).filter(Model.name == name).first()
    if model is None:
        model = Model(
            name=name,
            params_b=params_b,
            architecture=architecture,
            dtype=dtype,
            format=format,
            context_len=context_len,
            base_storage_path=storage_path,
            source=source,
        )
        db.add(model)
        db.flush()

    exists = (
        db.query(ModelVersion)
        .filter(
            ModelVersion.model_id == model.id,
            ModelVersion.storage_path == storage_path,
        )
        .first()
    )
    if exists is None:
        db.add(
            ModelVersion(
                model_id=model.id,
                version=version,
                quantization=quantization,
                dtype=dtype,
                format=format,
                architecture=architecture,
                storage_path=storage_path,
                size_gb=size_gb,
            )
        )

    db.commit()
    db.refresh(model)
    return model
