from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from autonomous_betting_agent.evidence_manifest import build_evidence_manifest, manifest_markdown
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots
from autonomous_betting_agent.proof_ledger import load_ledger
from autonomous_betting_agent.proof_readiness import build_proof_readiness_frame, proof_readiness_summary, safe_claims_for_current_state

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Proof Readiness', layout='wide')
st.title('Proof Readiness')
st.caption('Separates what is truly forward-proof from what is useful historical learning. This protects the product from overstating results.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
try:
    memory_bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {}
except Exception:
    memory_bank = {}

memory_rows = pd.DataFrame(memory_bank.get('compact_rows', [])) if isinstance(memory_bank, dict) else pd.DataFrame()
ledger_snapshots = build_prediction_snapshots(ledger, user_id=profile.user_id) if not ledger.empty else pd.DataFrame()
combined_parts = []
if not memory_rows.empty:
    combined_parts.append(memory_rows)
if not ledger_snapshots.empty:
    combined_parts.append(ledger_snapshots)
combined = pd.concat(combined_parts, ignore_index=True, sort=False) if combined_parts else pd.DataFrame()
proof = build_proof_readiness_frame(combined)
summary = proof_readiness_summary(combined)
manifest = build_evidence_manifest(memory_bank=memory_bank, ledger=ledger, snapshots=ledger_snapshots, proof_summary=summary)

cols = st.columns(6)
cols[0].metric('Proof Score', f"{summary['proof_score']}/100")
cols[1].metric('Official Forward Proof', summary['official_forward_proof'])
cols[2].metric('Historical ROI Candidates', summary['historical_roi_candidate'])
cols[3].metric('Learning Backfill', summary['learning_only_backfill'])
cols[4].metric('Result Only', summary['historical_result_only'])
cols[5].metric('Unresolved/Unusable', summary['unresolved_or_unusable'])

st.subheader('Safe claim')
st.success(summary['safe_claim'])
st.subheader('Unsafe claim warning')
st.warning(summary['unsafe_claim'])

st.subheader('Safe claims you can make now')
for claim in safe_claims_for_current_state(summary):
    st.write(f'- {claim}')

st.subheader('Proof readiness rows')
if proof.empty:
    st.info('No proof rows found yet.')
else:
    st.dataframe(proof, use_container_width=True, hide_index=True)

st.subheader('Evidence manifest')
st.json(manifest)
manifest_md = manifest_markdown(manifest)
st.download_button('Download evidence manifest JSON', json.dumps(manifest, indent=2, default=str), file_name=f'{profile.user_id}_evidence_manifest.json', mime='application/json')
st.download_button('Download evidence manifest MD', manifest_md, file_name=f'{profile.user_id}_evidence_manifest.md', mime='text/markdown')
if not proof.empty:
    st.download_button('Download proof readiness CSV', proof.to_csv(index=False), file_name=f'{profile.user_id}_proof_readiness.csv', mime='text/csv')

with st.expander('How to improve the proof score', expanded=True):
    st.write([
        'Run a forward test where every pick is locked before event start.',
        'Store model_probability and decimal_price for every official pick.',
        'Add closing odds later for CLV.',
        'Grade results automatically and separate review_needed rows.',
        'Do not count historical fallback rows as official ROI proof.',
    ])
