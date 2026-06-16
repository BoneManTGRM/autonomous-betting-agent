from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    apply_result_updates,
    dashboard_metrics,
    daily_locked_report,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
    save_persistent_ledger,
)
from autonomous_betting_agent.odds_lock_tools import performance_by_group, update_profit_columns

st.set_page_config(page_title='Public Proof Dashboard', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='public_proof_dashboard_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Public Proof Dashboard',
        'caption': 'No-login proof dashboard for locked picks, auto-grading uploads, client-safe tables, and shareable report cards.',
        'info': 'This page does not call sports APIs. It only uses real locked proof rows from the persistent ledger, Odds Lock Pro session rows, or uploaded CSVs with proof_id and locked_at_utc.',
        'use_db': 'Use persistent ledger database',
        'use_session': 'Use Odds Lock Pro session rows',
        'upload_ledger': 'Upload locked ledger CSV',
        'upload_results': 'Upload finished results CSV for auto-grading',
        'save_db': 'Save merged ledger to persistent CSV database',
        'apply_results': 'Apply result updates',
        'source': 'Source',
        'rows': 'Locked',
        'resolved': 'Resolved',
        'record': 'Record',
        'hit_rate': 'Hit rate',
        'roi': 'ROI',
        'units': 'Units',
        'pending': 'Pending',
        'valid': 'Valid proof rows',
        'filtered': 'Filtered rows',
        'filters': 'Dashboard filters',
        'sport_filter': 'Sport filter',
        'market_filter': 'Market filter',
        'status_filter': 'Result status filter',
        'table': 'Public ledger table',
        'dashboard': 'Breakdowns',
        'cards': 'Report cards',
        'markdown_card': 'Markdown card',
        'html_card': 'HTML card',
        'daily_report': 'Daily report',
        'brand': 'Brand name',
        'card_title': 'Card title',
        'download_public': 'Download public proof CSV',
        'download_private': 'Download private audit CSV',
        'download_markdown': 'Download Markdown card',
        'download_html': 'Download HTML card',
        'download_report': 'Download daily report TXT',
        'no_rows': 'No locked proof rows found yet. Create locks in Odds Lock Pro or upload a locked ledger with proof_id and locked_at_utc.',
        'updated': 'Result update summary',
        'safety': 'Proof safety check',
    },
    'es': {
        'title': 'Dashboard Público de Prueba',
        'caption': 'Dashboard sin contraseña para picks bloqueados, autocalificación por CSV, tablas para clientes y tarjetas compartibles.',
        'info': 'Esta página no llama APIs deportivas. Solo usa filas bloqueadas reales desde el ledger persistente, filas de Odds Lock Pro en sesión o CSVs con proof_id y locked_at_utc.',
        'use_db': 'Usar base CSV persistente',
        'use_session': 'Usar filas de Odds Lock Pro en sesión',
        'upload_ledger': 'Subir CSV de ledger bloqueado',
        'upload_results': 'Subir CSV de resultados finalizados para autocalificar',
        'save_db': 'Guardar ledger combinado en base CSV persistente',
        'apply_results': 'Aplicar resultados',
        'source': 'Fuente',
        'rows': 'Bloqueados',
        'resolved': 'Resueltos',
        'record': 'Récord',
        'hit_rate': 'Acierto',
        'roi': 'ROI',
        'units': 'Unidades',
        'pending': 'Pendientes',
        'valid': 'Filas de prueba válidas',
        'filtered': 'Filas filtradas',
        'filters': 'Filtros del dashboard',
        'sport_filter': 'Filtro de deporte',
        'market_filter': 'Filtro de mercado',
        'status_filter': 'Filtro de resultado',
        'table': 'Tabla pública del ledger',
        'dashboard': 'Desgloses',
        'cards': 'Tarjetas de reporte',
        'markdown_card': 'Tarjeta Markdown',
        'html_card': 'Tarjeta HTML',
        'daily_report': 'Reporte diario',
        'brand': 'Nombre de marca',
        'card_title': 'Título de tarjeta',
        'download_public': 'Descargar CSV público',
        'download_private': 'Descargar CSV privado',
        'download_markdown': 'Descargar tarjeta Markdown',
        'download_html': 'Descargar tarjeta HTML',
        'download_report': 'Descargar reporte diario TXT',
        'no_rows': 'Aún no hay filas de prueba bloqueadas. Crea bloqueos en Odds Lock Pro o sube un ledger con proof_id y locked_at_utc.',
        'updated': 'Resumen de actualización de resultados',
        'safety': 'Chequeo de seguridad de prueba',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def read_sources() -> tuple[str, pd.DataFrame, int]:
    frames: list[pd.DataFrame] = []
    raw_count = 0
    names: list[str] = []
    if st.checkbox(t('use_db'), value=True):
        db = load_persistent_ledger()
        if not db.empty:
            frames.append(db)
            raw_count += len(db)
            names.append('persistent_ledger')
    if st.checkbox(t('use_session'), value=True):
        rows = st.session_state.get('odds_lock_pro_locked_rows') or []
        if rows:
            session_frame = pd.DataFrame(rows)
            frames.append(session_frame)
            raw_count += len(session_frame)
            names.append('session_locked_rows')
    uploads = st.file_uploader(t('upload_ledger'), type=['csv'], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
                raw_count += len(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'{upload.name}: {exc}')
    if not frames:
        return '', pd.DataFrame(), 0
    return ', '.join(names), merge_ledgers(*frames), raw_count


def filter_dashboard(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    with st.expander(t('filters'), expanded=False):
        filtered = frame.copy()
        sport_options = sorted([str(value) for value in filtered.get('sport', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        market_options = sorted([str(value) for value in filtered.get('market_type', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        status_options = sorted([str(value) for value in filtered.get('result_status', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        selected_sports = st.multiselect(t('sport_filter'), sport_options, default=sport_options)
        selected_markets = st.multiselect(t('market_filter'), market_options, default=market_options)
        selected_statuses = st.multiselect(t('status_filter'), status_options, default=status_options)
        if selected_sports and 'sport' in filtered.columns:
            filtered = filtered[filtered['sport'].astype(str).isin(selected_sports)]
        if selected_markets and 'market_type' in filtered.columns:
            filtered = filtered[filtered['market_type'].astype(str).isin(selected_markets)]
        if selected_statuses and 'result_status' in filtered.columns:
            filtered = filtered[filtered['result_status'].astype(str).isin(selected_statuses)]
        st.caption(f"{t('filtered')}: {len(filtered)}")
        return filtered


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))

source, ledger, raw_count = read_sources()
st.caption(f"{t('source')}: {source or 'none'}")

results_upload = st.file_uploader(t('upload_results'), type=['csv'], accept_multiple_files=False, key='proof_results_upload')
if results_upload is not None and not ledger.empty:
    try:
        result_frame = pd.read_csv(results_upload)
        if st.button(t('apply_results'), type='primary', use_container_width=True):
            ledger, update_stats = apply_result_updates(ledger, result_frame)
            st.session_state['odds_lock_pro_locked_rows'] = ledger.to_dict('records')
            st.json({t('updated'): update_stats})
    except Exception as exc:
        st.warning(str(exc))

if not ledger.empty and st.button(t('save_db'), use_container_width=True):
    ledger = save_persistent_ledger(ledger)
    st.success('Saved persistent ledger.' if LANG == 'en' else 'Ledger persistente guardado.')

ledger = filter_locked_proof_rows(ledger)
if ledger.empty:
    st.warning(t('no_rows'))
    st.stop()

ledger = update_profit_columns(ledger)
filtered_ledger = filter_dashboard(ledger)
metrics = dashboard_metrics(filtered_ledger)
raw_cols = st.columns(2)
raw_cols[0].metric(t('valid'), len(ledger))
raw_cols[1].metric('Ignored raw/non-proof rows' if LANG == 'en' else 'Filas crudas/no-prueba ignoradas', max(0, raw_count - len(ledger)))

cols = st.columns(7)
cols[0].metric(t('rows'), metrics['locked_picks'])
cols[1].metric(t('resolved'), metrics['resolved_picks'])
cols[2].metric(t('record'), f"{metrics['wins']}-{metrics['losses']}")
cols[3].metric(t('hit_rate'), pct(metrics['hit_rate']))
cols[4].metric(t('roi'), pct(metrics['roi']))
cols[5].metric(t('units'), metrics['profit_units'])
cols[6].metric(t('pending'), metrics['pending_picks'])

tabs = st.tabs([t('table'), t('dashboard'), t('cards')])

with tabs[0]:
    public = public_dashboard_table(filtered_ledger)
    st.dataframe(public, use_container_width=True, hide_index=True)
    st.download_button(t('download_public'), public.to_csv(index=False), file_name='public_proof_dashboard.csv', mime='text/csv')
    st.download_button(t('download_private'), filtered_ledger.to_csv(index=False), file_name='private_proof_audit.csv', mime='text/csv')

with tabs[1]:
    st.json(metrics)
    by_sport = performance_by_group(filtered_ledger, 'sport')
    if not by_sport.empty:
        st.subheader('By sport' if LANG == 'en' else 'Por deporte')
        st.dataframe(by_sport, use_container_width=True, hide_index=True)
    by_market = performance_by_group(filtered_ledger, 'market_type')
    if not by_market.empty:
        st.subheader('By market' if LANG == 'en' else 'Por mercado')
        st.dataframe(by_market, use_container_width=True, hide_index=True)

with tabs[2]:
    brand = st.text_input(t('brand'), value='Private Analytics')
    title = st.text_input(t('card_title'), value='Proof Dashboard')
    markdown = report_card_markdown(filtered_ledger, title=title, brand=brand)
    html = report_card_html(filtered_ledger, title=title, brand=brand)
    report = daily_locked_report(filtered_ledger, language='Español' if LANG == 'es' else 'English')
    st.subheader(t('markdown_card'))
    st.text_area(t('markdown_card'), value=markdown, height=220)
    st.download_button(t('download_markdown'), markdown, file_name='proof_dashboard_card.md', mime='text/markdown')
    st.subheader(t('html_card'))
    st.markdown(html, unsafe_allow_html=True)
    st.text_area(t('html_card'), value=html, height=260)
    st.download_button(t('download_html'), html, file_name='proof_dashboard_card.html', mime='text/html')
    st.subheader(t('daily_report'))
    st.text_area(t('daily_report'), value=report, height=320)
    st.download_button(t('download_report'), report, file_name='daily_locked_report.txt', mime='text/plain')
