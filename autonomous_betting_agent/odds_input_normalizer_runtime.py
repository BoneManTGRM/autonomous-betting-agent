from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

import pandas as pd

CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    'event': ('event', 'event_name', 'game', 'match', 'fixture', 'partido'),
    'prediction': ('prediction', 'pick', 'selection', 'predicted_winner', 'predicted_side', 'favorite', 'pronostico', 'seleccion'),
    'sport': ('sport', 'sport_title', 'league', 'competition', 'deporte', 'liga'),
    'market_type': ('market_type', 'market', 'bet_type', 'tipo_mercado', 'mercado'),
    'model_probability': ('model_probability', 'final_probability_value', 'final_probability', 'calibrated_probability', 'predicted_probability', 'win_probability', 'pick_probability', 'true_probability', 'ai_probability', 'probability', 'probabilidad_modelo'),
    'market_probability': ('market_probability', 'market_probability_value', 'book_probability', 'sportsbook_probability', 'market_implied_probability', 'probabilidad_mercado'),
    'best_price': ('best_price', 'best_odds', 'decimal_price', 'decimal_odds', 'odds_decimal', 'american_odds', 'american_price', 'moneyline', 'price', 'odds', 'market_price', 'book_price', 'bookmaker_price', 'avg_price', 'average_price', 'current_odds', 'opening_odds', 'closing_odds', 'cuota', 'cuotas', 'mejor_cuota'),
    'confidence': ('confidence', 'confianza', 'read', 'classification', 'grade', 'tier'),
    'books': ('books', 'bookmakers', 'bookmaker_count', 'source_count', 'casas'),
    'api_coverage_score': ('api_coverage_score', 'api_coverage', 'coverage', 'puntaje_cobertura_api'),
    'computed_ev_decimal': ('computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev_value', 'ev', 'edge', 'value', 'expected_value'),
}

IMPLIED_PROBABILITY_ALIASES = (
    'implied_probability',
    'implied_probability_from_price',
    'break_even_win_rate',
    'breakeven_probability',
    'book_implied_probability',
    'price_implied_probability',
)

MISSING_TEXT = {'', 'nan', 'none', 'null', 'unknown', 'missing', 'n/a', 'na'}


def clean_key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii')
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return re.sub(r'_+', '_', text).strip('_')


def parse_probability(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '')
    if not text or text.lower() in MISSING_TEXT:
        return None
    is_percent = text.endswith('%')
    if is_percent:
        text = text[:-1].strip()
    try:
        number = float(text)
    except ValueError:
        return None
    if is_percent or 1.0 < number <= 100.0:
        number /= 100.0
    return number if 0.0 < number < 1.0 else None


def parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '')
    if not text or text.lower() in MISSING_TEXT:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number >= 100:
        return round(1.0 + number / 100.0, 6)
    if number <= -100:
        return round(1.0 + 100.0 / abs(number), 6)
    if number > 1.0:
        return round(number, 6)
    return None


def _lookup(frame: pd.DataFrame) -> dict[str, str]:
    return {clean_key(col): str(col) for col in frame.columns}


def _find_column(frame: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    lookup = _lookup(frame)
    keys = [clean_key(alias) for alias in aliases]
    for key in keys:
        if key in lookup:
            return lookup[key]
    compact_lookup = {key.replace('_', ''): col for key, col in lookup.items()}
    for key in keys:
        compact = key.replace('_', '')
        if compact in compact_lookup:
            return compact_lookup[compact]
    return None


def _clean_text(series: pd.Series) -> pd.Series:
    values = series.astype('object').where(pd.notna(series), '')
    return values.astype(str).str.strip()


def _series_has_values(series: pd.Series) -> bool:
    values = _clean_text(series).str.lower().replace({'nan': '', 'none': '', 'missing': '', 'unknown': ''})
    return bool(values.astype(bool).any())


def _missing_mask(series: pd.Series) -> pd.Series:
    return _clean_text(series).str.lower().isin(MISSING_TEXT)


def _copy_if_missing(frame: pd.DataFrame, target: str, aliases: Iterable[str]) -> None:
    if target in frame.columns and _series_has_values(frame[target]):
        return
    source = _find_column(frame, aliases)
    if source is not None:
        frame[target] = frame[source]


def _normalize_best_price(frame: pd.DataFrame) -> None:
    if 'best_price' not in frame.columns:
        return
    frame['best_price'] = frame['best_price'].map(lambda value: pd.NA if parse_price(value) is None else parse_price(value)).astype('Float64')
    if 'decimal_price' not in frame.columns:
        frame['decimal_price'] = frame['best_price']
    else:
        mask = _missing_mask(frame['decimal_price'])
        if bool(mask.any()):
            frame.loc[mask, 'decimal_price'] = frame.loc[mask, 'best_price']


def _derive_price_from_implied_probability(frame: pd.DataFrame) -> None:
    source = _find_column(frame, IMPLIED_PROBABILITY_ALIASES)
    if source is None:
        return

    def convert(value: Any):
        probability = parse_probability(value)
        return pd.NA if probability is None else round(1.0 / probability, 4)

    derived = frame[source].map(convert).astype('Float64')
    if 'best_price' not in frame.columns:
        frame['best_price'] = derived
    else:
        mask = _missing_mask(frame['best_price'])
        if bool(mask.any()):
            frame.loc[mask, 'best_price'] = derived.loc[mask]
    if 'decimal_price' not in frame.columns:
        frame['decimal_price'] = frame['best_price']
    else:
        mask = _missing_mask(frame['decimal_price'])
        if bool(mask.any()):
            frame.loc[mask, 'decimal_price'] = frame.loc[mask, 'best_price']


def normalize_odds_input(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    for target, aliases in CANONICAL_ALIASES.items():
        _copy_if_missing(out, target, aliases)
    _normalize_best_price(out)
    _derive_price_from_implied_probability(out)
    return out


def install_odds_breakdown_normalizer() -> None:
    try:
        from .roi_ui_patch import install_roi_metric_patch
        install_roi_metric_patch()
    except Exception:
        pass
    try:
        from . import odds_breakdown
    except Exception:
        return
    if getattr(odds_breakdown, '_input_normalizer_installed', False):
        return
    original = odds_breakdown.build_odds_breakdown

    def normalized_build_odds_breakdown(frame: pd.DataFrame):
        return original(normalize_odds_input(frame))

    odds_breakdown.build_odds_breakdown = normalized_build_odds_breakdown
    odds_breakdown._input_normalizer_installed = True
