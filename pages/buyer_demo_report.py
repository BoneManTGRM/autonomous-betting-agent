from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from autonomous_betting_agent.buyer_report import buyer_demo_markdown
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import load_ledger

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Buyer Demo Report', layout='wide')
st.title('Buyer Demo Report')
st.caption('One-click buyer-facing report for demos, investors, influencers, or potential acquirers.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
try:
    bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {}
except Exception:
    bank = {}
summary = bank.get('summary', {}) if isinstance(bank, dict) else {}
summary['training_mode'] = bank.get('training_mode', 'N/A') if isinstance(bank, dict) else 'N/A'

report = buyer_demo_markdown(ledger=ledger, memory_summary=summary)
st.markdown(report)
st.download_button('Download buyer demo report MD', report, file_name=f'{profile.user_id}_buyer_demo_report.md', mime='text/markdown')
