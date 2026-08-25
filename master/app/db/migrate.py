"""轻量自动迁移（SQLite）。

项目当前以 SQLite 为默认存储，schema 演进时对「新增列」执行 ALTER TABLE
ADD COLUMN（幂等），对 schema 重构的表（如 quantize_jobs 由 P0 占位改为正式
字段）则重建。生产环境（MySQL/PostgreSQL）应改用 Alembic，此模块仅兜底。
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.session import engine

# 表 -> {列名: DDL}（仅 SQLite 方言，缺列时补充）
_NEW_COLUMNS: dict[str, dict[str, str]] = {
    "models": {
        "architecture": "VARCHAR(64) DEFAULT ''",
        "format": "VARCHAR(32) DEFAULT 'safetensors'",
    },
    "model_versions": {
        "dtype": "VARCHAR(32) DEFAULT 'bf16'",
        "format": "VARCHAR(32) DEFAULT 'safetensors'",
        "architecture": "VARCHAR(64) DEFAULT ''",
        "gguf_file_type": "INTEGER DEFAULT 0",
        "file_size_mb": "INTEGER DEFAULT 0",
    },
    "deployments": {
        "format": "VARCHAR(32) DEFAULT 'safetensors'",
        "extra": "TEXT DEFAULT '{}'",
    },
    "servers": {
        "source": "VARCHAR(32) DEFAULT 'agent'",
    },
}


def _add_columns() -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for table, columns in _NEW_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for col, ddl in columns.items():
            if col in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {ddl}'))


def _rebuild_quantize_jobs() -> None:
    """quantize_jobs 由占位 schema 改为正式字段，若为旧结构则重建。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "quantize_jobs" not in tables:
        return
    columns = {c["name"] for c in insp.get_columns("quantize_jobs")}
    # 旧结构以 model_id/node_id 为主键外键，新结构以 model_version_id/server_id
    if "model_id" in columns and "model_version_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE quantize_jobs"))


def migrate() -> None:
    if engine.dialect.name != "sqlite":
        return
    _rebuild_quantize_jobs()
    _add_columns()
