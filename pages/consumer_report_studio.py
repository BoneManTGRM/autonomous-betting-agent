from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.report_studio_legacy_notice import render_legacy_report_notice
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Consumer Report Studio', layout='wide')
LANG = render_app_sidebar('consumer_report_studio', language_key='consumer_report_studio_language', selector='radio')

st.title('Consumer Report Studio')
render_legacy_report_notice(LANG)
st.page_link('pages/report_studio.py', label='Open unified Report Studio')
st.caption('Consumer cards, magazine reports, copy, exports, proof status, and app feeds now live in the unified Report Studio.')
