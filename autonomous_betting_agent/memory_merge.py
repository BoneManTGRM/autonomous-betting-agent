from __future__ import annotations

from typing import Optional

import pandas as pd


def merge_memory_frames(base: Optional[pd.DataFrame], extra: Optional[pd.DataFrame]) -> pd.DataFrame | None:
    """Combine built-in ARA memory with uploaded or pasted memory.

    The built-in repo memory is treated as the base memory. Uploaded or pasted
    memory is appended so learning rows accumulate instead of replacing the
    base memory. Exact duplicate rows are removed when possible.
    """
    frames = []
    if base is not None and not base.empty:
        frames.append(base)
    if extra is not None and not extra.empty:
        frames.append(extra)
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True, sort=False)
    try:
        combined = combined.drop_duplicates(ignore_index=True)
    except Exception:
        pass
    return combined
