from __future__ import annotations

import pandas as pd

from .report_learning_layer import apply_learning_layer


def apply_learning_layer_compat(cards: pd.DataFrame) -> pd.DataFrame:
    """Apply learning labels while preserving legacy report grouping.

    The original magazine renderer still expects non-official rows in the legacy `no_play`
    bucket. The learning layer adds better consumer labels, so this wrapper keeps those
    rows visible in older magazine/markdown/PDF paths while Premium Cards use `report_lane_v2`.
    """
    frame = apply_learning_layer(cards)
    if frame is not None and not frame.empty and 'report_lane' in frame.columns:
        frame['report_lane'] = frame['report_lane'].replace({'research': 'no_play'})
    return frame
