from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.report_studio_legacy_notice import render_legacy_report_notice
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Consumer Magazine Builder', layout='wide')
LANG = render_app_sidebar('consumer_magazine_builder', language_key='consumer_magazine_builder_language', selector='radio')

st.title('Consumer Magazine Builder')
render_legacy_report_notice(LANG)
st.page_link('pages/report_studio.py', label='Open unified Report Studio')
st.caption('Magazine report building now lives in the unified Report Studio with image, PDF, app-feed, and proof exports.')
