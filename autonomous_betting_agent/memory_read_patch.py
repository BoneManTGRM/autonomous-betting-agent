from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


def install_memory_read_merge(repo_memory_path: Path) -> None:
    """Patch pandas CSV loading so uploaded ARA memory accumulates.

    The Pro Predictor page reads uploaded/pasted memory with pandas.read_csv.
    This patch makes those uploaded/pasted frames merge with built-in repo memory
    instead of replacing it. Reading the built-in repo memory itself is left
    unchanged.
    """
    real_read_csv = pd.read_csv
    repo_path = Path(repo_memory_path).resolve()

    def source_path(source: Any) -> Path | None:
        if isinstance(source, (str, Path)):
            try:
                return Path(source).resolve()
            except Exception:
                return None
        return None

    def should_merge(source: Any) -> bool:
        path = source_path(source)
        if path is not None:
            return path != repo_path
        return isinstance(source, StringIO) or hasattr(source, "name") or hasattr(source, "getvalue") or hasattr(source, "read")

    def merged_read_csv(source, *args, **kwargs):
        frame = real_read_csv(source, *args, **kwargs)
        if not should_merge(source) or not repo_path.exists():
            return frame
        try:
            base = real_read_csv(repo_path)
        except Exception:
            return frame
        if base.empty:
            return frame
        if frame.empty:
            return base
        combined = pd.concat([base, frame], ignore_index=True, sort=False)
        try:
            return combined.drop_duplicates(ignore_index=True)
        except Exception:
            return combined

    pd.read_csv = merged_read_csv
