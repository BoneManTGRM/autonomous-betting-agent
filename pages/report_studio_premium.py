from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.pdf_report import render_report_pdf
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_product_layer import MagazineBrand, cards_to_json, enrich_rows, grouped_report, render_consumer_magazine_html, render_markdown_summary, safe_text
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.sports_context import CONTEXT_UNAVAILABLE, enrich_sports_context
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

st.set_page_config(page_title='Report Studio', layout='wide')
LANG = render_app_sidebar('report_studio_premium', language_key='report_studio_language', selector='radio')

TEXT = {
    'en': {'title':'Report Studio','caption':'Premium cards, magazine reports, WhatsApp copy, proof tables, PDFs, and app feeds.','input':'Input rows','workspace':'Client / Workspace ID','use_saved':'Use saved workspace rows','upload':'Upload CSV rows','source':'Source','empty':'No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.','profile':'White-label profile','profile_id':'Profile ID','profile_key':'Profile key','load_profile':'Load profile','save_profile':'Save profile','brand_name':'Brand / tipster name','tagline':'Tagline','report_title':'Report title','logo_url':'Logo URL','disclaimer':'Disclaimer','mode':'Report mode','risk':'Risk preference','sports':'Sports','max_rows':'Max rows','visibility':'Feed visibility','cards':'Premium Cards','magazine':'Magazine Report','copy':'WhatsApp / Telegram','proof':'Analyst Proof','exports':'Exports','profile_json':'Profile JSON','feed_json':'Saved app feed','pdf':'Download PDF','html':'Download HTML','md':'Download Markdown','json':'Download JSON','csv':'Download CSV','copy_download':'Download WhatsApp copy','feed_saved':'Latest app feed saved.','context_note':'Sports context is added only when fields or configured JSON context are available. Missing context is labeled unavailable.','copy_label':'Short copy'},
    'es': {'title':'Estudio de Reportes','caption':'Tarjetas premium, reporte revista, copy WhatsApp, prueba técnica, PDFs y feed para app.','input':'Filas de entrada','workspace':'ID de cliente / workspace','use_saved':'Usar filas guardadas','upload':'Subir CSV','source':'Fuente','empty':'No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.','profile':'Perfil white-label','profile_id':'ID del perfil','profile_key':'Clave del perfil','load_profile':'Cargar perfil','save_profile':'Guardar perfil','brand_name':'Marca / tipster','tagline':'Lema','report_title':'Título del reporte','logo_url':'URL del logo','disclaimer':'Aviso legal','mode':'Modo de reporte','risk':'Preferencia de riesgo','sports':'Deportes','max_rows':'Máximo de filas','visibility':'Visibilidad del feed','cards':'Tarjetas premium','magazine':'Reporte revista','copy':'WhatsApp / Telegram','proof':'Prueba técnica','exports':'Exportaciones','profile_json':'JSON del perfil','feed_json':'Feed de app guardado','pdf':'Descargar PDF','html':'Descargar HTML','md':'Descargar Markdown','json':'Descargar JSON','csv':'Descargar CSV','copy_download':'Descargar copy WhatsApp','feed_saved':'Feed de app actualizado guardado.','context_note':'El contexto deportivo solo se agrega cuando existen campos o JSON configurado. Si falta, se marca como no disponible.','copy_label':'Copy corto'},
}
HANDOFF_KEYS = ('odds_lock_pro_locked_rows','public_proof_dashboard_refresh_rows','pro_predictor_high_confidence_rows','pro_predictor_latest_rows','what_are_the_odds_latest_rows','ara_latest_predictions')


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, key)


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return 'persistent_proof_ledger', persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return f'session:{key}', pd.DataFrame(rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    return (f'saved:{key}', pd.DataFrame(rows)) if rows else ('', pd.DataFrame())


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames, names = [], []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame['source_file'] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f'{upload.name}: {exc}')
    return (', '.join(names), pd.concat(frames, ignore_index=True, sort=False)) if frames else ('', pd.DataFrame())


def sport_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or 'sport' not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame['sport'].tolist() if safe_text(value)})


def whatsapp_copy(cards: pd.DataFrame, brand: MagazineBrand, max_items: int = 8) -> str:
    es = LANG == 'es'
    groups = grouped_report(cards)
    lines = [brand.report_title, f'{brand.brand_name} — {brand.tagline}', '']
    section_names = [('best_plays','Jugadas aprobadas' if es else 'Approved'),('watchlist','Seguimiento' if es else 'Watchlist'),('no_play','Investigación / no aprobado' if es else 'Research / Not Approved')]
    for key, label in section_names:
        section = groups.get(key, pd.DataFrame())
        lines.append(label)
        if section.empty:
            lines.append('— ' + ('Sin tarjetas.' if es else 'No cards.'))
        for _, row in section.head(max_items).iterrows():
            rowd = row.to_dict()
            event = safe_text(rowd.get('event')) or 'Matchup'
            pick = safe_text(rowd.get('public_pick') or rowd.get('prediction'))
            action = safe_text(rowd.get('recommended_action'))
            market = safe_text(rowd.get('market_read'))
            lines.append(f'— {event}: {pick}')
            lines.append(f'  {"Acción" if es else "Action"}: {action}')
            if market:
                lines.append(f'  {"Mercado" if es else "Market"}: {market}')
        lines.append('')
    if brand.disclaimer:
        lines.append(brand.disclaimer)
    return '\n'.join(lines).strip()


st.title(t('title'))
st.caption(t('caption'))

with st.expander(t('input'), expanded=True):
    workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    use_saved = st.checkbox(t('use_saved'), value=True)
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ('', pd.DataFrame())
    upload_source, upload_rows = read_uploaded_rows()
    raw = pd.concat([frame for frame in (saved_rows, upload_rows) if frame is not None and not frame.empty], ignore_index=True, sort=False) if (not saved_rows.empty or not upload_rows.empty) else pd.DataFrame()
    st.caption(f"{t('source')}: " + (', '.join([name for name in (saved_source, upload_source) if name]) or 'none'))

if raw.empty:
    st.warning(t('empty'))
    st.stop()

normalized = normalize_frame(raw)
all_sports = sport_options(normalized)

with st.expander(t('profile'), expanded=True):
    profile_ids = sorted({safe_text(row.get('profile_id')) for row in list_profiles() if safe_text(row.get('profile_id'))}) or ['default']
    p1, p2, p3 = st.columns([2, 1, 1])
    selected_profile = p1.selectbox(t('profile_id'), profile_ids, index=0)
    profile_id = p1.text_input(t('profile_key'), value=selected_profile)
    if p2.button(t('load_profile'), use_container_width=True):
        st.session_state['report_studio_profile'] = asdict(load_profile(profile_id))
        st.rerun()
    loaded = WhiteLabelProfile(**st.session_state.get('report_studio_profile', {})).normalized() if st.session_state.get('report_studio_profile') else load_profile(profile_id)
    c1, c2 = st.columns(2)
    brand_name = c1.text_input(t('brand_name'), value=loaded.brand_name)
    tagline = c2.text_input(t('tagline'), value=loaded.tagline)
    report_title = c1.text_input(t('report_title'), value=loaded.report_title)
    logo_url = c2.text_input(t('logo_url'), value=loaded.logo_url)
    mode_options = ['Consumer Magazine','Tipster Report','Client-Safe Summary','Analyst Proof Report'] if LANG == 'en' else ['Revista consumidor','Reporte tipster','Resumen cliente','Reporte técnico']
    report_mode = c1.selectbox(t('mode'), mode_options, index=mode_options.index(loaded.preferred_report_mode) if loaded.preferred_report_mode in mode_options else 0)
    risk_values = ['Balanced','Conservative','Aggressive'] if LANG == 'en' else ['Balanceado','Conservador','Agresivo']
    risk_preference = c2.selectbox(t('risk'), risk_values, index=risk_values.index(loaded.risk_preference) if loaded.risk_preference in risk_values else 0)
    visibility = c2.selectbox(t('visibility'), ['private','public'], index=0)
    preferred_sports = st.multiselect(t('sports'), all_sports, default=[sport for sport in list(loaded.preferred_sports or []) if sport in all_sports], key='report_profile_sports')
    disclaimer_default = 'Contenido informativo. No garantiza resultados.' if LANG == 'es' else 'Informational content only. Results are not guaranteed.'
    disclaimer = st.text_area(t('disclaimer'), value=loaded.disclaimer or disclaimer_default, height=80)
    technical = 'Analyst' in report_mode or 'técnico' in report_mode.lower()
    if p3.button(t('save_profile'), use_container_width=True):
        saved = save_profile(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace_id, brand_name=brand_name, logo_url=logo_url, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_report_mode=report_mode, preferred_sports=list(preferred_sports), risk_preference=risk_preference, show_technical_fields=technical, default_audience='analyst' if technical else 'consumer', delivery_settings={'save_latest_feed': True, 'visibility': visibility}))
        st.session_state['report_studio_profile'] = asdict(saved)
        st.success(t('save_profile'))

max_rows = st.number_input(t('max_rows'), min_value=1, max_value=500, value=75, step=1)
filtered = normalized.copy()
if preferred_sports and 'sport' in filtered.columns:
    filtered = filtered[filtered['sport'].map(safe_text).isin(preferred_sports)].copy()
filtered = enrich_sports_context(filtered.head(int(max_rows)).copy(), language=LANG)
brand = MagazineBrand(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace_id, language=LANG, logo_url=logo_url, disclaimer=disclaimer)
cards = enrich_rows(filtered, language=LANG)
if 'sports_context_summary' in cards.columns:
    unavailable = CONTEXT_UNAVAILABLE.get(LANG, CONTEXT_UNAVAILABLE['en'])
    has_context = cards['sports_context_summary'].map(safe_text).ne('').astype(bool) & cards['sports_context_summary'].ne(unavailable)
    cards.loc[has_context, 'game_preview'] = cards.loc[has_context, 'sports_context_summary']

mode_key = 'analyst' if technical else 'consumer'
html_report = render_consumer_magazine_html(cards, brand, mode=mode_key)
markdown_report = render_markdown_summary(cards, brand, mode=mode_key)
copy_text = whatsapp_copy(cards, brand)
json_report = cards_to_json(cards)
pdf_bytes = render_report_pdf(cards, brand, mode=mode_key)
csv_payload = cards.to_csv(index=False)
feed = save_app_feed(cards, brand, mode=mode_key, public=visibility == 'public')

st.markdown(render_status_dashboard(cards, language=LANG), unsafe_allow_html=True)
st.caption(t('context_note'))

safe_workspace = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in workspace_id)
tabs = st.tabs([t('cards'), t('magazine'), t('copy'), t('proof'), t('exports'), t('profile_json'), t('feed_json')])
with tabs[0]:
    st.markdown(render_premium_card_deck(cards, language=LANG), unsafe_allow_html=True)
with tabs[1]:
    st.markdown(html_report, unsafe_allow_html=True)
with tabs[2]:
    st.text_area(t('copy_label'), value=copy_text, height=420)
    st.download_button(t('copy_download'), data=copy_text, file_name=f'whatsapp_copy_{safe_workspace}.txt', mime='text/plain')
with tabs[3]:
    proof_cols = ['event','sport','prediction','decimal_price','model_probability','market_probability','model_market_edge','expected_value_per_unit','odds_verified','report_lane','publish_ready','tennis_blocked','proof_id','locked_at_utc','odds_source','bookmaker','model_probability_source','sports_context_summary']
    cols = [col for col in proof_cols if col in cards.columns]
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
with tabs[4]:
    st.download_button(t('pdf'), data=pdf_bytes, file_name=f'report_{safe_workspace}.pdf', mime='application/pdf')
    st.download_button(t('html'), data=html_report, file_name=f'report_{safe_workspace}.html', mime='text/html')
    st.download_button(t('md'), data=markdown_report, file_name=f'report_{safe_workspace}.md', mime='text/markdown')
    st.download_button(t('copy_download'), data=copy_text, file_name=f'whatsapp_copy_{safe_workspace}.txt', mime='text/plain')
    st.download_button(t('json'), data=json_report, file_name=f'report_{safe_workspace}.json', mime='application/json')
    st.download_button(t('csv'), data=csv_payload, file_name=f'report_{safe_workspace}.csv', mime='text/csv')
with tabs[5]:
    st.json(asdict(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace_id, brand_name=brand_name, logo_url=logo_url, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_report_mode=report_mode, preferred_sports=preferred_sports, risk_preference=risk_preference, show_technical_fields=technical, default_audience='analyst' if technical else 'consumer')))
with tabs[6]:
    st.success(t('feed_saved'))
    st.json(feed)
