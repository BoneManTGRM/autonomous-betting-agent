from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_float(value: Any) -> float | None:
    text = str(value or '').strip().replace('%', '').replace(',', '')
    if not text or text.lower() in {'nan', 'none', 'null', 'n/a'}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _numeric(frame: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[name], errors='coerce').fillna(default).astype(float)


def _clip01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').fillna(0.0).clip(0.0, 1.0)


def _text_blob(row: dict[str, Any]) -> str:
    keys = [
        'news', 'news_headline', 'news_headlines', 'headline', 'headlines', 'team_news',
        'injury_news', 'lineup_news', 'weather_reason', 'fusion_warning', 'public_reason',
        'lock_blockers', 'notes', 'reason', 'motivo', 'revisar',
    ]
    parts = [str(row.get(key, '') or '') for key in keys]
    return ' '.join(parts).lower()


def news_risk_from_text(text: str) -> tuple[float, str]:
    tokens = {
        'major_injury': ['out for season', 'ruled out', 'inactive', 'doubtful', 'injured reserve', 'key injury', 'star out'],
        'lineup_rotation': ['resting starters', 'rotation', 'bench', 'limited minutes', 'minutes restriction', 'lineup change'],
        'discipline': ['suspended', 'arrest', 'investigation', 'disciplinary', 'ban'],
        'weather': ['storm', 'heavy rain', 'wind advisory', 'snow', 'delay', 'postponed', 'wet field'],
        'travel': ['travel delay', 'short rest', 'back to back', 'altitude', 'high altitude', 'jet lag'],
        'market': ['sharp money against', 'line moved against', 'steam against', 'odds drift', 'negative clv'],
    }
    matched: list[str] = []
    score = 0.0
    for label, words in tokens.items():
        if any(word in text for word in words):
            matched.append(label)
            score += 0.18 if label != 'major_injury' else 0.28
    return round(min(score, 1.0), 6), ';'.join(matched)


def add_pattern_swarm_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add lightweight specialist-agent risk/consensus fields for Simulation Lab.

    This is not an LLM swarm. It is a deterministic pattern swarm: multiple small
    specialist checks produce weather, injury, travel, market, data, memory, and
    news scores that can be audited row by row.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    weather = _clip01(_numeric(out, 'weather_risk'))
    injury = _clip01(_numeric(out, 'injury_risk'))
    altitude = _clip01(_numeric(out, 'altitude_risk'))
    travel = _clip01(_numeric(out, 'travel_risk'))
    line = _clip01(_numeric(out, 'line_movement_risk'))
    price = _clip01(_numeric(out, 'price_risk'))
    data = _clip01(_numeric(out, 'data_quality_risk'))
    memory = pd.to_numeric(out.get('memory_signal', pd.Series(0.0, index=out.index)), errors='coerce').fillna(0.0)

    news_scores = []
    news_flags = []
    for row in out.to_dict(orient='records'):
        score, flags = news_risk_from_text(_text_blob(row))
        news_scores.append(score)
        news_flags.append(flags)
    news = pd.Series(news_scores, index=out.index, dtype=float).clip(0.0, 1.0)

    out['swarm_weather_agent_score'] = (100.0 * (1.0 - weather)).round(2)
    out['swarm_injury_agent_score'] = (100.0 * (1.0 - injury)).round(2)
    out['swarm_travel_altitude_agent_score'] = (100.0 * (1.0 - pd.concat([altitude, travel], axis=1).max(axis=1))).round(2)
    out['swarm_market_agent_score'] = (100.0 * (1.0 - pd.concat([line, price], axis=1).max(axis=1))).round(2)
    out['swarm_data_agent_score'] = (100.0 * (1.0 - data)).round(2)
    out['swarm_memory_agent_score'] = (100.0 * (0.5 + memory.clip(-0.10, 0.10) * 5.0)).clip(0.0, 100.0).round(2)
    out['swarm_news_agent_score'] = (100.0 * (1.0 - news)).round(2)
    out['news_risk'] = news.round(6)
    out['news_risk_flags'] = news_flags

    score_cols = [
        'swarm_weather_agent_score', 'swarm_injury_agent_score', 'swarm_travel_altitude_agent_score',
        'swarm_market_agent_score', 'swarm_data_agent_score', 'swarm_memory_agent_score', 'swarm_news_agent_score',
    ]
    out['swarm_consensus_score'] = out[score_cols].mean(axis=1).round(2)
    out['swarm_min_agent_score'] = out[score_cols].min(axis=1).round(2)

    flags: list[str] = []
    for row in out.to_dict(orient='records'):
        row_flags = []
        if _safe_float(row.get('swarm_weather_agent_score')) is not None and float(row.get('swarm_weather_agent_score')) < 65:
            row_flags.append('weather')
        if _safe_float(row.get('swarm_injury_agent_score')) is not None and float(row.get('swarm_injury_agent_score')) < 65:
            row_flags.append('injury')
        if _safe_float(row.get('swarm_travel_altitude_agent_score')) is not None and float(row.get('swarm_travel_altitude_agent_score')) < 65:
            row_flags.append('travel_altitude')
        if _safe_float(row.get('swarm_market_agent_score')) is not None and float(row.get('swarm_market_agent_score')) < 65:
            row_flags.append('market_reversal')
        if _safe_float(row.get('swarm_data_agent_score')) is not None and float(row.get('swarm_data_agent_score')) < 65:
            row_flags.append('data_quality')
        if _safe_float(row.get('swarm_news_agent_score')) is not None and float(row.get('swarm_news_agent_score')) < 65:
            row_flags.append('news')
        flags.append(';'.join(row_flags))
    out['swarm_red_flags'] = flags
    out['swarm_recommendation'] = 'watch'
    out.loc[(out['swarm_consensus_score'] >= 80) & (out['swarm_min_agent_score'] >= 55), 'swarm_recommendation'] = 'lock_candidate_after_simulation'
    out.loc[(out['swarm_consensus_score'] < 65) | (out['swarm_min_agent_score'] < 35), 'swarm_recommendation'] = 'avoid_or_manual_review'
    return out


def swarm_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or 'swarm_recommendation' not in frame.columns:
        return pd.DataFrame()
    grouped = frame.groupby('swarm_recommendation', dropna=False).agg(
        rows=('swarm_recommendation', 'size'),
        avg_consensus=('swarm_consensus_score', 'mean'),
        avg_min_agent=('swarm_min_agent_score', 'mean'),
        avg_news_risk=('news_risk', 'mean'),
    ).reset_index()
    for col in ['avg_consensus', 'avg_min_agent', 'avg_news_risk']:
        grouped[col] = grouped[col].round(4)
    return grouped.sort_values(['avg_consensus', 'rows'], ascending=[False, False]).reset_index(drop=True)
