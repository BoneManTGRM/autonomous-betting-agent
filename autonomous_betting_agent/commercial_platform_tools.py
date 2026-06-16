from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import (
    client_view,
    daily_report,
    lock_rows,
    lock_status,
    proof_hash,
    summarize_locked_picks,
    update_profit_columns,
)
from .row_normalizer import normalize_frame, result_status, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = REPO_ROOT / 'data' / 'odds_lock_pro_ledger.csv'
PROOF_REQUIRED_COLUMNS = {'proof_id', 'locked_at_utc'}


def ensure_data_dir(path: Path = DEFAULT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def add_clv_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    cleaned = update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if cleaned.empty:
        return pd.DataFrame()
    rows = []
    for row in cleaned.to_dict(orient='records'):
        item = dict(row)
        locked_price = _safe_float(item.get('decimal_price'))
        closing_price = _safe_float(item.get('closing_decimal_price'))
        if locked_price is not None and closing_price is not None and locked_price > 1.0 and closing_price > 1.0:
            clv = (locked_price / closing_price) - 1.0
            item['clv_percent'] = round(clv, 6)
            item['beat_close'] = clv > 0
        else:
            item.setdefault('clv_percent', '')
            item.setdefault('beat_close', '')
        rows.append(item)
    return pd.DataFrame(rows)


def filter_locked_proof_rows(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    cleaned = add_clv_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if cleaned.empty or not PROOF_REQUIRED_COLUMNS.issubset(set(cleaned.columns)):
        return pd.DataFrame()
    proof = cleaned['proof_id'].map(safe_text)
    locked_at = cleaned['locked_at_utc'].map(safe_text)
    return cleaned[proof.ne('') & locked_at.ne('')].copy()


def has_locked_proof_rows(frame: pd.DataFrame | list[dict[str, Any]]) -> bool:
    return not filter_locked_proof_rows(frame).empty


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH) -> pd.DataFrame:
    try:
        if path.exists():
            return filter_locked_proof_rows(pd.read_csv(path))
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def save_persistent_ledger(frame: pd.DataFrame | list[dict[str, Any]], path: Path = DEFAULT_LEDGER_PATH) -> pd.DataFrame:
    ensure_data_dir(path)
    cleaned = filter_locked_proof_rows(frame)
    if cleaned.empty:
        return pd.DataFrame()
    cleaned.to_csv(path, index=False)
    return cleaned


def merge_ledgers(*frames: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    usable = []
    for frame in frames:
        raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
        locked = filter_locked_proof_rows(raw) if raw is not None and not raw.empty else pd.DataFrame()
        if not locked.empty:
            usable.append(locked)
    if not usable:
        return pd.DataFrame()
    merged = pd.concat(usable, ignore_index=True, sort=False)
    if 'proof_id' in merged.columns:
        proof = merged['proof_id'].map(safe_text)
        with_proof = merged[proof.ne('')].drop_duplicates(subset=['proof_id'], keep='last')
        without_proof = merged[proof.eq('')]
        merged = pd.concat([with_proof, without_proof], ignore_index=True, sort=False)
    fallback_cols = [col for col in ['event', 'prediction', 'event_start_utc', 'market_type'] if col in merged.columns]
    if fallback_cols:
        merged = merged.drop_duplicates(subset=fallback_cols, keep='last')
    return filter_locked_proof_rows(merged)


def _key_text(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def _match_key(row: Mapping[str, Any]) -> str:
    return '|'.join([
        _key_text(row.get('event')),
        _key_text(row.get('prediction')),
        _key_text(row.get('market_type')),
        _key_text(row.get('event_start_utc')),
    ])


def _result_from_row(row: Mapping[str, Any], pick: str = '') -> str:
    status = result_status(row)
    if status in {'win', 'loss', 'void'}:
        return status
    winner = _key_text(row.get('winner') or row.get('actual_winner') or row.get('final_winner'))
    if winner and pick:
        return 'win' if winner == _key_text(pick) else 'loss'
    return status if status else 'pending'


def apply_result_updates(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    result_frame = normalize_frame(pd.DataFrame(results) if isinstance(results, list) else results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': int(len(result_frame)) if result_frame is not None else 0}
    if result_frame.empty:
        return filter_locked_proof_rows(locked), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': 0}

    proof_lookup: dict[str, Mapping[str, Any]] = {}
    key_lookup: dict[str, Mapping[str, Any]] = {}
    for row in result_frame.to_dict(orient='records'):
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            proof_lookup[proof_id] = row
        key = _match_key(row)
        if key.strip('|'):
            key_lookup[key] = row

    rows = []
    updated = 0
    proof_matches = 0
    key_matches = 0
    matched_result_keys: set[str] = set()
    for row in locked.to_dict(orient='records'):
        item = dict(row)
        match = None
        proof_id = safe_text(item.get('proof_id'))
        if proof_id and proof_id in proof_lookup:
            match = proof_lookup[proof_id]
            proof_matches += 1
            matched_result_keys.add(f'proof:{proof_id}')
        else:
            key = _match_key(item)
            if key in key_lookup:
                match = key_lookup[key]
                key_matches += 1
                matched_result_keys.add(f'key:{key}')
        if match is not None:
            result = _result_from_row(match, pick=safe_text(item.get('prediction')))
            if result in {'win', 'loss', 'void'}:
                item['result_status'] = result
                item['winner'] = safe_text(match.get('winner') or match.get('actual_winner') or match.get('final_winner') or item.get('winner'))
                item['final_score'] = safe_text(match.get('final_score') or match.get('score') or item.get('final_score'))
                closing = safe_text(match.get('closing_decimal_price') or match.get('closing_price') or match.get('close_decimal') or match.get('closing_odds'))
                if closing:
                    item['closing_decimal_price'] = closing
                item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
                updated += 1
        rows.append(item)
    updated_frame = filter_locked_proof_rows(pd.DataFrame(rows))
    unmatched = max(0, len(result_frame) - len(matched_result_keys))
    return updated_frame, {'updated_rows': updated, 'matched_by_proof_id': proof_matches, 'matched_by_event_pick': key_matches, 'unmatched_results': unmatched}


def proof_audit_frame(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return pd.DataFrame(columns=['proof_id', 'hash_status', 'lock_status', 'audit_status'])
    rows = []
    for row in locked.to_dict(orient='records'):
        stored_hash = safe_text(row.get('proof_hash'))
        recomputed_hash = proof_hash(row)
        hash_status = 'hash_match' if stored_hash and stored_hash == recomputed_hash else 'hash_mismatch'
        current_lock_status = lock_status(row)
        audit_status = 'pass' if hash_status == 'hash_match' and current_lock_status == 'locked_before_start' else 'review'
        item = {
            'proof_id': safe_text(row.get('proof_id')),
            'event': safe_text(row.get('event')),
            'prediction': safe_text(row.get('prediction')),
            'locked_at_utc': safe_text(row.get('locked_at_utc')),
            'event_start_utc': safe_text(row.get('event_start_utc')),
            'hash_status': hash_status,
            'lock_status': current_lock_status,
            'audit_status': audit_status,
            'stored_hash_prefix': stored_hash[:12],
            'recomputed_hash_prefix': recomputed_hash[:12],
        }
        rows.append(item)
    return pd.DataFrame(rows)


def proof_audit_summary(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    audit = proof_audit_frame(frame)
    if audit.empty:
        return {'proof_rows': 0, 'hash_match': 0, 'hash_mismatch': 0, 'locked_before_start': 0, 'needs_review': 0, 'proof_quality_score': 0.0}
    proof_rows = int(len(audit))
    hash_match = int(audit['hash_status'].eq('hash_match').sum())
    hash_mismatch = int(audit['hash_status'].eq('hash_mismatch').sum())
    locked_before = int(audit['lock_status'].eq('locked_before_start').sum())
    needs_review = int(audit['audit_status'].eq('review').sum())
    score = 0.0
    if proof_rows:
        score += 50.0 * (hash_match / proof_rows)
        score += 35.0 * (locked_before / proof_rows)
        score += 15.0 * max(0.0, 1.0 - (needs_review / proof_rows))
    return {
        'proof_rows': proof_rows,
        'hash_match': hash_match,
        'hash_mismatch': hash_mismatch,
        'locked_before_start': locked_before,
        'needs_review': needs_review,
        'proof_quality_score': round(score, 2),
    }


def dashboard_metrics(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    cleaned = filter_locked_proof_rows(frame)
    summary = summarize_locked_picks(cleaned)
    audit = proof_audit_summary(cleaned)
    pending = 0
    avg_stake = None
    avg_clv = None
    beat_close_rate = None
    if not cleaned.empty:
        status = cleaned.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
        pending = int(status.isin(['pending', 'unknown', 'scheduled', 'live', '']).sum())
        stake = pd.to_numeric(cleaned.get('stake_units', pd.Series(dtype=float)), errors='coerce').dropna()
        avg_stake = None if stake.empty else round(float(stake.mean()), 4)
        clv = pd.to_numeric(cleaned.get('clv_percent', pd.Series(dtype=float)), errors='coerce').dropna()
        avg_clv = None if clv.empty else round(float(clv.mean()), 6)
        beat_close = cleaned.get('beat_close', pd.Series(dtype=str)).astype(str).str.lower()
        beat_mask = beat_close.isin(['true', 'false'])
        if beat_mask.any():
            beat_close_rate = round(float(beat_close[beat_mask].eq('true').mean()), 6)
    out = dict(summary)
    out.update(audit)
    out['pending_picks'] = pending
    out['avg_stake_units'] = avg_stake
    out['avg_clv_percent'] = avg_clv
    out['beat_close_rate'] = beat_close_rate
    return out


def public_dashboard_table(frame: pd.DataFrame | list[dict[str, Any]], limit: int = 200) -> pd.DataFrame:
    cleaned = filter_locked_proof_rows(frame)
    view = client_view(cleaned, public_only=True)
    if view.empty:
        return pd.DataFrame()
    sort_cols = [col for col in ['locked_at_utc', 'event_start_utc'] if col in view.columns]
    if sort_cols:
        view = view.sort_values(sort_cols, ascending=False, na_position='last')
    return view.head(limit)


def report_card_markdown(frame: pd.DataFrame | list[dict[str, Any]], *, title: str = 'Proof Dashboard', brand: str = 'Private Analytics') -> str:
    metrics = dashboard_metrics(frame)
    hit_rate = metrics.get('hit_rate')
    roi = metrics.get('roi')
    clv = metrics.get('avg_clv_percent')
    quality = metrics.get('proof_quality_score')
    lines = [
        f'# {title}',
        f'**{brand}**',
        '',
        f"Locked picks: **{metrics['locked_picks']}**",
        f"Resolved: **{metrics['resolved_picks']}**",
        f"Record: **{metrics['wins']}-{metrics['losses']}**",
        f"Hit rate: **{'N/A' if hit_rate is None else f'{hit_rate * 100:.1f}%'}**",
        f"Units: **{metrics['profit_units']}**",
        f"ROI: **{'N/A' if roi is None else f'{roi * 100:.1f}%'}**",
        f"Avg CLV: **{'N/A' if clv is None else f'{clv * 100:.2f}%'}**",
        f"Proof quality: **{quality}/100**",
        '',
        '_Research only. No guaranteed outcomes._',
    ]
    return '\n'.join(lines)


def report_card_html(frame: pd.DataFrame | list[dict[str, Any]], *, title: str = 'Proof Dashboard', brand: str = 'Private Analytics') -> str:
    metrics = dashboard_metrics(frame)
    hit_rate = metrics.get('hit_rate')
    roi = metrics.get('roi')
    clv = metrics.get('avg_clv_percent')
    quality = metrics.get('proof_quality_score')
    hit_text = 'N/A' if hit_rate is None else f'{hit_rate * 100:.1f}%'
    roi_text = 'N/A' if roi is None else f'{roi * 100:.1f}%'
    clv_text = 'N/A' if clv is None else f'{clv * 100:.2f}%'
    quality_text = 'N/A' if quality is None else f'{quality:.0f}/100'
    return f"""
<div style="font-family:Arial,sans-serif;border:1px solid #333;border-radius:18px;padding:22px;max-width:760px;background:#10141f;color:#f6f7fb;">
  <div style="font-size:14px;letter-spacing:1px;text-transform:uppercase;color:#9fb3c8;">{brand}</div>
  <div style="font-size:34px;font-weight:800;margin:6px 0 18px;">{title}</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Record</div><div style="font-size:28px;font-weight:800;">{metrics['wins']}-{metrics['losses']}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Hit Rate</div><div style="font-size:28px;font-weight:800;">{hit_text}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">ROI</div><div style="font-size:28px;font-weight:800;">{roi_text}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Units</div><div style="font-size:28px;font-weight:800;">{metrics['profit_units']}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Avg CLV</div><div style="font-size:28px;font-weight:800;">{clv_text}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Proof Quality</div><div style="font-size:28px;font-weight:800;">{quality_text}</div></div>
  </div>
  <div style="margin-top:16px;color:#9fb3c8;font-size:12px;">Research only. No guaranteed outcomes.</div>
</div>
""".strip()


def daily_locked_report(frame: pd.DataFrame | list[dict[str, Any]], *, language: str = 'English', public_only: bool = True) -> str:
    cleaned = filter_locked_proof_rows(frame)
    return daily_report(cleaned, language=language, public_only=public_only)


def demo_ledger() -> pd.DataFrame:
    rows = [
        {'event': 'Demo FC at Sample United', 'sport': 'Soccer', 'market_type': 'h2h', 'prediction': 'Sample United', 'model_probability': 0.64, 'decimal_price': 2.05, 'closing_decimal_price': 1.91, 'bookmaker': 'DemoBook', 'agent_decision': 'play_small', 'agent_score': 81, 'scanner_strength_score': 78, 'lock_ready': True, 'event_start_utc': '2099-01-01T20:00:00Z', 'result_status': 'win'},
        {'event': 'North Stars at South Kings', 'sport': 'Basketball', 'market_type': 'spread', 'prediction': 'South Kings -3.5', 'model_probability': 0.58, 'decimal_price': 1.95, 'closing_decimal_price': 1.88, 'bookmaker': 'DemoBook', 'agent_decision': 'play_small', 'agent_score': 74, 'scanner_strength_score': 84, 'lock_ready': True, 'event_start_utc': '2099-01-02T01:00:00Z', 'result_status': 'loss'},
        {'event': 'A. Player vs B. Player', 'sport': 'Tennis', 'market_type': 'h2h', 'prediction': 'A. Player', 'model_probability': 0.67, 'decimal_price': 1.82, 'closing_decimal_price': 1.70, 'bookmaker': 'DemoBook', 'agent_decision': 'play_strong', 'agent_score': 88, 'scanner_strength_score': 82, 'lock_ready': True, 'event_start_utc': '2099-01-03T18:00:00Z', 'result_status': 'pending'},
    ]
    locked = lock_rows(pd.DataFrame(rows), analyst='Demo Brand', include_watch=False)
    for idx, source in enumerate(rows):
        for key in ['result_status', 'closing_decimal_price']:
            locked.loc[idx, key] = source.get(key, '')
    return filter_locked_proof_rows(locked)
