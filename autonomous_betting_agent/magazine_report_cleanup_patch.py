from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

_PATCH_VERSION = 'magazine_report_cleanup_guardrails_v1'

BAD_CONTEXT_TOKENS = (
    'api-mma',
    'api mma',
    'matching fight',
    'fighter data',
    'fight returned',
    'fight news',
    'weight cut',
    'camp updates',
    'no provider event id',
    'sdio checked',
    'no fixture match',
    'no match returned',
    'simple news aggregator',
    'show hn',
    'uploaded/cached row',
    'fila cargada/en caché',
    'not returned for this event',
    'data not returned',
    'player data not returned',
)

COMPLETED_GAME_WORDS = (
    ' defeated ',
    ' beat ',
    ' won ',
    ' lost ',
    ' confirming ',
    ' confirmed ',
)

MOJIBAKE_REPLACEMENTS = {
    'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú', 'Ã±': 'ñ',
    'ÃÁ': 'Á', 'Ã‰': 'É', 'Ã‘': 'Ñ', 'Ã¼': 'ü', 'Ã': '', 'Â': '',
    'â€™': "'", 'â€œ': '"', 'â€�': '"', 'â€“': '-', 'â€”': '-', 'â€¦': '…',
    '�': '', '\uFFFD': '',
}


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, 'to_dict'):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, '__dict__', {}) or {})


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    for old, new in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _sport_kind(row: Mapping[str, Any]) -> str:
    text = ' '.join(str(row.get(k, '')) for k in ('sport', 'league', 'event', 'event_name', 'matchup')).lower()
    if any(token in text for token in ('mma', 'ufc', 'boxing', 'fighter')):
        return 'combat'
    if any(token in text for token in ('soccer', 'fifa', 'football', 'world cup', 'uefa', 'liga')):
        return 'soccer'
    if any(token in text for token in ('mlb', 'baseball')):
        return 'baseball'
    return 'generic'


def _is_resolved(row: Mapping[str, Any]) -> bool:
    status = str(row.get('result_status') or row.get('verified_grade') or row.get('grade') or '').strip().lower()
    return status in {'win', 'loss', 'void', 'push', 'final', 'graded'} or bool(str(row.get('final_score') or '').strip() and str(row.get('graded_at_utc') or '').strip())


def _bad_context(text: Any, row: Mapping[str, Any]) -> bool:
    cleaned = _safe_text(text)
    if not cleaned:
        return True
    lowered = cleaned.lower()
    kind = _sport_kind(row)
    if kind != 'combat' and any(token in lowered for token in ('api-mma', 'api mma', 'matching fight', 'fighter data', 'weight cut', 'camp updates')):
        return True
    if any(token in lowered for token in BAD_CONTEXT_TOKENS):
        return True
    if not _is_resolved(row) and any(token in lowered for token in COMPLETED_GAME_WORDS):
        return True
    return False


def _split_sentences(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    raw = re.split(r'(?:\n|•|;|\s+-\s+|(?<=[.!?])\s+)', text)
    return [_safe_text(part).strip(' .•-') for part in raw if _safe_text(part).strip(' .•-')]


def _shorten(text: str, max_chars: int = 92) -> str:
    text = _safe_text(text)
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(' ', 1)[0].strip()
    return (cut or text[: max_chars - 1]).rstrip('.,;:') + '…'


def _clean_items(row: Mapping[str, Any], values: Iterable[Any], *, limit: int = 3, max_chars: int = 92) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for sentence in _split_sentences(value):
            if _bad_context(sentence, row):
                continue
            item = _shorten(sentence, max_chars=max_chars)
            key = item.lower()
            if key and key not in seen:
                out.append(item)
                seen.add(key)
            if len(out) >= limit:
                return out
    return out


def _number(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or str(value).strip().lower() in {'', 'nan', 'none', 'null', 'n/a'}:
            continue
        try:
            return float(str(value).replace('%', '').replace(',', ''))
        except Exception:
            continue
    return None


def build_matchup_items(row_like: Any) -> list[str]:
    row = _row(row_like)
    values = [
        row.get('perplexity_context'),
        row.get('perplexity_summary'),
        row.get('newsapi_summary'),
        row.get('news_summary'),
        row.get('weather_summary'),
        row.get('sports_context_summary'),
        row.get('preview_summary'),
        row.get('game_summary'),
        row.get('short_reason'),
        row.get('matchup_notes'),
        row.get('matchup_note'),
    ]
    items = _clean_items(row, values, limit=3, max_chars=82)
    odds_status = str(row.get('odds_status') or row.get('odds_source') or '').strip().upper()
    if odds_status and odds_status != 'LIVE' and not any('odds' in item.lower() for item in items):
        items.insert(0, 'Odds are not live; verify the current price before betting.')
    if not items:
        items = ['Live context was not returned; verify odds, lineup, and news before entry.']
    return items[:3]


def sanitize_row(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    for key, value in list(row.items()):
        if isinstance(value, str):
            row[key] = _safe_text(value)

    matchup_items = build_matchup_items(row)
    row['matchup_notes'] = '\n'.join(matchup_items)
    row['sports_context_summary'] = row.get('sports_context_summary') if not _bad_context(row.get('sports_context_summary'), row) else matchup_items[-1]
    row['preview_summary'] = row.get('preview_summary') if not _bad_context(row.get('preview_summary'), row) else matchup_items[-1]
    row['game_summary'] = row.get('game_summary') if not _bad_context(row.get('game_summary'), row) else matchup_items[-1]
    row['short_reason'] = row.get('short_reason') if not _bad_context(row.get('short_reason'), row) else matchup_items[-1]

    odds_status = str(row.get('odds_status') or '').strip().upper()
    ev = _number(row, 'expected_value_per_unit', 'EV', 'ev', 'expected_value')
    if odds_status != 'LIVE':
        row['risk'] = 'FALLBACK'
        row['risk_level'] = 'FALLBACK'
        row['risk_label'] = 'FALLBACK MODE'
        row['why_lose'] = 'Fallback data used.\nVerify live odds before betting.\nDo not play until the price is confirmed.'
        row['risk_notes'] = row['why_lose']
    elif ev is not None and ev < 0:
        row['risk'] = 'NEG EV'
        row['risk_level'] = 'NEG EV'
        row['risk_label'] = 'NEGATIVE EV'
        row['why_lose'] = 'Negative edge at current price.\nDo not play unless price improves.\nRecheck odds and key news.'
        row['risk_notes'] = row['why_lose']

    if ev is not None and ev < 0:
        row['chain_notes'] = 'No parlay recommended.\nNot enough compatible selections.\nVerified odds or edge are not positive.'
        row['final_decision'] = row.get('final_decision') or 'WATCHLIST'
    if odds_status != 'LIVE':
        row['final_decision'] = 'WATCHLIST'
    return row


def install_live_cleanup() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    if getattr(live, '_ABA_REPORT_CLEANUP_VERSION', '') == _PATCH_VERSION:
        return
    original_one = live.enrich_row_with_live_api_data
    original_many = live.enrich_rows_with_live_api_data

    def enrich_one(row_like: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return sanitize_row(original_one(row_like, *args, **kwargs))

    def enrich_many(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
        return [sanitize_row(row) for row in original_many(rows)]

    live.enrich_row_with_live_api_data = enrich_one
    live.enrich_rows_with_live_api_data = enrich_many
    live._ABA_REPORT_CLEANUP_VERSION = _PATCH_VERSION


def install_renderer_cleanup(module: Any | None = None) -> Any | None:
    if module is None:
        try:
            from autonomous_betting_agent import magazine_book_export as module
        except Exception:
            return None
    if getattr(module, '_ABA_REPORT_CLEANUP_VERSION', '') == _PATCH_VERSION:
        return module

    module._matchup_items = lambda row: build_matchup_items(row)

    original_metric_cells = getattr(module, 'magazine_metric_cells', None)
    if callable(original_metric_cells):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            cells = list(original_metric_cells(odds, conf, edge, ev, units, risk))
            fixed = []
            risk_text = str(risk or '').upper()
            danger = getattr(module, 'DANGER', (225, 67, 62))
            green = getattr(module, 'GREEN', (61, 205, 84))
            cream = getattr(module, 'CREAM', (255, 248, 230))
            for label, value, color, x, width in cells:
                if str(label).upper() == 'RISK':
                    if any(token in risk_text for token in ('LIVE', 'VOLUME OK', 'SAFE')):
                        color = green
                    elif any(token in risk_text for token in ('FALLBACK', 'NEG', 'MISSING', 'WATCH', 'NO')):
                        color = danger
                    else:
                        color = cream
                fixed.append((label, value, color, x, width))
            return fixed
        module.magazine_metric_cells = metric_cells

    original_render = getattr(module, 'render_full_pick_magazine_page', None)
    if callable(original_render):
        def render(row_like: Any, *args: Any, **kwargs: Any):
            return original_render(sanitize_row(row_like), *args, **kwargs)
        module.render_full_pick_magazine_page = render

    module._ABA_REPORT_CLEANUP_VERSION = _PATCH_VERSION
    return module


def install() -> None:
    install_live_cleanup()
    install_renderer_cleanup()


install()
