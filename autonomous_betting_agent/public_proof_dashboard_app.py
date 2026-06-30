from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    apply_result_updates,
    dashboard_metrics,
    daily_locked_report,
    demo_ledger,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    normalize_workspace_id,
    proof_audit_frame,
    proof_audit_summary,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
    save_persistent_ledger,
)
from autonomous_betting_agent.event_exposure import add_event_exposure_columns, exposure_metrics
from autonomous_betting_agent.odds_lock_tools import performance_by_group, update_profit_columns
from autonomous_betting_agent.pick_hold_store import load_first_available, save_held_rows
from autonomous_betting_agent.row_normalizer import result_status, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value, render_upload_css

SESSION_KEYS = ['public_proof_dashboard_refresh_rows', 'odds_lock_pro_locked_rows']
IDENTITY_COLUMNS = ['active_list_id', 'ledger_batch_id', 'source_file']
HIGH_CONFIDENCE_FIELDS = [
    'confidence_bucket', 'confidence_tier', 'public_confidence', 'volume_tier',
    'profit_lane', 'profit_official_ok', 'profit_elite_ok', 'ultra80_candidate',
    'strict_ultra80_candidate', 'official_lock_ready', 'research_lock_ready',
]
TRUTHY_VALUES = {'true', '1', 'yes', 'y', 'pass', 'ok'}
RESOLVED_VALUES = {'win', 'loss', 'void'}

TEXT = {
    'en': {
        'title': 'Public Proof Dashboard',
        'caption': 'Client-safe proof dashboard for high-confidence locked picks, result uploads, report cards, and historical tracker review.',
        'info': 'Official proof mode uses high-confidence / lock-ready rows only. Full low-confidence research rows are not included in public proof performance.',
        'active_test_window': 'Active test ledger', 'test_window': 'Test Window ID',
        'use_db': 'Use saved proof ledger', 'use_session': 'Use current synced rows', 'use_demo': 'Show demo ledger if no real ledger exists',
        'upload_ledger': 'Upload locked ledger or historical tracker CSV', 'upload_results': 'Upload finished results CSV for auto-grading',
        'save_db': 'Save current dashboard ledger to this test ledger', 'apply_results': 'Apply result updates',
        'source': 'Source', 'active_source': 'Active proof source', 'valid': 'Rows', 'ignored_nonproof': 'Ignored raw/non-proof rows', 'proof_quality': 'Proof quality',
        'events': 'Unique events', 'pick_rows': 'Pick rows', 'completed_events': 'Completed events', 'resolved': 'Resolved', 'record': 'Record', 'hit_rate': 'Hit rate', 'voids': 'Voids', 'pending': 'Pending',
        'wins': 'Wins', 'losses': 'Losses', 'multi_market': 'Multi-market events', 'extra_pick_rows': 'Extra same-event rows',
        'roi': 'ROI', 'units': 'Units', 'clv': 'Avg CLV', 'beat_close': 'Beat close',
        'filters': 'Dashboard filters', 'filtered': 'Filtered rows', 'sport_filter': 'Sport filter', 'market_filter': 'Market filter', 'status_filter': 'Result status filter',
        'table': 'Public ledger table', 'dashboard': 'Breakdowns', 'audit': 'Proof audit', 'cards': 'Report cards', 'brand': 'Brand name', 'card_title': 'Card title',
        'markdown_card': 'Markdown card', 'html_card': 'HTML card', 'daily_report': 'Daily report',
        'download_public': 'Download public proof CSV', 'download_private': 'Download private audit CSV', 'download_audit': 'Download proof audit CSV',
        'download_markdown': 'Download Markdown card', 'download_html': 'Download HTML card', 'download_report': 'Download daily report TXT', 'download_tracker': 'Download normalized tracker CSV',
        'no_rows': 'No official high-confidence proof rows are loaded. Upload the high-confidence proof ledger or enable the saved proof ledger.',
        'tracker_warning': 'This file can be reviewed for record tracking, but it is not official high-confidence proof.', 'updated': 'Result update summary',
        'stale_warning': 'Ignored stale synced dashboard rows with no source_file/active_list_id. Run Pro Predictor Volume again or enable the saved proof ledger.',
        'source_identity': 'Active source identity', 'by_sport': 'By sport', 'by_market': 'By market', 'saved': 'Saved persistent ledger: ',
        'scope': 'Proof scope', 'official_scope': 'Official high-confidence proof only', 'research_scope': 'Research/all locked rows',
        'protect_history': 'Protected saved proof history from being replaced by an unresolved raw refresh.',
        'raw_refresh_warning': 'Current synced/uploaded rows have no resolved grades. Saved proof ledger was preferred when available.',
        'allow_unresolved_save': 'Allow saving unresolved rows over proof history',
    },
    'es': {
        'title': 'Dashboard Público de Prueba',
        'caption': 'Dashboard para clientes con picks bloqueados de alta confianza.',
        'info': 'El modo oficial usa solo filas bloqueadas de alta confianza. Las filas de baja confianza son investigación, no prueba pública.',
        'active_test_window': 'Ledger activo', 'test_window': 'ID de ventana', 'use_db': 'Usar ledger guardado', 'use_session': 'Usar filas sincronizadas actuales', 'use_demo': 'Mostrar demo',
        'upload_ledger': 'Subir CSV', 'upload_results': 'Subir resultados', 'save_db': 'Guardar ledger actual', 'apply_results': 'Aplicar resultados', 'source': 'Fuente', 'active_source': 'Fuente activa',
        'valid': 'Filas', 'ignored_nonproof': 'Ignoradas/no-prueba', 'proof_quality': 'Calidad prueba', 'events': 'Eventos únicos', 'pick_rows': 'Filas de picks', 'completed_events': 'Eventos terminados',
        'resolved': 'Resueltas', 'record': 'Récord', 'hit_rate': 'Acierto', 'voids': 'Voids', 'pending': 'Pendientes', 'wins': 'Victorias', 'losses': 'Derrotas',
        'multi_market': 'Eventos multi-mercado', 'extra_pick_rows': 'Filas extra mismo evento', 'roi': 'ROI', 'units': 'Unidades', 'clv': 'CLV prom.', 'beat_close': 'Superó cierre',
        'filters': 'Filtros', 'filtered': 'Filas filtradas', 'sport_filter': 'Deporte', 'market_filter': 'Mercado', 'status_filter': 'Estado',
        'table': 'Tabla pública', 'dashboard': 'Desgloses', 'audit': 'Auditoría', 'cards': 'Tarjetas', 'brand': 'Marca', 'card_title': 'Título', 'markdown_card': 'Markdown', 'html_card': 'HTML',
        'daily_report': 'Reporte', 'download_public': 'Descargar público', 'download_private': 'Descargar privado', 'download_audit': 'Descargar auditoría',
        'download_markdown': 'Descargar Markdown', 'download_html': 'Descargar HTML', 'download_report': 'Descargar reporte', 'download_tracker': 'Descargar tracker',
        'no_rows': 'No hay filas oficiales de alta confianza cargadas.', 'tracker_warning': 'Este archivo se puede revisar, pero no es prueba oficial de alta confianza.', 'updated': 'Actualización',
        'stale_warning': 'Se ignoraron filas sincronizadas antiguas sin source_file/active_list_id.', 'source_identity': 'Identidad de fuente activa', 'by_sport': 'Por deporte', 'by_market': 'Por mercado', 'saved': 'Ledger persistente guardado: ',
        'scope': 'Alcance', 'official_scope': 'Solo prueba oficial de alta confianza', 'research_scope': 'Investigación/todas las filas bloqueadas',
        'protect_history': 'Se protegió el historial guardado de prueba contra una actualización sin resultados.',
        'raw_refresh_warning': 'Las filas actuales no tienen resultados. Se prefirió el ledger guardado cuando existía.',
        'allow_unresolved_save': 'Permitir guardar filas sin resultados sobre el historial',
    },
}


def _t(lang: str, key: str) -> str:
    return TEXT[lang].get(key, TEXT['en'].get(key, key))


def _pct(value: float | None, digits: int = 1) -> str:
    return 'N/A' if value is None else f'{value * 100:.{digits}f}%'


def _truthy(value: Any) -> bool:
    return safe_text(value).lower() in TRUTHY_VALUES


def _status_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=str)
    return pd.Series([result_status(row) for row in frame.to_dict('records')], index=frame.index, dtype=str).str.lower()


def _resolved_count(frame: pd.DataFrame) -> int:
    status = _status_series(frame)
    return int(status.isin(RESOLVED_VALUES).sum())


def _has_current_identity(frame: pd.DataFrame) -> bool:
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return False
    return any(col in locked.columns and locked[col].map(safe_text).ne('').any() for col in IDENTITY_COLUMNS)


def _has_high_confidence_indicators(frame: pd.DataFrame) -> bool:
    return any(col in frame.columns and frame[col].map(safe_text).ne('').any() for col in HIGH_CONFIDENCE_FIELDS)


def _high_confidence_mask(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    text_checks = {
        'confidence_bucket': ['high_confidence', 'high confidence', 'b_high', 'elite', 'official'],
        'confidence_tier': ['high', 'elite', 'premium', 'qualified', 'official'],
        'public_confidence': ['qualified', 'premium', 'strict ultra', 'ultra 80', 'elite'],
        'volume_tier': ['a_', 'b_', 'strict', 'ultra', 'premium', 'high'],
        'profit_lane': ['official', 'elite', 'high_confidence', 'positive_ev'],
    }
    for col, terms in text_checks.items():
        if col in frame.columns:
            values = frame[col].map(safe_text).str.lower()
            for term in terms:
                mask = mask | values.str.contains(term, regex=False, na=False)
    for col in ['profit_official_ok', 'profit_elite_ok', 'ultra80_candidate', 'strict_ultra80_candidate', 'official_lock_ready']:
        if col in frame.columns:
            mask = mask | frame[col].map(_truthy).fillna(False)
    # Current high-confidence export uses play_small + lock_ready + scanner_strength_score >= 70.
    if {'agent_decision', 'lock_ready', 'scanner_strength_score'}.issubset(frame.columns):
        scanner = pd.to_numeric(frame['scanner_strength_score'], errors='coerce').fillna(0)
        decision = frame['agent_decision'].map(safe_text).str.lower()
        mask = mask | (frame['lock_ready'].map(_truthy).fillna(False) & decision.isin(['play_small', 'play_strong']) & scanner.ge(70))
    return mask


def official_high_confidence_rows(frame: pd.DataFrame) -> pd.DataFrame:
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return pd.DataFrame()
    if not _has_high_confidence_indicators(locked):
        # Older proof ledgers did not include confidence_bucket. Keep them rather than blanking history.
        return locked.copy()
    mask = _high_confidence_mask(locked)
    return locked[mask].copy()


def _load_saved_session_rows(workspace_id: str, lang: str) -> tuple[str, pd.DataFrame]:
    skipped = []
    for key in SESSION_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            frame = pd.DataFrame(rows)
            if _has_current_identity(frame):
                return key, frame
            skipped.append(key)
    for key in SESSION_KEYS:
        loaded_key, rows = load_first_available([key], workspace_id)
        if rows:
            frame = pd.DataFrame(rows)
            if _has_current_identity(frame):
                st.session_state[key] = rows
                return f'local:{key}', frame
            skipped.append(f'local:{key}')
    if skipped:
        st.warning(_t(lang, 'stale_warning'))
    return '', pd.DataFrame()


def _read_sources(
    workspace_id: str,
    *,
    use_db: bool,
    use_session: bool,
    use_demo: bool,
    uploads: list | None,
    official_only: bool,
    lang: str,
) -> tuple[str, pd.DataFrame, pd.DataFrame, int]:
    raw_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []
    names: list[str] = []
    raw_count = 0

    # Load saved proof first. This is the history anchor and prevents raw API refreshes from wiping proof metrics.
    if use_db:
        db = load_persistent_ledger(workspace_id=workspace_id)
        if not db.empty:
            raw_frames.append(db)
            ledger_frames.append(db)
            raw_count += len(db)
            names.append(f'persistent_ledger:{workspace_id}')

    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                raw_frames.append(frame)
                locked = filter_locked_proof_rows(frame)
                if not locked.empty:
                    ledger_frames.append(locked)
                raw_count += len(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'{upload.name}: {exc}')

    if use_session:
        label, session_frame = _load_saved_session_rows(workspace_id, lang)
        if not session_frame.empty:
            raw_frames.append(session_frame)
            locked = filter_locked_proof_rows(session_frame)
            if not locked.empty:
                ledger_frames.append(locked)
            raw_count += len(session_frame)
            names.append(label)

    if not raw_frames:
        demo = demo_ledger() if use_demo else pd.DataFrame()
        return ('demo_ledger' if use_demo else ''), demo, demo, len(demo)

    raw_all = pd.concat(raw_frames, ignore_index=True, sort=False)
    ledger = merge_ledgers(*ledger_frames) if ledger_frames else pd.DataFrame()
    if official_only and not ledger.empty:
        ledger = official_high_confidence_rows(ledger)
    return ', '.join(names), ledger, raw_all, raw_count


def _with_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    exposed = add_event_exposure_columns(frame)
    metrics = dashboard_metrics(exposed) if not exposed.empty else {}
    metrics.update(exposure_metrics(exposed))
    return exposed, metrics


def _filter_dashboard(frame: pd.DataFrame, lang: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    with st.expander(_t(lang, 'filters'), expanded=False):
        filtered = frame.copy()
        for col, label in [('sport', 'sport_filter'), ('market_type', 'market_filter'), ('result_status', 'status_filter')]:
            if col not in filtered.columns:
                continue
            options = sorted([str(v) for v in filtered[col].dropna().unique() if str(v).strip()])
            display_options, display_to_raw = localize_options(options, lang)
            selected_display = st.multiselect(_t(lang, label), display_options, default=display_options)
            selected = [display_to_raw.get(item, item) for item in selected_display]
            if selected:
                filtered = filtered[filtered[col].astype(str).isin(selected)]
        st.caption(f"{_t(lang, 'filtered')}: {len(filtered)}")
        return filtered


def _show_source_summary(frame: pd.DataFrame, source: str, workspace_id: str, lang: str) -> None:
    exposed = add_event_exposure_columns(frame)
    metrics = exposure_metrics(exposed)
    status = _status_series(exposed)
    info = {
        'source': source or 'none', 'workspace_id': workspace_id,
        'pick_rows': metrics.get('pick_rows', len(exposed)), 'unique_events': metrics.get('unique_events', 0),
        'completed_events': metrics.get('completed_events', 0), 'wins': int(status.eq('win').sum()),
        'losses': int(status.eq('loss').sum()), 'voids': int(status.eq('void').sum()),
        'pending': int(status.isin(['pending', 'unknown', 'scheduled', 'live', '', 'needs_review', 'nan']).sum()),
        'events_with_multiple_pick_rows': metrics.get('events_with_multiple_pick_rows', 0),
        'extra_same_event_pick_rows': metrics.get('extra_same_event_pick_rows', 0),
        'max_pick_rows_per_event': metrics.get('max_pick_rows_per_event', 0),
    }
    st.subheader(_t(lang, 'active_source'))
    cols = st.columns(7)
    cols[0].metric(_t(lang, 'events'), info['unique_events']); cols[1].metric(_t(lang, 'pick_rows'), info['pick_rows']); cols[2].metric(_t(lang, 'wins'), info['wins']); cols[3].metric(_t(lang, 'losses'), info['losses']); cols[4].metric(_t(lang, 'voids'), info['voids']); cols[5].metric(_t(lang, 'pending'), info['pending']); cols[6].metric(_t(lang, 'multi_market'), info['events_with_multiple_pick_rows'])
    with st.expander(_t(lang, 'source_identity'), expanded=False):
        st.dataframe(localize_dataframe(pd.DataFrame([info]), lang), use_container_width=True, hide_index=True)


def _show_tracker_mode(raw_input: pd.DataFrame, lang: str) -> None:
    exposed, metrics = _with_metrics(raw_input)
    if exposed.empty:
        st.warning(_t(lang, 'no_rows'))
        st.stop()
    st.warning(_t(lang, 'tracker_warning'))
    cols = st.columns(8)
    cols[0].metric(_t(lang, 'events'), metrics.get('unique_events', 0)); cols[1].metric(_t(lang, 'pick_rows'), metrics.get('pick_rows', len(exposed))); cols[2].metric(_t(lang, 'completed_events'), metrics.get('completed_events', 0)); cols[3].metric(_t(lang, 'record'), f"{metrics.get('wins', 0)}-{metrics.get('losses', 0)}"); cols[4].metric(_t(lang, 'hit_rate'), _pct(metrics.get('pick_hit_rate_excluding_voids') or metrics.get('hit_rate'))); cols[5].metric(_t(lang, 'voids'), metrics.get('voids', 0)); cols[6].metric(_t(lang, 'pending'), metrics.get('pending_pick_rows', 0)); cols[7].metric(_t(lang, 'proof_quality'), '0/100')
    show_cols = [col for col in ['event', 'unique_event_id', 'same_event_pick_count', 'event_pick_index', 'sport', 'market_type', 'line_point', 'prediction', 'result_status', 'winner', 'final_score', 'event_start_utc', 'source_file'] if col in exposed.columns]
    st.dataframe(localize_dataframe(exposed[show_cols] if show_cols else exposed, lang), use_container_width=True, hide_index=True)
    st.download_button(_t(lang, 'download_tracker'), exposed.to_csv(index=False), file_name='historical_tracker_non_proof.csv', mime='text/csv')
    st.stop()


def _public_table_with_exposure(frame: pd.DataFrame) -> pd.DataFrame:
    public = public_dashboard_table(frame)
    if public.empty or len(public) != len(frame):
        return public
    out = public.copy()
    insert_at = 1 if 'event' in out.columns else 0
    for col in ['unique_event_id', 'same_event_pick_count', 'event_pick_index']:
        if col in frame.columns and col not in out.columns:
            out.insert(min(insert_at, len(out.columns)), col, frame[col].to_list())
            insert_at += 1
    return out


def run() -> None:
    st.set_page_config(page_title='Public Proof Dashboard', layout='wide')
    lang = render_app_sidebar('public_proof_dashboard', language_key='public_proof_dashboard_language', selector='radio')
    render_upload_css(st, lang)
    st.title(_t(lang, 'title'))
    st.caption(_t(lang, 'caption'))
    st.info(_t(lang, 'info'))

    with st.expander(_t(lang, 'active_test_window'), expanded=True):
        workspace_input = st.text_input(_t(lang, 'test_window'), value=st.session_state.get('aba_test_window_id', 'test_01'))
        scope_options = [_t(lang, 'official_scope'), _t(lang, 'research_scope')]
        proof_scope = st.radio(_t(lang, 'scope'), scope_options, index=0, horizontal=True)
        official_only = proof_scope == scope_options[0]
        use_db = st.checkbox(_t(lang, 'use_db'), value=True, help='ON by default so public proof history is not lost when live prediction files refresh.')
        use_session = st.checkbox(_t(lang, 'use_session'), value=True)
        use_demo = st.checkbox(_t(lang, 'use_demo'), value=False, key='public_proof_use_demo')
        allow_unresolved_save = st.checkbox(_t(lang, 'allow_unresolved_save'), value=False)
        uploads = st.file_uploader(_t(lang, 'upload_ledger'), type=['csv'], accept_multiple_files=True)

    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id

    source, ledger, raw_input, raw_count = _read_sources(
        workspace_id,
        use_db=use_db,
        use_session=use_session,
        use_demo=use_demo,
        uploads=uploads,
        official_only=official_only,
        lang=lang,
    )
    st.caption(f"{_t(lang, 'active_test_window')}: {workspace_id}")
    st.caption(f"{_t(lang, 'source')}: {localize_value(source or 'none', lang)}")

    saved_for_protection = load_persistent_ledger(workspace_id=workspace_id)
    if official_only and not saved_for_protection.empty:
        saved_for_protection = official_high_confidence_rows(saved_for_protection)
    saved_resolved = _resolved_count(saved_for_protection)
    ledger_resolved = _resolved_count(ledger)
    if saved_resolved > ledger_resolved and saved_resolved > 0:
        st.warning(_t(lang, 'raw_refresh_warning'))
        ledger = merge_ledgers(saved_for_protection, ledger)
        if official_only:
            ledger = official_high_confidence_rows(ledger)

    results_upload = st.file_uploader(_t(lang, 'upload_results'), type=['csv'], accept_multiple_files=False, key='proof_results_upload')
    if results_upload is not None and not ledger.empty:
        result_frame = pd.read_csv(results_upload)
        if st.button(_t(lang, 'apply_results'), type='primary', use_container_width=True):
            ledger, update_stats = apply_result_updates(ledger, result_frame)
            if official_only:
                ledger = official_high_confidence_rows(ledger)
            ledger['test_window_id'] = workspace_id
            records = ledger.to_dict('records')
            st.session_state['odds_lock_pro_locked_rows'] = records
            st.session_state['public_proof_dashboard_refresh_rows'] = records
            save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
            save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
            save_persistent_ledger(ledger, workspace_id=workspace_id)
            st.json({_t(lang, 'updated'): update_stats})

    if not ledger.empty and source != 'demo_ledger' and st.button(_t(lang, 'save_db'), use_container_width=True):
        if _resolved_count(ledger) == 0 and saved_resolved > 0 and not allow_unresolved_save:
            st.error(_t(lang, 'protect_history'))
        else:
            ledger['test_window_id'] = workspace_id
            ledger = save_persistent_ledger(ledger, workspace_id=workspace_id)
            if official_only:
                ledger = official_high_confidence_rows(ledger)
            records = ledger.to_dict('records')
            save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
            save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
            st.success(_t(lang, 'saved') + workspace_id)

    ledger = official_high_confidence_rows(ledger) if official_only else filter_locked_proof_rows(ledger)
    if ledger.empty:
        if not raw_input.empty and not official_only:
            _show_tracker_mode(raw_input, lang)
        st.warning(_t(lang, 'no_rows'))
        st.stop()

    ledger, _ = _with_metrics(update_profit_columns(ledger))
    _show_source_summary(ledger, source, workspace_id, lang)
    filtered_ledger = _filter_dashboard(ledger, lang)
    filtered_ledger, metrics = _with_metrics(filtered_ledger)
    audit_summary = proof_audit_summary(filtered_ledger)

    raw_cols = st.columns(5)
    raw_cols[0].metric(_t(lang, 'valid'), len(ledger))
    raw_cols[1].metric(_t(lang, 'events'), metrics.get('unique_events', 0))
    raw_cols[2].metric(_t(lang, 'ignored_nonproof'), max(0, raw_count - len(ledger)))
    raw_cols[3].metric(_t(lang, 'multi_market'), metrics.get('events_with_multiple_pick_rows', 0))
    raw_cols[4].metric(_t(lang, 'proof_quality'), f"{audit_summary.get('proof_quality_score', 0)}/100")

    resolved_display = metrics.get('resolved_pick_rows', metrics.get('resolved_picks', 0))
    pending_display = metrics.get('pending_pick_rows', metrics.get('pending_picks', 0))
    hit = metrics.get('pick_hit_rate_excluding_voids') if metrics.get('pick_hit_rate_excluding_voids') is not None else metrics.get('hit_rate')
    cols = st.columns(10)
    cols[0].metric(_t(lang, 'events'), metrics.get('unique_events', 0)); cols[1].metric(_t(lang, 'pick_rows'), metrics.get('pick_rows', len(filtered_ledger))); cols[2].metric(_t(lang, 'completed_events'), metrics.get('completed_events', 0)); cols[3].metric(_t(lang, 'resolved'), resolved_display); cols[4].metric(_t(lang, 'record'), f"{metrics.get('wins', 0)}-{metrics.get('losses', 0)}"); cols[5].metric(_t(lang, 'hit_rate'), _pct(hit)); cols[6].metric(_t(lang, 'roi'), _pct(metrics.get('roi'))); cols[7].metric(_t(lang, 'units'), metrics.get('profit_units', 0)); cols[8].metric(_t(lang, 'pending'), pending_display); cols[9].metric(_t(lang, 'clv'), _pct(metrics.get('avg_clv_percent'), 2))
    st.caption(f"{_t(lang, 'voids')}: {metrics.get('voids', metrics.get('pushes', 0))} | {_t(lang, 'extra_pick_rows')}: {metrics.get('extra_same_event_pick_rows', 0)} | {_t(lang, 'beat_close')}: {_pct(metrics.get('beat_close_rate'))}")

    tabs = st.tabs([_t(lang, 'table'), _t(lang, 'dashboard'), _t(lang, 'audit'), _t(lang, 'cards')])
    with tabs[0]:
        public = _public_table_with_exposure(filtered_ledger)
        st.dataframe(localize_dataframe(public, lang), use_container_width=True, hide_index=True)
        st.download_button(_t(lang, 'download_public'), public.to_csv(index=False), file_name=f'public_proof_dashboard_{workspace_id}.csv', mime='text/csv')
        st.download_button(_t(lang, 'download_private'), filtered_ledger.to_csv(index=False), file_name=f'private_proof_audit_{workspace_id}.csv', mime='text/csv')
    with tabs[1]:
        st.dataframe(localize_dataframe(pd.DataFrame([metrics]), lang), use_container_width=True, hide_index=True)
        by_sport = performance_by_group(filtered_ledger, 'sport')
        if not by_sport.empty:
            st.subheader(_t(lang, 'by_sport')); st.dataframe(localize_dataframe(by_sport, lang), use_container_width=True, hide_index=True)
        by_market = performance_by_group(filtered_ledger, 'market_type')
        if not by_market.empty:
            st.subheader(_t(lang, 'by_market')); st.dataframe(localize_dataframe(by_market, lang), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(localize_dataframe(pd.DataFrame([audit_summary]), lang), use_container_width=True, hide_index=True)
        audit = proof_audit_frame(filtered_ledger)
        st.dataframe(localize_dataframe(audit, lang), use_container_width=True, hide_index=True)
        st.download_button(_t(lang, 'download_audit'), audit.to_csv(index=False), file_name=f'proof_audit_{workspace_id}.csv', mime='text/csv')
    with tabs[3]:
        brand = st.text_input(_t(lang, 'brand'), value='ABA Signal Pro · Powered by Reparodynamics')
        title = st.text_input(_t(lang, 'card_title'), value='Proof Dashboard' if lang == 'en' else 'Dashboard de Prueba')
        markdown = report_card_markdown(filtered_ledger, title=title, brand=brand)
        html = report_card_html(filtered_ledger, title=title, brand=brand)
        report = daily_locked_report(filtered_ledger, language='Español' if lang == 'es' else 'English')
        st.text_area(_t(lang, 'markdown_card'), value=markdown, height=240); st.download_button(_t(lang, 'download_markdown'), markdown, file_name=f'proof_dashboard_card_{workspace_id}.md', mime='text/markdown')
        st.markdown(html, unsafe_allow_html=True); st.text_area(_t(lang, 'html_card'), value=html, height=280); st.download_button(_t(lang, 'download_html'), html, file_name=f'proof_dashboard_card_{workspace_id}.html', mime='text/html')
        st.text_area(_t(lang, 'daily_report'), value=report, height=340); st.download_button(_t(lang, 'download_report'), report, file_name=f'daily_locked_report_{workspace_id}.txt', mime='text/plain')
