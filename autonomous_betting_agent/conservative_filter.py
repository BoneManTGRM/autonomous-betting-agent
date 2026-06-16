from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .row_normalizer import safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'

SPORT_SOCCER_TERMS = ('soccer', 'football', 'fifa', 'world cup', 'uefa', 'liga', 'epl', 'mls', 'champions league', 'concacaf')
SPORT_TENNIS_TERMS = ('tennis', 'atp', 'wta', 'halle', 'queen', 'stuttgart', 'berlin', 'wimbledon', 'eastbourne', 'mallorca')
SPORT_BASEBALL_TERMS = ('mlb', 'baseball', 'ncaa baseball')
SPORT_BASKETBALL_TERMS = ('nba', 'wnba', 'basketball', 'ncaab')
GRASS_TERMS = ('grass', 'halle', "queen", 'stuttgart', 'wimbledon', 'mallorca', 'eastbourne', 'nottingham', 's-hertogenbosch', 'den bosch')
CLAY_TERMS = ('clay', 'roland garros', 'french open', 'monte carlo', 'madrid open', 'rome masters')
HARD_TERMS = ('hard', 'australian open', 'us open', 'indian wells', 'miami open', 'cincinnati')


def _num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _prob(value: Any) -> float | None:
    parsed = _num(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 < parsed < 1.0 else None


def _price_to_prob(value: Any) -> float | None:
    price = _num(value)
    if price is None or price <= 1.0:
        return None
    return 1.0 / price


def _text(row: dict[str, Any], *keys: str) -> str:
    return ' '.join(safe_text(row.get(key)) for key in keys if safe_text(row.get(key))).lower()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column in frame.columns:
        return frame[column].astype(str)
    return pd.Series([''] * len(frame), index=frame.index, dtype=str)


def sport_family(row: dict[str, Any]) -> str:
    text = _text(row, 'sport', 'league', 'sport_title', 'event', 'competition', 'tournament', 'sport_key')
    if _contains(text, SPORT_SOCCER_TERMS):
        return 'soccer'
    if _contains(text, SPORT_TENNIS_TERMS):
        return 'tennis'
    if _contains(text, SPORT_BASEBALL_TERMS):
        return 'baseball'
    if _contains(text, SPORT_BASKETBALL_TERMS):
        return 'basketball'
    return 'other'


def probability_bucket(probability: float | None) -> str:
    if probability is None:
        return 'unknown'
    percent = probability * 100.0
    low = int(percent // 10 * 10)
    high = low + 10
    if low < 50:
        return '<50%'
    if low >= 80:
        return '80%+'
    return f'{low}-{high}%'


def projected_scores(row: dict[str, Any]) -> tuple[float, float] | None:
    for key in ['projected_score', 'estimated_score', 'predicted_score', 'score_projection', 'projected_final_score', 'result_note']:
        text = safe_text(row.get(key)).replace('–', '-').replace('—', '-').replace('to', '-')
        if not text:
            continue
        numbers = [float(value) for value in re.findall(r'\d+(?:\.\d+)?', text)]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
    for pair in [('projected_home_score', 'projected_away_score'), ('home_projected_score', 'away_projected_score'), ('predicted_home_score', 'predicted_away_score')]:
        left = _num(row.get(pair[0]))
        right = _num(row.get(pair[1]))
        if left is not None and right is not None:
            return left, right
    return None


def projected_margin(row: dict[str, Any]) -> float | None:
    scores = projected_scores(row)
    if scores is None:
        return None
    return abs(scores[0] - scores[1])


def projected_total(row: dict[str, Any]) -> float | None:
    scores = projected_scores(row)
    if scores is None:
        return None
    return scores[0] + scores[1]


def set_projection_risk(row: dict[str, Any]) -> str:
    text = _text(row, 'projected_score', 'estimated_score', 'predicted_score', 'score_projection', 'result_note').replace('–', '-').replace('—', '-')
    if re.search(r'\b2\s*[-:]\s*1\b', text) or re.search(r'\b1\s*[-:]\s*2\b', text) or '2 sets to 1' in text:
        return 'projected_2_1_close_match'
    if re.search(r'\b5\s*[-:]\s*4\b', text) or re.search(r'\b4\s*[-:]\s*5\b', text):
        return 'projected_5_4_one_run_game'
    if re.search(r'\b7\s*[-:]\s*6\b', text) or re.search(r'\b6\s*[-:]\s*7\b', text) or 'tiebreak' in text or 'tie-break' in text:
        return 'projected_tiebreak_margin'
    return ''


def market_type(row: dict[str, Any]) -> str:
    return safe_text(row.get('market_type') or row.get('market') or row.get('bet_type')).lower()


def edge_value(row: dict[str, Any]) -> float | None:
    edge = _num(row.get('edge_probability'))
    if edge is not None:
        return edge / 100.0 if abs(edge) > 1 else edge
    edge_percent = _num(row.get('edge_percent') or row.get('model_market_edge_percent'))
    if edge_percent is not None:
        return edge_percent / 100.0
    model = _prob(row.get('memory_adjusted_probability') or row.get('model_probability_clean') or row.get('model_probability'))
    implied = _prob(row.get('market_implied_probability'))
    if implied is None:
        price = _num(row.get('decimal_price'))
        if price and price > 1.0:
            implied = 1.0 / price
    if model is not None and implied is not None:
        return model - implied
    return None


def load_memory(path: Path = ARA_MEMORY_PATH) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _memory_rows_for(row: dict[str, Any], memory: pd.DataFrame, probability: float | None) -> pd.DataFrame:
    if memory.empty:
        return pd.DataFrame()
    sport = safe_text(row.get('sport') or row.get('sport_title') or row.get('league'))
    market = safe_text(row.get('market_type') or row.get('market'))
    bucket = probability_bucket(probability)
    area_type = _series(memory, 'area_type')
    group_value = _series(memory, 'group_value').str.lower()
    candidates: list[pd.DataFrame] = []
    if sport:
        candidates.append(memory[(area_type == 'sport') & (group_value == sport.lower())])
        candidates.append(memory[(area_type == 'sport_probability_bucket') & (group_value == f'{sport}|{bucket}'.lower())])
    if market:
        candidates.append(memory[(area_type == 'market_type') & (group_value == market.lower())])
    if sport and market:
        candidates.append(memory[(area_type == 'sport_market') & (group_value == f'{sport}|{market}'.lower())])
    candidates.append(memory[(area_type == 'probability_bucket') & (group_value == bucket.lower())])
    valid = [candidate for candidate in candidates if candidate is not None and not candidate.empty]
    out = pd.concat(valid, ignore_index=True) if valid else pd.DataFrame()
    return out.drop_duplicates() if not out.empty else out


def memory_adjustment(row: dict[str, Any], probability: float | None = None, memory: pd.DataFrame | None = None) -> dict[str, Any]:
    base = probability if probability is not None else _prob(row.get('model_probability') or row.get('model_probability_clean'))
    if base is None:
        return {'raw_model_probability': None, 'memory_adjustment': 0.0, 'memory_adjusted_probability': None, 'memory_influence_strength': 'none', 'memory_reason': 'missing_probability'}
    memory_frame = load_memory() if memory is None else memory
    matched = _memory_rows_for(row, memory_frame, base)
    if matched.empty:
        return {'raw_model_probability': round(base, 6), 'memory_adjustment': 0.0, 'memory_adjusted_probability': round(base, 6), 'memory_influence_strength': 'none', 'memory_reason': 'no_similar_memory'}
    records = pd.to_numeric(matched.get('records', pd.Series(dtype=float)), errors='coerce').fillna(0)
    edge = pd.to_numeric(matched.get('smoothed_edge', matched.get('actual_minus_predicted', pd.Series(dtype=float))), errors='coerce').fillna(0)
    reliability = pd.to_numeric(matched.get('reliability', pd.Series(dtype=float)), errors='coerce').fillna(0.25)
    weights = (records.clip(lower=1) ** 0.5) * reliability.clip(lower=0.1, upper=1.0)
    raw_adjustment = 0.0 if float(weights.sum()) == 0.0 else float((edge * weights).sum() / weights.sum())
    similar = int(records.max()) if not records.empty else 0
    if similar < 10:
        cap = 0.0
        strength = 'visible_only_small_sample'
    elif similar < 25:
        cap = 0.015
        strength = 'weak'
    elif similar < 100:
        cap = 0.03
        strength = 'medium'
    else:
        cap = 0.05
        strength = 'strong'
    adjustment = max(-cap, min(cap, raw_adjustment))
    adjusted = max(0.01, min(0.99, base + adjustment))
    direction = 'lower_trust' if raw_adjustment < -0.005 else 'raise_trust' if raw_adjustment > 0.005 else 'neutral'
    reason = f'{len(matched)} matched memory patterns; max_records={similar}; raw_adjustment={raw_adjustment:.3f}; cap={cap:.3f}; direction={direction}'
    return {'raw_model_probability': round(base, 6), 'memory_adjustment': round(adjustment, 6), 'memory_adjusted_probability': round(adjusted, 6), 'memory_influence_strength': strength, 'memory_direction': direction, 'memory_similar_patterns': int(len(matched)), 'memory_max_records': similar, 'memory_reason': reason}


def soccer_draw_probability(row: dict[str, Any], model: float | None, margin: float | None, total: float | None) -> tuple[float | None, str]:
    for key in ['draw_probability', 'model_draw_probability', 'draw_prob', 'draw_implied_probability', 'market_draw_probability']:
        value = _prob(row.get(key))
        if value is not None:
            return value, key
    for key in ['draw_decimal_price', 'draw_price', 'draw_odds']:
        value = _price_to_prob(row.get(key))
        if value is not None:
            return value, key
    if margin is None:
        if model is not None and model < 0.58:
            return 0.29, 'estimated_from_low_favorite_probability'
        return None, 'missing'
    if margin == 0:
        return 0.33, 'estimated_from_projected_draw'
    if margin <= 1.0 and total is not None and total <= 2.5:
        return 0.30, 'estimated_from_one_goal_low_total'
    if margin <= 1.0:
        return 0.27, 'estimated_from_one_goal_margin'
    if model is not None and model < 0.60:
        return 0.26, 'estimated_from_soft_favorite'
    return None, 'missing'


def tennis_surface(row: dict[str, Any]) -> str:
    text = _text(row, 'sport', 'event', 'tournament', 'surface', 'manual_context_notes')
    explicit = safe_text(row.get('surface')).lower()
    if explicit:
        text = f'{explicit} {text}'
    if _contains(text, GRASS_TERMS):
        return 'grass'
    if _contains(text, CLAY_TERMS):
        return 'clay'
    if _contains(text, HARD_TERMS):
        return 'hard'
    return 'unknown'


def tennis_volatility(row: dict[str, Any], model: float | None, edge: float | None, projection_risk: str) -> tuple[float, list[str], str]:
    surface = tennis_surface(row)
    risk = 0.0
    reasons: list[str] = []
    if surface == 'grass':
        risk += 18
        reasons.append('grass_tennis_surface_volatility')
        if model is not None and model < 0.65:
            risk += 10
            reasons.append('grass_tennis_probability_below_65_percent')
        if edge is not None and edge < 0.08:
            risk += 10
            reasons.append('grass_tennis_edge_below_8_percent')
    elif surface == 'unknown':
        risk += 6
        reasons.append('tennis_surface_missing')
    if projection_risk == 'projected_2_1_close_match':
        risk += 15
        reasons.append('tennis_projected_three_sets')
    if projection_risk == 'projected_tiebreak_margin':
        risk += 14
        reasons.append('tennis_tiebreak_projection')
    tiebreak_prob = _prob(row.get('tiebreak_probability') or row.get('projected_tiebreak_probability'))
    if tiebreak_prob is not None and tiebreak_prob >= 0.25:
        risk += 14
        reasons.append('tennis_high_tiebreak_probability')
    underdog_ace = _num(row.get('underdog_ace_rate') or row.get('opponent_ace_rate') or row.get('ace_upside_score'))
    if underdog_ace is not None and underdog_ace >= 8:
        risk += 10
        reasons.append('underdog_serve_ace_upside')
    surface_win_rate = _prob(row.get('surface_win_rate') or row.get('grass_win_rate') or row.get('favorite_surface_win_rate'))
    if surface_win_rate is not None and surface_win_rate < 0.55:
        risk += 12
        reasons.append('favorite_surface_form_below_55_percent')
    recent_minutes = _num(row.get('last_match_minutes') or row.get('recent_match_minutes'))
    recent_three_set = _num(row.get('recent_three_set_matches') or row.get('recent_3set_matches'))
    rest_days = _num(row.get('rest_days'))
    if recent_minutes is not None and recent_minutes >= 150:
        risk += 8
        reasons.append('recent_long_match_fatigue')
    if recent_three_set is not None and recent_three_set >= 2:
        risk += 8
        reasons.append('multiple_recent_three_set_matches')
    if rest_days is not None and rest_days <= 1:
        risk += 6
        reasons.append('short_rest_window')
    rank_gap = _num(row.get('ranking_gap') or row.get('rank_gap'))
    if rank_gap is not None and rank_gap >= 45 and model is not None and model < 0.65:
        risk += 8
        reasons.append('possible_ranking_name_bias')
    return min(100.0, risk), reasons, surface


def conservative_filter(row: dict[str, Any]) -> dict[str, Any]:
    family = sport_family(row)
    model = _prob(row.get('memory_adjusted_probability') or row.get('model_probability_clean') or row.get('model_probability'))
    edge = edge_value(row)
    margin = projected_margin(row)
    total = projected_total(row)
    projection_risk = set_projection_risk(row)
    market = market_type(row)
    reasons: list[str] = []
    volatility = 0.0
    draw_estimate = None
    draw_source = ''
    surface = ''
    tennis_extra = 0.0

    if edge is None:
        reasons.append('missing_edge_over_market')
        volatility += 15
    elif edge < 0.06:
        reasons.append('edge_below_6_percent')
        volatility += 18
    if model is not None and model < 0.58:
        reasons.append('model_probability_below_58_percent')
        volatility += 15
    if model is not None and edge is not None:
        price = _num(row.get('decimal_price'))
        if price is not None and price < 1.50 and model < 0.68:
            reasons.append('short_price_not_enough_probability')
            volatility += 10

    if projection_risk:
        reasons.append(projection_risk)
        volatility += 15
    if margin is not None:
        if family == 'soccer' and margin <= 1.0:
            reasons.append('soccer_one_goal_margin_draw_risk')
            volatility += 20
        elif family == 'baseball' and margin <= 1.0:
            reasons.append('baseball_one_run_margin')
            volatility += 15
        elif family == 'basketball' and margin <= 5.0:
            reasons.append('basketball_one_score_or_close_margin')
            volatility += 10
        elif family == 'tennis' and margin <= 1.0:
            reasons.append('tennis_close_sets_or_tiebreak_risk')
            volatility += 15

    if family == 'soccer' and ('h2h' in market or 'moneyline' in market or market in {'winner', '1x2', ''}):
        draw_estimate, draw_source = soccer_draw_probability(row, model, margin, total)
        if model is not None and model < 0.60:
            reasons.append('soccer_moneyline_probability_below_60_percent')
        if draw_estimate is not None and draw_estimate >= 0.25:
            reasons.append('soccer_draw_probability_above_25_percent')
        elif draw_estimate is None:
            reasons.append('soccer_draw_probability_missing')
        if total is not None and total <= 2.5 and model is not None and model < 0.65:
            reasons.append('soccer_low_total_favorite_risk')
        if margin is not None and margin <= 1.0:
            reasons.append('soccer_use_draw_no_bet_or_skip')
        volatility += 12

    if family == 'tennis':
        tennis_extra, tennis_reasons, surface = tennis_volatility(row, model, edge, projection_risk)
        reasons.extend(tennis_reasons)
        volatility += tennis_extra

    if safe_text(row.get('line_value_signal')).lower() == 'negative' or 'negative_line_movement' in safe_text(row.get('decision_reasons')).lower():
        reasons.append('line_moved_against_pick')
        volatility += 12
    if safe_text(row.get('needed_info')) or safe_text(row.get('data_quality_blockers')):
        reasons.append('missing_required_context_or_data')
        volatility += 15
    if safe_text(row.get('injury_news_risk')).lower() in {'high', 'unclear', 'unknown'}:
        reasons.append('injury_news_unclear')
        volatility += 10

    volatility = max(0.0, min(100.0, volatility))
    unique_reasons = list(dict.fromkeys(reasons))
    if not unique_reasons and edge is not None and model is not None and edge >= 0.08 and model >= 0.64 and volatility <= 15:
        tier = 'A+'
        bettable = 'yes'
        final_action = 'play_strong'
    elif not unique_reasons and edge is not None and model is not None and edge >= 0.06 and model >= 0.60 and volatility <= 25:
        tier = 'A'
        bettable = 'yes_small'
        final_action = 'play_small'
    elif volatility <= 45 and edge is not None and edge >= 0.035:
        tier = 'B'
        bettable = 'track_only'
        final_action = 'watch_only'
    else:
        tier = 'C'
        bettable = 'no'
        final_action = 'no_action'

    return {
        'volatility_score': round(volatility, 3),
        'soccer_draw_probability_estimate': None if draw_estimate is None else round(draw_estimate, 4),
        'soccer_draw_probability_source': draw_source,
        'tennis_surface': surface,
        'tennis_volatility_score': round(tennis_extra, 3),
        'draw_risk': 'high' if any('draw' in reason for reason in unique_reasons) else 'low',
        'surface_risk': 'high' if any('grass_tennis' in reason or 'surface' in reason for reason in unique_reasons) else 'low',
        'close_margin_risk': 'high' if any(term in '|'.join(unique_reasons) for term in ['margin', '2_1', '5_4', 'tiebreak']) else 'low',
        'conservative_confidence_tier': tier,
        'bettable_yes_no': bettable,
        'conservative_action': final_action,
        'reason_for_downgrade': ' | '.join(unique_reasons),
    }


def apply_conservative_filter(row: dict[str, Any]) -> dict[str, Any]:
    memory = memory_adjustment(row)
    combined = dict(row)
    combined.update(memory)
    filt = conservative_filter(combined)
    combined.update(filt)
    return {**memory, **filt}


def enrich_conservative_frame(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    data = pd.DataFrame(frame) if isinstance(frame, list) else frame
    if data is None or data.empty:
        return pd.DataFrame()
    rows = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(apply_conservative_filter(item))
        rows.append(item)
    return pd.DataFrame(rows)
