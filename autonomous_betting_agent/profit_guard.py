from __future__ import annotations

import pandas as pd


def _num(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype='float64')
    return pd.to_numeric(frame[col], errors='coerce').fillna(default)


def add_profit_guard(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    prob = _num(out, 'learned_model_probability', 0.0)
    fallback_prob = _num(out, 'model_probability_clean', 0.0)
    prob = prob.where(prob.gt(0), fallback_prob).where(lambda s: s <= 1.0, lambda s: s / 100.0).clip(0, 1)
    odds = _num(out, 'decimal_price', 0.0)
    odds = odds.where(odds.gt(0), _num(out, 'odds_at_pick', 0.0)).where(lambda s: s.gt(0), _num(out, 'best_price', 0.0))
    implied = _num(out, 'market_implied_probability', 0.0).where(lambda s: s.gt(0), 1 / odds.where(odds.gt(1)))
    edge = _num(out, 'model_market_edge', 0.0).where(lambda s: s.ne(0), prob - implied.fillna(0.0))
    ev = (prob * odds.where(odds.gt(1), 0.0) - 1.0).fillna(-1.0)
    audit_ok = pd.Series(True, index=out.index)
    if 'odds_audit_status' in out.columns:
        audit_ok = out['odds_audit_status'].astype(str).str.lower().isin({'', 'pass', 'ok', 'nan'})
    status = pd.Series('research_only', index=out.index, dtype='object')
    status.loc[(~audit_ok) | odds.le(1.05) | odds.gt(5.00)] = 'reject_price_safety'
    status.loc[odds.lt(1.18) & edge.lt(0.02) & status.ne('reject_price_safety')] = 'reject_overpriced_favorite'
    status.loc[odds.lt(1.35) & edge.lt(-0.01) & status.eq('research_only')] = 'thin_edge_favorite'
    status.loc[(ev.ge(0.015) | edge.ge(0.015)) & status.eq('research_only')] = 'value_ok'
    status.loc[prob.ge(0.60) & odds.between(1.25, 2.75, inclusive='both') & edge.ge(-0.025) & status.eq('research_only')] = 'volume_ok'
    status.loc[prob.ge(0.66) & odds.le(1.55) & edge.ge(-0.035) & status.eq('research_only')] = 'safe_accuracy_only'
    base = _num(out, 'pattern_points', 0.0).where(_num(out, 'pattern_points', 0.0).gt(0), _num(out, 'agent_score', 0.0))
    odds_score = odds.between(1.25, 1.89, inclusive='both').astype(float) * 8.0 + odds.between(1.90, 2.75, inclusive='both').astype(float) * 4.0 - odds.lt(1.18).astype(float) * 14.0 - odds.gt(3.50).astype(float) * 10.0
    score = (base * 0.58 + prob * 18.0 + ev.clip(-0.10, 0.14) * 120.0 + edge.clip(-0.08, 0.12) * 80.0 + odds_score).clip(0, 100).round(3)
    out['profit_expected_value'] = ev.round(6)
    out['profit_edge_proxy'] = edge.round(6)
    out['profit_guard_status'] = status
    out['profit_protection_score'] = score
    out['profit_volume_safe'] = ~status.isin({'reject_price_safety', 'reject_overpriced_favorite'})
    out['profit_balanced_ok'] = status.isin({'value_ok', 'volume_ok', 'safe_accuracy_only'}) | (score.ge(62) & edge.ge(-0.025) & odds.between(1.18, 3.50, inclusive='both'))
    out['profit_official_ok'] = status.isin({'value_ok', 'volume_ok'}) & odds.between(1.18, 3.25, inclusive='both') & (ev.ge(-0.015) | edge.ge(-0.015))
    out['profit_elite_ok'] = status.eq('value_ok') & odds.between(1.25, 2.75, inclusive='both') & (ev.ge(0.005) | edge.ge(0.005))
    lane = pd.Series('research_volume', index=out.index, dtype='object')
    lane.loc[out['profit_balanced_ok'].astype(bool)] = 'balanced_roi'
    lane.loc[out['profit_official_ok'].astype(bool)] = 'official_candidate'
    lane.loc[out['profit_elite_ok'].astype(bool)] = 'elite_candidate'
    lane.loc[~out['profit_volume_safe'].astype(bool)] = 'blocked_price'
    out['profit_lane'] = lane
    stake = pd.Series(0.05, index=out.index, dtype='float64')
    stake.loc[lane.eq('balanced_roi')] = 0.10
    stake.loc[lane.eq('official_candidate')] = 0.15
    stake.loc[lane.eq('elite_candidate')] = 0.20
    stake.loc[lane.eq('blocked_price')] = 0.0
    out['suggested_stake_units'] = stake
    event_key = out.get('event_id', out.get('event', pd.Series('', index=out.index))).astype(str)
    market_key = out.get('market_type', pd.Series('', index=out.index)).astype(str)
    portfolio_key = event_key + '|' + market_key
    tmp = pd.DataFrame({'key': portfolio_key, 'score': score, 'idx': range(len(out))}).sort_values(['key', 'score'], ascending=[True, False])
    tmp['rank'] = tmp.groupby('key').cumcount() + 1
    group_rank = tmp.sort_values('idx')['rank'].reset_index(drop=True).astype(int)
    out['portfolio_group_rank'] = group_rank.values
    penalty = (out['portfolio_group_rank'].clip(lower=1) - 1) * 6.0
    out['portfolio_priority_score'] = (score - penalty).clip(0, 100).round(3)
    return out


def filter_profit_guard(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    if 'profit_guard_status' not in frame.columns:
        frame = add_profit_guard(frame)
    text = str(mode or '').lower()
    if text.startswith('research'):
        return frame
    if text.startswith('volume'):
        return frame[frame.get('profit_volume_safe', pd.Series(True, index=frame.index)).astype(bool)]
    if text.startswith('balanced'):
        return frame[frame.get('profit_balanced_ok', pd.Series(True, index=frame.index)).astype(bool)]
    if text.startswith('official'):
        return frame[frame.get('profit_official_ok', pd.Series(True, index=frame.index)).astype(bool)]
    if text.startswith('elite'):
        return frame[frame.get('profit_elite_ok', pd.Series(True, index=frame.index)).astype(bool)]
    return frame
