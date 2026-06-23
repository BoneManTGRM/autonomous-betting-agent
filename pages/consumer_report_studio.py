from __future__ import annotations

import base64
import html
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.consumer_report_engine import (
    BrandSettings,
    brand_payload,
    cards_to_app_feed,
    cards_to_json,
    consumer_cards,
    prepare_report_frame,
    render_magazine_html,
    render_magazine_markdown,
    render_short_copy,
    report_quality_summary,
)
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.row_normalizer import normalize_frame, result_status, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Consumer Report Studio', layout='wide')
LANG = render_app_sidebar('consumer_report_studio', language_key='consumer_report_studio_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Consumer Report Studio',
        'caption': 'Turn ABA rows into high-level consumer cards, magazine reports, app feeds, and tipster-ready copy.',
        'workspace': 'Client / Workspace ID',
        'workspace_help': 'Use a separate ID per client, tipster, app, or report brand.',
        'input': 'Input rows',
        'use_saved': 'Use saved workspace rows',
        'upload': 'Upload CSV rows',
        'source': 'Source',
        'no_rows': 'No rows found. Use Odds Lock Pro first or upload a CSV.',
        'brand': 'White-label brand',
        'brand_name': 'Brand / tipster name',
        'tagline': 'Tagline',
        'report_title': 'Report title',
        'logo_url': 'Logo URL',
        'disclaimer': 'Disclaimer',
        'filters': 'Report filters',
        'max_rows': 'Max picks/cards',
        'min_probability': 'Minimum model probability',
        'official_only': 'Official/proof-ready only',
        'pending_only': 'Pending/upcoming only',
        'sport_filter': 'Sports',
        'market_filter': 'Markets',
        'cards_tab': 'High-level cards',
        'magazine_tab': 'Magazine report',
        'copy_tab': 'WhatsApp / Telegram copy',
        'feed_tab': 'CSV / JSON feed',
        'settings_tab': 'Brand settings',
        'diagnostics_tab': 'Diagnostics',
        'cards': 'Cards',
        'avg_prob': 'Avg probability',
        'proof_rows': 'Proof rows',
        'publish_ready': 'Publish-ready',
        'warnings': 'Warnings',
        'download_cards_csv': 'Download cards CSV',
        'download_json': 'Download full JSON',
        'download_app_json': 'Download app feed JSON',
        'download_md': 'Download Markdown report',
        'download_html': 'Download HTML report',
        'download_copy': 'Download copy text',
        'markdown': 'Copy/paste report',
        'short_copy': 'Short copy',
        'json_feed': 'JSON feed',
        'app_feed': 'App feed',
        'settings_json': 'Current brand payload',
        'preview_cols': 'Preview columns',
        'quality_summary': 'Quality summary',
        'require_odds': 'Require verified sportsbook odds for publish-ready status',
        'odds_warning': 'Odds are unavailable or not verified on {count} selected row(s). These rows are model-only, edge is N/A, and they are not publish-ready.',
    },
    'es': {
        'title': 'Estudio de Reportes para Consumidores',
        'caption': 'Convierte filas ABA en tarjetas premium, reportes tipo revista, feeds para app y copy para tipsters.',
        'workspace': 'ID de cliente / workspace',
        'workspace_help': 'Usa un ID separado para cada cliente, tipster, app o marca de reporte.',
        'input': 'Filas de entrada',
        'use_saved': 'Usar filas guardadas del workspace',
        'upload': 'Subir CSV',
        'source': 'Fuente',
        'no_rows': 'No hay filas. Usa Odds Lock Pro primero o sube un CSV.',
        'brand': 'Marca white-label',
        'brand_name': 'Marca / tipster',
        'tagline': 'Lema',
        'report_title': 'Título del reporte',
        'logo_url': 'URL del logo',
        'disclaimer': 'Aviso legal',
        'filters': 'Filtros del reporte',
        'max_rows': 'Máximo de picks/tarjetas',
        'min_probability': 'Probabilidad mínima del modelo',
        'official_only': 'Solo oficiales/listos para prueba',
        'pending_only': 'Solo pendientes/próximos',
        'sport_filter': 'Deportes',
        'market_filter': 'Mercados',
        'cards_tab': 'Tarjetas premium',
        'magazine_tab': 'Reporte revista',
        'copy_tab': 'Copy WhatsApp / Telegram',
        'feed_tab': 'Feed CSV / JSON',
        'settings_tab': 'Configuración de marca',
        'diagnostics_tab': 'Diagnóstico',
        'cards': 'Tarjetas',
        'avg_prob': 'Probabilidad media',
        'proof_rows': 'Filas con prueba',
        'publish_ready': 'Listas para publicar',
        'warnings': 'Alertas',
        'download_cards_csv': 'Descargar CSV de tarjetas',
        'download_json': 'Descargar JSON completo',
        'download_app_json': 'Descargar JSON para app',
        'download_md': 'Descargar reporte Markdown',
        'download_html': 'Descargar reporte HTML',
        'download_copy': 'Descargar copy',
        'markdown': 'Reporte para copiar/pegar',
        'short_copy': 'Copy corto',
        'json_feed': 'Feed JSON',
        'app_feed': 'Feed para app',
        'settings_json': 'Payload actual de marca',
        'preview_cols': 'Columnas de vista previa',
        'quality_summary': 'Resumen de calidad',
        'require_odds': 'Requerir cuotas verificadas para marcar listo para publicar',
        'odds_warning': 'No hay cuotas verificadas en {count} fila(s). Estas filas son solo modelo, el edge es N/A y no están listas para publicar.',
    },
}

HANDOFF_KEYS = (
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
    'pro_predictor_high_confidence_rows',
    'pro_predictor_latest_rows',
    'what_are_the_odds_latest_rows',
    'ara_latest_predictions',
)

UNVERIFIED_SOURCE_TOKENS = (
    '.csv', 'session:', 'saved:', 'persistent', 'ledger', 'storage', 'upload', 'export',
    'model', 'model_only', 'high_confidence', 'pro_predictor', 'consensus_average',
    'fallback', 'unavailable', 'missing', 'no odds', 'no_odds', 'api limit', 'limit reached',
    'quota', 'maxed', 'rate limit', 'offline', 'simulated', 'research', 'test',
)
ODDS_BLOCKER_TEXT = 'Missing valid odds'
ODDS_BLOCKER_TEXT_ES = 'Falta cuota válida'


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def download_link(label: str, payload: str | bytes, filename: str, mime: str) -> None:
    data = payload if isinstance(payload, bytes) else payload.encode('utf-8')
    encoded = base64.b64encode(data).decode('ascii')
    st.markdown(
        f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:{html.escape(mime)};base64,{encoded}">{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def rows_from_saved_sources(workspace_id: str) -> tuple[str, pd.DataFrame]:
    persistent = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    if persistent is not None and not persistent.empty:
        return 'persistent_proof_ledger', persistent
    for key in HANDOFF_KEYS:
        session_rows = st.session_state.get(key) or []
        if session_rows:
            return f'session:{key}', pd.DataFrame(session_rows)
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    if rows:
        return f'saved:{key}', pd.DataFrame(rows)
    return '', pd.DataFrame()


def read_uploaded_rows() -> tuple[str, pd.DataFrame]:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame['source_file'] = upload.name
            frames.append(frame)
            names.append(upload.name)
        except Exception as exc:
            st.warning(f'{upload.name}: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


def probability_metric(cards: pd.DataFrame) -> str:
    if cards.empty or 'model_probability' not in cards.columns:
        return 'N/A'
    values = pd.to_numeric(cards['model_probability'], errors='coerce').dropna()
    if values.empty:
        return 'N/A'
    return f'{float(values.mean()) * 100:.1f}%'


def unique_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame[column].tolist() if safe_text(value)})


def filter_by_multiselect(frame: pd.DataFrame, column: str, selected: list[str]) -> pd.DataFrame:
    if frame.empty or not selected or column not in frame.columns:
        return frame
    return frame[frame[column].map(safe_text).isin(selected)].copy()


def status_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=str)
    return frame.apply(lambda row: result_status(row.to_dict()), axis=1)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _probability_float(value: Any) -> float | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed /= 100.0
    return parsed if 0.0 <= parsed <= 1.0 else None


def _pct_label(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return 'N/A'
    return f'{value * 100:+.1f}%' if signed else f'{value * 100:.1f}%'


def _decimal_price(row: Mapping[str, Any]) -> float | None:
    for name in ('decimal_price', 'best_price', 'average_price', 'avg_price', 'sportsbook_odds', 'odds_decimal'):
        value = _safe_float(row.get(name))
        if value is not None and value > 1.0:
            return value
    return None


def _market_source(row: Mapping[str, Any]) -> str:
    # Do not treat source_file as a sportsbook source. It only identifies the CSV/handoff origin.
    return safe_text(row.get('bookmaker')) or safe_text(row.get('sportsbook')) or safe_text(row.get('book')) or safe_text(row.get('odds_source'))


def _source_is_verified(source: str) -> bool:
    text = safe_text(source).lower()
    if not text:
        return False
    return not any(token in text for token in UNVERIFIED_SOURCE_TOKENS)


def has_verified_market_odds(row: Mapping[str, Any]) -> bool:
    return _decimal_price(row) is not None and _source_is_verified(_market_source(row))


def sanitize_model_only_rows(frame: pd.DataFrame, *, require_verified_odds: bool) -> tuple[pd.DataFrame, int]:
    if frame is None or frame.empty or not require_verified_odds:
        return frame, 0
    out = frame.copy()
    invalid_indexes: list[int] = []
    for idx, row in out.iterrows():
        if not has_verified_market_odds(row.to_dict()):
            invalid_indexes.append(idx)
    if not invalid_indexes:
        return out, 0

    clear_price_cols = [
        'decimal_price', 'best_price', 'average_price', 'avg_price', 'sportsbook_odds', 'odds_decimal',
        'model_edge', 'model_market_edge', 'edge_probability', 'edge', 'expected_value_per_unit',
        'computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev', 'ev', '_robust_expected_value',
        'robust_expected_value', '_robust_profit_at_80_percent', 'robust_profit_at_80_percent',
    ]
    for idx in invalid_indexes:
        for col in clear_price_cols:
            if col in out.columns:
                out.at[idx, col] = ''
        for col in ('bookmaker', 'sportsbook', 'book'):
            if col in out.columns:
                out.at[idx, col] = ''
        out.at[idx, 'odds_source'] = 'odds_unavailable_api_limit'
        out.at[idx, 'odds_status'] = 'odds_unavailable'
        out.at[idx, 'official_lock_ready'] = False
        out.at[idx, 'official_ev_pick'] = False
        out.at[idx, 'ledger_type'] = 'research_model_only'
        existing = safe_text(out.at[idx, 'lock_blockers']) if 'lock_blockers' in out.columns else ''
        blockers = [part.strip() for part in existing.split(';') if part.strip()]
        if 'odds_unavailable' not in blockers:
            blockers.append('odds_unavailable')
        out.at[idx, 'lock_blockers'] = '; '.join(blockers)
    return out, len(invalid_indexes)


def _append_flag(flags: Any, value: str) -> str:
    items = [part.strip() for part in safe_text(flags).split(';') if part.strip()]
    if value not in items:
        items.append(value)
    return '; '.join(items)


def _value_rating(edge: float | None, odds_valid: bool) -> str:
    if not odds_valid:
        return 'Odds unavailable' if LANG == 'en' else 'Cuotas no disponibles'
    if edge is None:
        return 'Unknown' if LANG == 'en' else 'Sin dato'
    if edge >= 0.05:
        return 'Strong Value' if LANG == 'en' else 'Valor fuerte'
    if edge >= 0.02:
        return 'Positive Value' if LANG == 'en' else 'Valor positivo'
    if edge > -0.01:
        return 'Neutral'
    return 'Negative Value' if LANG == 'en' else 'Valor negativo'


def _audit_message(model_prob: float | None, market_prob: float | None, odds_valid: bool) -> str:
    if model_prob is None:
        return 'Missing model probability' if LANG == 'en' else 'Falta probabilidad del modelo'
    if not odds_valid or market_prob is None:
        return 'Odds unavailable/API limit; model-only, not publish-ready' if LANG == 'en' else 'Cuotas no disponibles/límite API; solo modelo, no publicar'
    return 'Verified sportsbook odds loaded' if LANG == 'en' else 'Cuotas verificadas cargadas'


def enrich_card_values(cards: pd.DataFrame, source_rows: pd.DataFrame) -> pd.DataFrame:
    if cards is None or cards.empty:
        return pd.DataFrame() if cards is None else cards
    out = cards.copy()
    source_records = source_rows.to_dict('records') if source_rows is not None and not source_rows.empty else []
    for pos, idx in enumerate(out.index):
        source_row = source_records[pos] if pos < len(source_records) else out.loc[idx].to_dict()
        model_prob = _probability_float(out.at[idx, 'model_probability'] if 'model_probability' in out.columns else None)
        odds_valid = has_verified_market_odds(source_row)
        price = _decimal_price(source_row) if odds_valid else None
        market_prob = None if price is None else 1.0 / price
        edge = None if model_prob is None or market_prob is None else model_prob - market_prob

        out.at[idx, 'model_probability'] = model_prob
        out.at[idx, 'probability_label'] = _pct_label(model_prob)
        out.at[idx, 'decimal_price'] = f'{price:.2f}' if price is not None else 'N/A'
        out.at[idx, 'odds_label'] = f'{price:.2f}' if price is not None else 'N/A'
        out.at[idx, 'market_probability'] = market_prob
        out.at[idx, 'market_probability_label'] = _pct_label(market_prob)
        out.at[idx, 'edge'] = edge
        out.at[idx, 'edge_label'] = _pct_label(edge, signed=True)
        out.at[idx, 'value_rating'] = _value_rating(edge, odds_valid)
        out.at[idx, 'probability_audit'] = _audit_message(model_prob, market_prob, odds_valid)
        out.at[idx, 'odds_status'] = 'verified' if odds_valid else 'unavailable'
        out.at[idx, 'probability_source'] = 'model_probability' if model_prob is not None else ''
        if not odds_valid:
            out.at[idx, 'publish_ready'] = False
            out.at[idx, 'quality_flags'] = _append_flag(out.at[idx, 'quality_flags'] if 'quality_flags' in out.columns else '', ODDS_BLOCKER_TEXT if LANG == 'en' else ODDS_BLOCKER_TEXT_ES)
            if 'publish_status' in out.columns and 'official' in safe_text(out.at[idx, 'publish_status']).lower():
                out.at[idx, 'publish_status'] = 'Research / test' if LANG == 'en' else 'Investigación / prueba'
            out.at[idx, 'consumer_status'] = 'Model-only / odds unavailable' if LANG == 'en' else 'Solo modelo / sin cuotas'
        else:
            out.at[idx, 'consumer_status'] = 'Official Pick' if safe_text(out.at[idx, 'proof_id'] if 'proof_id' in out.columns else '') else 'Tracked Pick'
    return out


def render_cards_html(cards: pd.DataFrame, brand: BrandSettings) -> str:
    brand = brand.normalized()
    if cards is None or cards.empty:
        return '<p>No picks available.</p>' if brand.language == 'en' else '<p>No hay picks disponibles.</p>'
    labels = {
        'pick': 'Pick' if brand.language == 'en' else 'Pick',
        'odds': 'Odds' if brand.language == 'en' else 'Cuota',
        'model': 'Model Prob.' if brand.language == 'en' else 'Prob. modelo',
        'market': 'Market Prob.' if brand.language == 'en' else 'Prob. mercado',
        'edge': 'Edge',
        'status': 'Status' if brand.language == 'en' else 'Estado',
        'data': 'Data Check' if brand.language == 'en' else 'Control de datos',
        'value': 'Value' if brand.language == 'en' else 'Valor',
    }
    css = '''
    <style>
    .aba-premium-wrap{margin:1rem 0 1.5rem 0}.aba-premium-hero{border:1px solid rgba(125,125,125,.35);border-radius:24px;padding:1.1rem 1.25rem;margin-bottom:1rem;background:linear-gradient(135deg,rgba(255,255,255,.10),rgba(255,255,255,.035))}.aba-premium-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:1.05rem}.aba-premium-card{position:relative;overflow:hidden;border:1px solid rgba(125,125,125,.38);border-radius:24px;padding:1.05rem 1.08rem;background:radial-gradient(circle at top right,rgba(255,255,255,.12),rgba(255,255,255,.035) 38%,rgba(255,255,255,.025));box-shadow:0 10px 28px rgba(0,0,0,.18)}.aba-card-league{font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;opacity:.68;font-weight:750}.aba-verdict{display:inline-block;border:1px solid rgba(125,125,125,.45);border-radius:999px;padding:.22rem .55rem;font-size:.76rem;font-weight:800;white-space:nowrap}.aba-card-top{display:flex;justify-content:space-between;gap:.75rem;align-items:flex-start}.aba-premium-card h3{font-size:1.35rem;line-height:1.1;margin:.52rem 0 .7rem 0}.aba-recommendation{border-radius:18px;padding:.82rem .9rem;background:rgba(255,255,255,.07);margin:.4rem 0 .85rem 0}.aba-recommendation .label{font-size:.75rem;text-transform:uppercase;letter-spacing:.07em;opacity:.67;font-weight:850}.aba-recommendation .pick{font-size:1.12rem;font-weight:900;margin:.2rem 0 0 0}.aba-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.45rem;margin:.7rem 0}.aba-metric{border:1px solid rgba(125,125,125,.33);border-radius:16px;padding:.48rem .55rem}.aba-metric .k{font-size:.66rem;text-transform:uppercase;letter-spacing:.055em;opacity:.62;font-weight:800}.aba-metric .v{font-size:.9rem;font-weight:850;margin-top:.08rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.aba-meter{height:8px;border-radius:999px;background:rgba(125,125,125,.25);overflow:hidden;margin:.65rem 0 .75rem 0}.aba-meter span{display:block;height:100%;border-radius:999px;background:rgba(255,255,255,.58)}.aba-check-pill{display:inline-block;border:1px solid rgba(125,125,125,.35);border-radius:999px;padding:.26rem .58rem;font-size:.76rem;font-weight:750;opacity:.9;margin:.15rem}.aba-why{margin:.72rem 0 0 0;padding-left:1.15rem}.aba-why li{margin:.35rem 0;line-height:1.35}@media(max-width:760px){.aba-premium-grid{grid-template-columns:1fr}.aba-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>
    '''
    parts = [css, '<div class="aba-premium-wrap">', '<section class="aba-premium-hero">', f'<h2>{html.escape(brand.report_title or "Trend Report")}</h2>', f'<p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p>', f'<p>{html.escape(brand.workspace_id)}</p>', '</section>', '<div class="aba-premium-grid">']
    for _, row in cards.fillna('').iterrows():
        prob = _probability_float(row.get('model_probability'))
        width = 0 if prob is None else max(0, min(100, int(round(prob * 100))))
        bullets = [safe_text(row.get(f'bullet_{i}')) for i in range(1, 5) if safe_text(row.get(f'bullet_{i}'))]
        parts += [
            '<article class="aba-premium-card">',
            '<div class="aba-card-top">',
            f'<div class="aba-card-league">{html.escape(safe_text(row.get("sport")) or "Match")}</div>',
            f'<div class="aba-verdict">{html.escape(safe_text(row.get("consumer_status")) or safe_text(row.get("publish_status")))}</div>',
            '</div>',
            f'<h3>{html.escape(safe_text(row.get("event")))}</h3>',
            '<div class="aba-recommendation">',
            f'<div class="label">{html.escape(labels["pick"])}</div>',
            f'<div class="pick">{html.escape(safe_text(row.get("tendency") or row.get("prediction")))}</div>',
            '</div>',
            '<div class="aba-metrics">',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["odds"])}</div><div class="v">{html.escape(safe_text(row.get("decimal_price")) or "N/A")}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["model"])}</div><div class="v">{html.escape(safe_text(row.get("probability_label")) or "N/A")}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["market"])}</div><div class="v">{html.escape(safe_text(row.get("market_probability_label")) or "N/A")}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["edge"])}</div><div class="v">{html.escape(safe_text(row.get("edge_label")) or "N/A")}</div></div>',
            f'<div class="aba-metric"><div class="k">{html.escape(labels["status"])}</div><div class="v">{html.escape(safe_text(row.get("publish_status")))}</div></div>',
            '</div>',
            f'<div class="aba-meter"><span style="width:{width}%"></span></div>',
            f'<span class="aba-check-pill">{html.escape(labels["value"])}: {html.escape(safe_text(row.get("value_rating")))}</span>',
            f'<span class="aba-check-pill">{html.escape(labels["data"])}: {html.escape(safe_text(row.get("probability_audit")))}</span>',
        ]
        if bullets:
            parts.append('<ul class="aba-why">')
            for bullet in bullets[:3]:
                parts.append(f'<li>{html.escape(bullet)}</li>')
            parts.append('</ul>')
        proof = safe_text(row.get('proof_id'))
        if proof:
            parts.append(f'<p style="opacity:.72;font-size:.82rem">Proof ID: {html.escape(proof)}</p>')
        parts.append('</article>')
    parts += ['</div>', '</div>']
    disclaimer = brand.disclaimer or ('Informational content only. Results are not guaranteed.' if brand.language == 'en' else 'Contenido informativo. No garantiza resultados.')
    if disclaimer:
        parts.append(f'<p style="opacity:.72;font-size:.88rem">{html.escape(disclaimer)}</p>')
    return '\n'.join(parts)


st.title(t('title'))
st.caption(t('caption'))

with st.expander(t('input'), expanded=True):
    workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'), help=t('workspace_help'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    use_saved = st.checkbox(t('use_saved'), value=True)
    saved_source, saved_rows = rows_from_saved_sources(workspace_id) if use_saved else ('', pd.DataFrame())
    upload_source, upload_rows = read_uploaded_rows()
    parts = [frame for frame in [saved_rows, upload_rows] if frame is not None and not frame.empty]
    raw = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    sources = ', '.join([name for name in [saved_source, upload_source] if name]) or 'none'
    st.caption(f'{t("source")}: {sources}')

if raw.empty:
    st.warning(t('no_rows'))
    st.stop()

normalized = normalize_frame(raw)

with st.expander(t('brand'), expanded=True):
    c1, c2 = st.columns(2)
    brand_name = c1.text_input(t('brand_name'), value=st.session_state.get('consumer_report_brand_name', 'ABA Signal Pro'))
    tagline = c2.text_input(t('tagline'), value=st.session_state.get('consumer_report_tagline', 'Powered by Reparodynamics'))
    report_title = c1.text_input(t('report_title'), value=st.session_state.get('consumer_report_title', 'Reporte de Tendencias' if LANG == 'es' else 'Trend Report'))
    logo_url = c2.text_input(t('logo_url'), value=st.session_state.get('consumer_report_logo_url', ''))
    disclaimer_default = 'Contenido informativo. No garantiza resultados.' if LANG == 'es' else 'Informational content only. Results are not guaranteed.'
    disclaimer = st.text_area(t('disclaimer'), value=st.session_state.get('consumer_report_disclaimer', disclaimer_default), height=80)

for key, value in {
    'consumer_report_brand_name': brand_name,
    'consumer_report_tagline': tagline,
    'consumer_report_title': report_title,
    'consumer_report_logo_url': logo_url,
    'consumer_report_disclaimer': disclaimer,
}.items():
    st.session_state[key] = value

brand = BrandSettings(
    brand_name=brand_name,
    tagline=tagline,
    report_title=report_title,
    workspace_id=workspace_id,
    language=LANG,
    logo_url=logo_url,
    disclaimer=disclaimer,
)

with st.expander(t('filters'), expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    max_rows = c1.number_input(t('max_rows'), min_value=1, max_value=100, value=12, step=1)
    min_probability = c2.number_input(t('min_probability'), min_value=0.0, max_value=0.99, value=0.0, step=0.01)
    official_only = c3.checkbox(t('official_only'), value=False)
    pending_only = c4.checkbox(t('pending_only'), value=False)
    require_verified_odds = c5.checkbox(t('require_odds'), value=True)

    f1, f2, f3, f4 = st.columns(4)
    sport_filter = f1.multiselect(t('sport_filter'), unique_options(normalized, 'sport'))
    market_filter = f2.multiselect(t('market_filter'), unique_options(normalized, 'market_type'))
    status_values = sorted({safe_text(value) for value in status_series(normalized).tolist() if safe_text(value)})
    result_filter = f3.multiselect('Result status' if LANG == 'en' else 'Estado resultado', status_values)
    source_filter = f4.multiselect(t('source'), unique_options(normalized, 'source_file'))

filtered = normalized.copy()
filtered = filter_by_multiselect(filtered, 'sport', sport_filter)
filtered = filter_by_multiselect(filtered, 'market_type', market_filter)
filtered = filter_by_multiselect(filtered, 'source_file', source_filter)
if result_filter and not filtered.empty:
    statuses = status_series(filtered)
    filtered = filtered[statuses.isin(result_filter)].copy()

filtered, unavailable_count = sanitize_model_only_rows(filtered, require_verified_odds=require_verified_odds)
if unavailable_count:
    st.warning(t('odds_warning').format(count=unavailable_count))

report_rows = prepare_report_frame(
    filtered,
    min_probability=float(min_probability),
    official_only=bool(official_only),
    pending_only=bool(pending_only),
    max_rows=int(max_rows),
)
report_rows, selected_unavailable_count = sanitize_model_only_rows(report_rows, require_verified_odds=require_verified_odds)
cards = enrich_card_values(consumer_cards(report_rows, brand), report_rows)
st.session_state['consumer_report_latest_cards'] = cards.to_dict('records') if not cards.empty else []

proof_rows = int(cards.get('proof_id', pd.Series(dtype=str)).map(safe_text).ne('').sum()) if not cards.empty and 'proof_id' in cards.columns else 0
quality = report_quality_summary(cards)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(t('cards'), int(len(cards)))
m2.metric(t('avg_prob'), probability_metric(cards))
m3.metric(t('proof_rows'), proof_rows)
m4.metric(t('publish_ready'), quality['publish_ready'])
m5.metric(t('warnings'), quality['warnings'])
st.caption('Edge requires verified sportsbook odds. Missing or API-limited odds display as N/A and block publish-ready status.' if LANG == 'en' else 'El edge requiere cuotas verificadas. Si faltan cuotas o la API está limitada, se muestra N/A y no se puede publicar.')

markdown_report = render_magazine_markdown(cards, brand)
html_cards = render_cards_html(cards, brand)
html_report = render_magazine_html(cards, brand)
short_copy = render_short_copy(cards, brand)
json_feed = cards_to_json(cards, brand)
app_feed = cards_to_app_feed(cards, brand)
csv_payload = cards.to_csv(index=False) if not cards.empty else ''

safe_workspace = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in workspace_id)
tabs = st.tabs([t('cards_tab'), t('magazine_tab'), t('copy_tab'), t('feed_tab'), t('settings_tab'), t('diagnostics_tab')])

with tabs[0]:
    st.markdown(html_cards, unsafe_allow_html=True)
    download_link(t('download_cards_csv'), csv_payload, f'consumer_cards_{safe_workspace}.csv', 'text/csv')

with tabs[1]:
    st.markdown(html_report, unsafe_allow_html=True)
    st.text_area(t('markdown'), value=markdown_report, height=360)
    c1, c2 = st.columns(2)
    with c1:
        download_link(t('download_md'), markdown_report, f'magazine_report_{safe_workspace}.md', 'text/markdown')
    with c2:
        download_link(t('download_html'), html_report, f'magazine_report_{safe_workspace}.html', 'text/html')

with tabs[2]:
    st.text_area(t('short_copy'), value=short_copy, height=360)
    download_link(t('download_copy'), short_copy, f'report_copy_{safe_workspace}.txt', 'text/plain')

with tabs[3]:
    st.dataframe(cards, use_container_width=True, hide_index=True)
    st.text_area(t('json_feed'), value=json_feed, height=260)
    st.text_area(t('app_feed'), value=app_feed, height=260)
    c1, c2, c3 = st.columns(3)
    with c1:
        download_link(t('download_cards_csv'), csv_payload, f'consumer_cards_{safe_workspace}.csv', 'text/csv')
    with c2:
        download_link(t('download_json'), json_feed, f'consumer_feed_{safe_workspace}.json', 'application/json')
    with c3:
        download_link(t('download_app_json'), app_feed, f'app_feed_{safe_workspace}.json', 'application/json')

with tabs[4]:
    st.json(brand_payload(brand))
    st.caption(t('settings_json'))

with tabs[5]:
    st.json(quality)
    st.caption(t('quality_summary'))
    preview_cols = [
        'event', 'sport', 'market', 'prediction', 'decimal_price', 'odds_status', 'probability_label',
        'market_probability_label', 'edge_label', 'value_rating', 'consumer_status', 'probability_audit',
        'confidence', 'risk', 'publish_status', 'proof_id', 'quality_flags', 'lock_blockers',
    ]
    cols = [col for col in preview_cols if col in cards.columns]
    st.caption(t('preview_cols'))
    st.dataframe(cards[cols] if cols else cards, use_container_width=True, hide_index=True)
