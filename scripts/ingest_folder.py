#!/usr/bin/env python
"""批量将 data/raw（或 samples）中的文档入库。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config import RAW_DIR, SAMPLES_DIR
from src.ingest.loaders import SUPPORTED_SUFFIXES
from src.ingest.pipeline import ingest_files


def main() -> None:
    parser = argparse.ArgumentParser(description="企业知识库批量入库")
    parser.add_argument("--dir", type=Path, default=None, help="文档目录，默认 data/raw")
    parser.add_argument("--samples", action="store_true", help="入库 samples/ 示例制度")
    args = parser.parse_args()

    target = SAMPLES_DIR if args.samples else (args.dir or RAW_DIR)
    if not target.is_dir():
        print(f"[错误] 目录不存在: {target}")
        sys.exit(1)

    paths = sorted(
        p
        for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not paths:
        print(f"[提示] {target} 下无支持的文件。可先: python scripts/ingest_folder.py --samples")
        sys.exit(0)

    result = ingest_files(paths)
    print(result)
    if result.get("errors"):
        sys.exit(1)


if __name__ == "__main__":
    main()
