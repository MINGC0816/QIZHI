from __future__ import annotations

from pathlib import Path

from src.config import RAW_DIR
from src.ingest.chunking import split_documents
from src.ingest.loaders import SUPPORTED_SUFFIXES, load_file
from src.logging_config import get_logger
from src.rag.store import add_documents, delete_by_source

log = get_logger("qizhi.ingest")


def ingest_files(paths: list[Path], *, replace: bool = True) -> dict:
    """解析、分块并写入向量库。"""
    total_chunks = 0
    ingested: list[str] = []
    errors: list[str] = []

    for path in paths:
        path = Path(path)
        try:
            log.info("ingest file start name=%s", path.name)
            docs = load_file(path)
            chunks = split_documents(docs)
            for i, chunk in enumerate(chunks):
                chunk.metadata["chunk_id"] = i
            if replace:
                delete_by_source(path.name)
            add_documents(chunks)
            total_chunks += len(chunks)
            ingested.append(path.name)
            log.info(
                "ingest file ok name=%s docs=%s chunks=%s",
                path.name,
                len(docs),
                len(chunks),
            )
        except Exception as e:  # noqa: BLE001 — 批量入库需汇总错误
            log.exception("ingest file failed name=%s", path.name)
            errors.append(f"{path.name}: {e}")

    return {
        "ingested": ingested,
        "chunk_count": total_chunks,
        "errors": errors,
    }


def ingest_raw_dir(raw_dir: Path | None = None, *, replace: bool = True) -> dict:
    raw_dir = Path(raw_dir or RAW_DIR)
    paths = sorted(
        p
        for p in raw_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not paths:
        log.warning("ingest raw empty dir=%s", raw_dir)
        return {"ingested": [], "chunk_count": 0, "errors": ["raw 目录无支持的文件"]}
    log.info("ingest raw dir=%s files=%s", raw_dir, len(paths))
    return ingest_files(paths, replace=replace)
