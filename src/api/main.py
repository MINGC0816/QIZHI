from __future__ import annotations

import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent.kb_agent import ask, delete_thread, get_thread_messages
from src.config import RAW_DIR
from src.ingest.chunking import split_documents
from src.ingest.loaders import SUPPORTED_SUFFIXES, load_file
from src.ingest.pipeline import ingest_files, ingest_raw_dir
from src.logging_config import get_logger, setup_logging
from src.rag.store import delete_by_source, get_vectorstore, list_sources
from src.sessions.store import create_thread, get_thread, list_threads

setup_logging()
log = get_logger("qizhi.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("API startup")
    yield
    log.info("API shutdown")


app = FastAPI(
    title="Enterprise KB Agent",
    description="企业内部员工知识问答智能体 API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:
        log.exception("unhandled error path=%s", request.url.path)
        raise
    finally:
        # 健康检查太吵，降为 debug
        elapsed_ms = (time.perf_counter() - started) * 1000
        msg = "%s %s -> %s (%.1fms)" % (
            request.method,
            request.url.path,
            status,
            elapsed_ms,
        )
        if request.url.path == "/health":
            log.debug(msg)
        elif status >= 500:
            log.error(msg)
        elif status >= 400:
            log.warning(msg)
        else:
            log.info(msg)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    thread_id: str


class IngestRequest(BaseModel):
    filename: Optional[str] = None
    replace: bool = True


class CreateThreadRequest(BaseModel):
    user_id: str = "local"
    title: str = "新对话"


class PreviewChunk(BaseModel):
    chunk_id: int
    page: int | None = None
    content: str


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- 用户问答 / 会话 ----------


@app.get("/api/v1/threads")
def api_list_threads(user_id: str = "local"):
    return {"threads": list_threads(user_id=user_id)}


@app.post("/api/v1/threads")
def api_create_thread(body: CreateThreadRequest = CreateThreadRequest()):
    row = create_thread(user_id=body.user_id, title=body.title)
    log.info("thread created id=%s user=%s", row.get("thread_id"), body.user_id)
    return row


@app.get("/api/v1/threads/{thread_id}")
def api_get_thread(thread_id: str):
    row = get_thread(thread_id)
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    return row


@app.get("/api/v1/threads/{thread_id}/messages")
def api_thread_messages(thread_id: str):
    return {"thread_id": thread_id, "messages": get_thread_messages(thread_id)}


@app.delete("/api/v1/threads/{thread_id}")
def api_delete_thread(thread_id: str):
    delete_thread(thread_id)
    log.info("thread deleted id=%s", thread_id)
    return {"ok": True, "thread_id": thread_id}


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    log.info(
        "chat start thread=%s q_len=%s",
        body.thread_id,
        len(body.message),
    )
    try:
        answer = ask(body.message, thread_id=body.thread_id)
    except Exception as e:  # noqa: BLE001
        log.exception("chat failed thread=%s", body.thread_id)
        raise HTTPException(status_code=500, detail=str(e)) from e
    log.info(
        "chat done thread=%s answer_len=%s",
        body.thread_id,
        len(answer or ""),
    )
    return ChatResponse(answer=answer, thread_id=body.thread_id)


# ---------- 知识库管理（Admin） ----------


@app.get("/api/v1/admin/documents")
def admin_documents():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    indexed = set(list_sources())
    files = sorted(
        p.name
        for p in RAW_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    for name in sorted(indexed):
        if name not in files:
            files.append(name)
    return {
        "documents": [
            {
                "filename": name,
                "indexed": name in indexed,
                "has_raw": (RAW_DIR / name).is_file(),
            }
            for name in files
        ]
    }


@app.get("/api/v1/admin/documents/{filename}/preview")
def admin_document_preview(filename: str, max_chars: int = 8000):
    path = RAW_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

    try:
        docs = load_file(path)
    except ValueError as e:
        log.warning("preview rejected file=%s err=%s", filename, e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("preview failed file=%s", filename)
        raise HTTPException(status_code=500, detail=f"解析失败: {e}") from e

    pages = [
        {
            "page": d.metadata.get("page"),
            "content": d.page_content,
        }
        for d in docs
    ]
    full_text = "\n\n".join(d.page_content for d in docs).strip()
    full_text = full_text[: max(500, min(max_chars, 50000))]
    log.info("preview ok file=%s pages=%s", filename, len(pages))
    return {
        "filename": filename,
        "page_count": len(pages),
        "content_preview": full_text,
        "pages": pages,
    }


@app.get("/api/v1/admin/documents/{filename}/chunks")
def admin_document_chunks(filename: str, max_chunks: int = 200):
    path = RAW_DIR / filename
    has_raw = path.is_file()

    store = get_vectorstore()
    data = store.get(
        where={"source": filename},
        include=["documents", "metadatas"],
    )
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    chunks: list[PreviewChunk] = []

    for doc_text, meta in zip(docs, metas):
        if not isinstance(doc_text, str):
            continue
        chunk_id = -1
        page = None
        if isinstance(meta, dict):
            try:
                chunk_id = int(meta.get("chunk_id", -1))
            except Exception:
                chunk_id = -1
            page_val = meta.get("page")
            if isinstance(page_val, int):
                page = page_val
        chunks.append(PreviewChunk(chunk_id=chunk_id, page=page, content=doc_text))

    chunks.sort(key=lambda c: c.chunk_id)
    if chunks:
        log.info(
            "chunks from vectorstore file=%s count=%s",
            filename,
            len(chunks),
        )
        return {
            "filename": filename,
            "from_vectorstore": True,
            "chunk_count": len(chunks),
            "chunks": [c.model_dump() for c in chunks[: max(1, min(max_chunks, 1000))]],
        }

    if not has_raw:
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在且向量库无切片: {filename}",
        )

    try:
        preview_docs = load_file(path)
    except ValueError as e:
        log.warning("chunks rejected file=%s err=%s", filename, e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("chunks failed file=%s", filename)
        raise HTTPException(status_code=500, detail=f"解析失败: {e}") from e

    split = split_documents(preview_docs)
    for idx, ch in enumerate(split):
        page_val = ch.metadata.get("page")
        page = page_val if isinstance(page_val, int) else None
        chunks.append(
            PreviewChunk(
                chunk_id=idx,
                page=page,
                content=ch.page_content,
            )
        )

    log.info("chunks preview split file=%s count=%s", filename, len(chunks))
    return {
        "filename": filename,
        "from_vectorstore": False,
        "chunk_count": len(chunks),
        "chunks": [c.model_dump() for c in chunks[: max(1, min(max_chunks, 1000))]],
    }


@app.post("/api/v1/admin/upload")
async def admin_upload(file: UploadFile = File(...)):
    raw_name = Path(file.filename or "").name
    suffix = Path(raw_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {suffix}，支持 {sorted(SUPPORTED_SUFFIXES)}",
        )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / raw_name
    try:
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:  # noqa: BLE001
        log.exception("upload failed file=%s", raw_name)
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}") from e
    size = dest.stat().st_size if dest.is_file() else 0
    log.info("upload ok file=%s size=%s", dest.name, size)
    return {"saved": dest.name, "path": str(dest)}


@app.post("/api/v1/admin/ingest")
def admin_ingest(body: IngestRequest = IngestRequest()):
    log.info("ingest start filename=%s replace=%s", body.filename, body.replace)
    if body.filename:
        path = RAW_DIR / body.filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"文件不存在: {body.filename}")
        result = ingest_files([path], replace=body.replace)
    else:
        result = ingest_raw_dir(replace=body.replace)
    log.info(
        "ingest done ingested=%s chunks=%s errors=%s",
        len(result.get("ingested") or []),
        result.get("chunk_count"),
        len(result.get("errors") or []),
    )
    return result


@app.delete("/api/v1/admin/documents/{filename}")
def admin_delete_document(filename: str):
    """删除原始文件（若存在）并清除向量库中对应切片。"""
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name:
        raise HTTPException(status_code=400, detail="非法文件名")

    path = RAW_DIR / safe_name
    indexed = safe_name in set(list_sources())
    has_raw = path.is_file()

    if not has_raw and not indexed:
        raise HTTPException(status_code=404, detail=f"文档不存在: {safe_name}")

    deleted_raw = False
    if has_raw:
        try:
            path.unlink()
            deleted_raw = True
        except Exception as e:  # noqa: BLE001
            log.exception("delete raw failed file=%s", safe_name)
            raise HTTPException(status_code=500, detail=f"删除文件失败: {e}") from e

    deleted_index = False
    if indexed:
        delete_by_source(safe_name)
        deleted_index = True

    log.info(
        "document deleted file=%s raw=%s index=%s",
        safe_name,
        deleted_raw,
        deleted_index,
    )
    return {
        "ok": True,
        "filename": safe_name,
        "deleted_raw": deleted_raw,
        "deleted_index": deleted_index,
    }


# 兼容旧路径（可选）
@app.get("/api/v1/documents")
def documents_compat():
    return admin_documents()


@app.post("/api/v1/upload")
async def upload_compat(file: UploadFile = File(...)):
    return await admin_upload(file)


@app.post("/api/v1/ingest")
def ingest_compat(body: IngestRequest = IngestRequest()):
    return admin_ingest(body)
