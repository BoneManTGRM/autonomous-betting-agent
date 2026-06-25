from __future__ import annotations

import builtins
import os


def get_secret(*names: str) -> str:
    """Read a secret from Streamlit secrets first, then environment variables.

    This file intentionally does not monkey-patch Streamlit widgets. Uploaders,
    buttons, forms, text inputs, radios, and selectboxes must stay native so the
    app remains stable on mobile and desktop.
    """
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _patch_magazine_export() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_overlap_patch_applied', False):
        return

    original_fit = m._fit
    original_bullets = m._bullets

    def fit_smaller(text, width, start, minimum=16, bold=True):
        return original_fit(text, width, max(int(minimum), int(start) - 3), minimum, bold)

    def headline_font_smaller(text, width, preferred, minimum):
        text = str(text or '').upper()
        start = preferred - 10 if len(text) <= 8 else min(preferred - 8, 108)
        return original_fit(text, width, max(minimum, start), max(40, minimum - 5), True)

    def bullets_smaller(draw, x, y, items, width, color, limit, fs=20, lines=2):
        return original_bullets(draw, x, y, items, width, color, limit, max(14, fs - 2), lines)

    def metric_smaller(draw, x, y, w, label, value, color):
        w = min(w, max(52, m.PAGE_WIDTH - 20 - x))
        draw.rectangle((x, y, x + w, y + 94), fill=m.BLACK, outline=(230, 224, 204), width=1)
        draw.text((x + 7, y + 10), label, font=original_fit(label, w - 12, 16, 12, True), fill=(232, 230, 220))
        clean = m._clean(value, True)
        m._txt(draw, x + 7, y + 43, clean, original_fit(clean, w - 12, 31, 15, True), color, w - 12, 1)

    def compact_pairs(row):
        rows = [
            ('SOURCE', m._get(row, 'odds_source', 'data_source', default=m.NO_VERIFIED)),
            ('BOOK', m._get(row, 'bookmaker', 'sportsbook', default=m.NO_VERIFIED)),
            ('LINE', m._get(row, 'line_movement', 'price_movement', 'market_move', default=m.NO_VERIFIED)),
            ('PUBLIC', m._pct(m._num(row, 'public_percent', 'public_bet_percent', 'public_pct'))),
            ('PRO', m._pct(m._num(row, 'pro_percent', 'sharp_percent', 'smart_money_percent'))),
        ]
        return [(a, m._clean(b)) for a, b in rows if b != m.NO_VERIFIED][:5]

    m._fit = fit_smaller
    m._headline_font = headline_font_smaller
    m._bullets = bullets_smaller
    m._metric = metric_smaller
    m._pairs = compact_pairs
    m._aba_overlap_patch_applied = True


_patch_magazine_export()
