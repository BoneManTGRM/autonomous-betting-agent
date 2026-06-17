from __future__ import annotations

from typing import Any

import pandas as pd

MISS = {'', 'none', 'null', 'nan', 'n/a', 'na', 'unknown', 'missing', 'pending'}


def text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    out = str(value).strip()
    return '' if out.lower() in MISS else out


def num(value: Any) -> float | None:
    raw = text(value).replace(',', '')
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return None if pd.isna(value) else value


def price(value: Any) -> float | None:
    value = num(value)
    if value is None:
        return None
    if value >= 100:
        return round(1 + value / 100, 6)
    if value <= -100:
        return round(1 + 100 / abs(value), 6)
    return round(value, 6) if value > 1 else None


def status(row: dict[str, Any]) -> str:
    raw = text(row.get('result_status') or row.get('result') or row.get('outcome') or row.get('win_loss')).lower()
    if raw in {'won', 'win', 'w', 'correct', 'hit', 'true', 'yes', '1', '1.0', 'ganada', 'gano', 'victoria'}:
        return 'win'
    if raw in {'lost', 'loss', 'l', 'incorrect', 'miss', 'false', 'no', '0', '0.0', 'perdida', 'perdio', 'derrota'}:
        return 'loss'
    if raw in {'void', 'push', 'cancelled', 'canceled', 'postponed', 'abandoned'}:
        return 'void'
    return raw or 'pending'


def locked_price(row: dict[str, Any]) -> float | None:
    for col in ('locked_decimal_price', 'entry_decimal_price', 'entry_odds', 'decimal_price', 'best_price', 'odds', 'price'):
        value = price(row.get(col))
        if value is not None:
            return value
    return None


def close_price(row: dict[str, Any]) -> float | None:
    for col in ('closing_decimal_price', 'closing_price', 'close_decimal', 'closing_odds'):
        value = price(row.get(col))
        if value is not None:
            return value
    return None


def odds_bucket(value: Any) -> str:
    p = price(value)
    if p is None:
        return 'unknown'
    if p < 1.40:
        return '<1.40 heavy favorite'
    if p < 1.70:
        return '1.40-1.69 favorite'
    if p < 2.05:
        return '1.70-2.04 near even'
    if p < 3.00:
        return '2.05-2.99 underdog'
    return '3.00+ longshot'


def edge_bucket(value: Any) -> str:
    edge = num(value)
    if edge is None:
        return 'unknown'
    if abs(edge) > 1:
        edge /= 100
    if edge < 0:
        return '<0% negative'
    if edge < 0.03:
        return '0-3% thin'
    if edge < 0.06:
        return '3-6% usable'
    if edge < 0.10:
        return '6-10% strong'
    return '10%+ elite'


def enhance(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    rows = out.to_dict(orient='records')
    out['result_status'] = [status(r) for r in rows]
    out['locked_decimal_price'] = [locked_price(r) or '' for r in rows]
    if 'decimal_price' not in out.columns:
        out['decimal_price'] = out['locked_decimal_price']
    out['locked_bookmaker'] = [text(r.get('locked_bookmaker') or r.get('bookmaker') or r.get('odds_source')) for r in rows]
    out['locked_odds_source'] = [text(r.get('locked_odds_source') or r.get('odds_source') or r.get('source')) for r in rows]
    out['confidence_tier'] = [text(r.get('confidence_tier') or r.get('public_confidence') or r.get('confidence')) or 'unknown' for r in rows]
    out['odds_range_bucket'] = [odds_bucket(locked_price(r)) for r in rows]
    out['model_edge_bucket'] = [edge_bucket(r.get('model_edge') or r.get('model_market_edge') or r.get('edge')) for r in rows]
    flat = []
    clv = []
    beat = []
    for r in rows:
        s = status(r)
        p = locked_price(r)
        c = close_price(r)
        flat.append(0.0 if s == 'void' else -1.0 if s == 'loss' and p else round(p - 1, 4) if s == 'win' and p else '')
        if p and c and c > 1:
            value = round(p / c - 1, 6)
            clv.append(value)
            beat.append(value > 0)
        else:
            clv.append('')
            beat.append('')
    out['flat_profit_units'] = flat
    out['clv_percent'] = clv
    out['beat_close'] = beat
    if 'stake_mode' not in out.columns:
        out['stake_mode'] = 'flat_1u'
    return out


def summarize(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    out = enhance(frame)
    if out.empty:
        return {'locked_picks': 0, 'resolved_picks': 0, 'wins': 0, 'losses': 0, 'pushes': 0, 'hit_rate': None, 'profit_units': 0.0, 'roi': None, 'flat_profit_units': 0.0, 'flat_roi': None, 'resolved_with_odds': 0, 'resolved_missing_odds': 0}
    st = out['result_status'].astype(str).str.lower()
    resolved = st.isin(['win', 'loss'])
    wins = int(st.eq('win').sum())
    losses = int(st.eq('loss').sum())
    pushes = int(st.isin(['void', 'push']).sum())
    price_ok = pd.to_numeric(out['locked_decimal_price'], errors='coerce').gt(1).fillna(False)
    with_odds = resolved & price_ok
    unit_profit = pd.to_numeric(out.get('profit_units', pd.Series(index=out.index)), errors='coerce').fillna(0)
    flat_profit = pd.to_numeric(out['flat_profit_units'], errors='coerce').fillna(0)
    unit_size = pd.to_numeric(out.get('stake_units', pd.Series(index=out.index)), errors='coerce').fillna(1)
    staked = float(unit_size[resolved].sum())
    profit = float(unit_profit[resolved].sum())
    flat = float(flat_profit[with_odds].sum())
    return {'locked_picks': int(len(out)), 'resolved_picks': wins + losses, 'wins': wins, 'losses': losses, 'pushes': pushes, 'hit_rate': None if wins + losses == 0 else round(wins / (wins + losses), 6), 'total_staked_units': round(staked, 4), 'profit_units': round(profit, 4), 'roi': None if staked <= 0 else round(profit / staked, 6), 'flat_profit_units': round(flat, 4), 'flat_roi': None if int(with_odds.sum()) == 0 else round(flat / int(with_odds.sum()), 6), 'resolved_with_odds': int(with_odds.sum()), 'resolved_missing_odds': max(0, wins + losses - int(with_odds.sum()))}


def group(frame: pd.DataFrame | list[dict[str, Any]], column: str) -> pd.DataFrame:
    out = enhance(frame)
    if out.empty or column not in out.columns:
        return pd.DataFrame()
    rows = []
    for value, part in out.groupby(column, dropna=False):
        item = summarize(part)
        item[column] = text(value) or 'unknown'
        rows.append(item)
    data = pd.DataFrame(rows)
    cols = [column, 'locked_picks', 'resolved_picks', 'wins', 'losses', 'pushes', 'hit_rate', 'profit_units', 'roi', 'flat_profit_units', 'flat_roi', 'resolved_with_odds', 'resolved_missing_odds']
    return data[[c for c in cols if c in data.columns]].sort_values(['resolved_picks', 'profit_units'], ascending=False, na_position='last')


def curve(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    out = enhance(frame)
    if out.empty:
        return pd.DataFrame()
    st = out['result_status'].astype(str).str.lower()
    out = out[st.isin(['win', 'loss'])].copy()
    if out.empty:
        return out
    for col in ('locked_at_utc', 'event_start_utc'):
        if col in out.columns:
            out = out.sort_values(col, na_position='last')
            break
    out['profit_units'] = pd.to_numeric(out.get('profit_units', pd.Series(index=out.index)), errors='coerce').fillna(0)
    out['flat_profit_units'] = pd.to_numeric(out['flat_profit_units'], errors='coerce').fillna(0)
    out['cumulative_profit_units'] = out['profit_units'].cumsum().round(4)
    out['flat_cumulative_profit_units'] = out['flat_profit_units'].cumsum().round(4)
    cols = ['locked_at_utc', 'event', 'prediction', 'result_status', 'profit_units', 'cumulative_profit_units', 'flat_profit_units', 'flat_cumulative_profit_units']
    return out[[c for c in cols if c in out.columns]]
