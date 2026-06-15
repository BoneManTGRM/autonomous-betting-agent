from __future__ import annotations

from typing import Any

import pandas as pd

from .agent_decision_engine import evaluate_row
from .audit import parse_float
from .line_movement import analyze_line_row
from .row_normalizer import normalize_frame, result_status, safe_text


def autopsy_row(row: dict[str, Any]) -> dict[str, Any]:
    status = result_status(row)
    if status != 'loss':
        return {
            'autopsy_required': False,
            'loss_type': '',
            'primary_cause': '',
            'contributing_causes': '',
            'future_rule': '',
        }
    decision = evaluate_row(row)
    line = analyze_line_row(row)
    model_prob = parse_float(row.get('model_probability'))
    if model_prob is not None and model_prob > 1:
        model_prob /= 100.0
    edge = decision.get('model_market_edge')
    causes: list[str] = []

    if not safe_text(row.get('decimal_price')):
        causes.append('missing_price')
    if not safe_text(row.get('bookmaker')) or not safe_text(row.get('odds_source')):
        causes.append('missing_or_weak_source')
    if edge is None:
        causes.append('edge_unavailable')
    elif edge < 0:
        causes.append('negative_edge')
    elif edge < 0.035:
        causes.append('thin_edge')
    if model_prob is not None and model_prob >= 0.70:
        causes.append('overconfident_probability')
    if line.get('line_value_signal') == 'negative':
        causes.append('negative_closing_line_value')
    if decision.get('field_coverage_score', 0) < 0.70:
        causes.append('low_data_coverage')
    if decision.get('event_timing_status') in {'prediction_timestamp_not_before_start', 'event_already_started_without_prediction_timestamp'}:
        causes.append('bad_timing')

    if not causes:
        causes.append('acceptable_loss_or_variance')

    primary = causes[0]
    if primary in {'missing_price', 'edge_unavailable', 'missing_or_weak_source'}:
        loss_type = 'data_quality_loss'
        future_rule = 'Do not classify as playable without price, source, and edge.'
    elif primary in {'negative_edge', 'thin_edge'}:
        loss_type = 'value_error'
        future_rule = 'Raise edge threshold or downgrade similar thin-edge rows.'
    elif primary == 'overconfident_probability':
        loss_type = 'calibration_error'
        future_rule = 'Lower confidence for similar high-probability losses until segment proves itself.'
    elif primary == 'negative_closing_line_value':
        loss_type = 'market_moved_against_pick'
        future_rule = 'Require CLV review before trusting similar rows.'
    elif primary == 'bad_timing':
        loss_type = 'proof_timing_error'
        future_rule = 'Reject rows whose prediction timestamp is missing or not before event start.'
    else:
        loss_type = 'variance_or_unclassified'
        future_rule = 'Track more similar rows before changing the rule.'

    return {
        'autopsy_required': True,
        'loss_type': loss_type,
        'primary_cause': primary,
        'contributing_causes': ' | '.join(causes),
        'future_rule': future_rule,
    }


def build_loss_autopsies(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows: list[dict[str, Any]] = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(autopsy_row(row))
        if item.get('autopsy_required'):
            rows.append(item)
    return pd.DataFrame(rows)


def autopsy_summary(frame: pd.DataFrame) -> dict[str, Any]:
    autopsies = build_loss_autopsies(frame)
    if autopsies.empty:
        return {'losses_reviewed': 0, 'top_loss_type': '', 'top_primary_cause': '', 'rule_count': 0}
    return {
        'losses_reviewed': int(len(autopsies)),
        'top_loss_type': str(autopsies['loss_type'].mode().iloc[0]) if 'loss_type' in autopsies else '',
        'top_primary_cause': str(autopsies['primary_cause'].mode().iloc[0]) if 'primary_cause' in autopsies else '',
        'rule_count': int(autopsies['future_rule'].nunique()) if 'future_rule' in autopsies else 0,
    }


def future_rules(frame: pd.DataFrame) -> pd.DataFrame:
    autopsies = build_loss_autopsies(frame)
    if autopsies.empty or 'future_rule' not in autopsies.columns:
        return pd.DataFrame(columns=['future_rule', 'count'])
    return autopsies.groupby('future_rule').size().reset_index(name='count').sort_values('count', ascending=False)
