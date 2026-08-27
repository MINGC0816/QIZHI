"""文档入库包。"""

from src.ingest.loaders import SUPPORTED_SUFFIXES, load_file, load_paths
from src.ingest.pipeline import ingest_files, ingest_raw_dir

__all__ = [
    "SUPPORTED_SUFFIXES",
    "load_file",
    "load_paths",
    "ingest_files",
    "ingest_raw_dir",
]
