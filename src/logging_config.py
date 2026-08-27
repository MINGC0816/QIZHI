from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from src.config import LOG_DIR, LOG_LEVEL

_CONFIGURED = False


def setup_logging() -> None:
    """配置控制台 + 文件日志（可重复调用，仅首次生效）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    # 清掉可能已有的默认 handler，避免重复
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    app_file = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_file.setLevel(level)
    app_file.setFormatter(fmt)
    root.addHandler(app_file)

    err_file = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    err_file.setLevel(logging.ERROR)
    err_file.setFormatter(fmt)
    root.addHandler(err_file)

    # 降低第三方噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger("qizhi").info(
        "logging ready: dir=%s level=%s files=app.log,error.log",
        LOG_DIR,
        logging.getLevelName(level),
    )


def get_logger(name: str = "qizhi") -> logging.Logger:
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)
