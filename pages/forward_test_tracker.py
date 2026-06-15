from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots
from autonomous_betting_agent.proof_ledger import load_ledger
from autonomous_betting_agent.proof_readiness import build_proof_readiness_frame, proof_readiness_summary
from autonomous_betting_agent.stat_validation import statistical_summary

STAGES = [
    {'stage': 'Smoke test', 'target': 25, 'meaning': 'Confirms the pipeline works.'},
    {'stage': 'Early proof', 'target': 100, 'meaning': 'First meaningful sample.'},
    {'stage': 'Serious proof', 'target': 500, 'meaning': 'Stronger buyer conversation.'},
    {'stage': 'Strong proof', 'target': 1000, 'meaning': 'More credible valuation case.'},
]

st.set_page_config(page_title='Forward Test Tracker', layout='wide')
st.title('Forward Test Tracker')
st.caption('Tracks progress toward locked, timestamped forward-test samples.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
snapshots = build_prediction_snapshots(ledger, user_id=profile.user_id) if not ledger.empty else pd.DataFrame()
proof = build_proof_readiness_frame(snapshots)
official_rows = proof[proof['evidence_level'].eq('official_forward_proof')].copy() if not proof.empty and 'evidence_level' in proof.columns else pd.DataFrame()
summary = proof_readiness_summary(snapshots)
stats = statistical_summary(official_rows)
resolved_official = int(stats['total'])
pending_official = max(0, len(official_rows) - resolved_official)

official = int(summary['official_forward_proof'])
cols = st.columns(6)
cols[0].metric('Locked Rows', official)
cols[1].metric('Resolved Locked', resolved_official)
cols[2].metric('Pending Locked', pending_official)
cols[3].metric('Wins', stats['wins'])
cols[4].metric('Observed Hit Rate', '' if stats['observed_win_rate'] is None else f"{stats['observed_win_rate']:.1%}")
cols[5].metric('95% Low', '' if stats['wilson_low_95'] is None else f"{stats['wilson_low_95']:.1%}")

if official and resolved_official == 0:
    st.warning('Locked rows exist, but none are resolved yet.')
elif resolved_official < 25:
    st.warning('Resolved locked sample is below 25 rows. Treat it as early signal only.')

stage_rows = []
for item in STAGES:
    target = int(item['target'])
    locked_progress = min(1.0, official / target) if target else 0.0
    resolved_progress = min(1.0, resolved_official / target) if target else 0.0
    stage_rows.append({
        'stage': item['stage'],
        'target_locked_rows': target,
        'current_locked_rows': official,
        'resolved_locked_rows': resolved_official,
        'remaining_locked': max(0, target - official),
        'remaining_resolved': max(0, target - resolved_official),
        'locked_progress_percent': round(locked_progress * 100, 2),
        'resolved_progress_percent': round(resolved_progress * 100, 2),
        'status': 'complete' if official >= target else 'in_progress',
        'meaning': item['meaning'],
    })

st.subheader('Forward-test stages')
st.dataframe(pd.DataFrame(stage_rows), use_container_width=True, hide_index=True)
for row in stage_rows:
    st.progress(int(row['locked_progress_percent']), text=f"{row['stage']} locked: {row['current_locked_rows']} / {row['target_locked_rows']}")
    st.progress(int(row['resolved_progress_percent']), text=f"{row['stage']} resolved: {row['resolved_locked_rows']} / {row['target_locked_rows']}")

st.subheader('Rules')
st.write([
    'Only locked rows count toward this tracker.',
    'Resolved metrics use only locked rows with clean win/loss results.',
    'Historical fallback rows do not count here.',
    'Rows missing odds or model_probability do not count.',
    'Review-needed rows should be fixed before presentation.',
])

if not official_rows.empty:
    st.subheader('Locked rows')
    st.dataframe(official_rows.head(200), use_container_width=True, hide_index=True)
    st.download_button('Download locked rows CSV', official_rows.to_csv(index=False), file_name=f'{profile.user_id}_locked_rows.csv', mime='text/csv')
else:
    st.info('No locked rows found yet. Use Odds Lock before games start, then grade results after they finish.')
