from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import expected_value, model_edge, robust_expected_value
from .row_normalizer import normalize_frame, probability_value, result_status, safe_text


@dataclass(frozen=True)
class BrandSettings:
    brand_name: str = 'ABA Signal Pro'
    tagline: str = 'Powered by Reparodynamics'
    report_title: str = ''
    workspace_id: str = 'test_01'
    language: str = 'es'
    logo_url: str = ''
    disclaimer: str = ''
    powered_by: str = 'ABA Signal Pro'

    def normalized(self) -> 'BrandSettings':
        return BrandSettings(
            brand_name=safe_text(self.brand_name) or 'ABA Signal Pro',
            tagline=safe_text(self.tagline) or 'Powered by Reparodynamics',
            report_title=safe_text(self.report_title),
            workspace_id=safe_text(self.workspace_id) or 'test_01',
            language=normalize_language(self.language),
            logo_url=safe_text(self.logo_url),
            disclaimer=safe_text(self.disclaimer),
            powered_by=safe_text(self.powered_by) or 'ABA Signal Pro',
        )


def normalize_language(value: Any) -> str:
    text = safe_text(value).lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def labels(language: str) -> dict[str, str]:
    if normalize_language(language) == 'es':
        return {
            'report': 'Reporte de Tendencias',
            'cards': 'Tarjetas para consumidores',
            'tendency': 'Tendencia',
            'market': 'Mercado',
            'odds': 'Cuota',
            'confidence': 'Confianza',
            'risk': 'Riesgo',
            'proof': 'Proof ID',
            'workspace': 'Workspace',
            'no_rows': 'No hay picks disponibles.',
            'disclaimer': 'Contenido informativo. No garantiza resultados.',
            'probability': 'Probabilidad',
            'status': 'Estado',
            'source': 'Fuente',
            'summary': 'Resumen',
            'official': 'Oficial',
            'research': 'Investigación',
            'unverified': 'Sin prueba',
            'quality': 'Calidad',
            'generated': 'Generado',
        }
    return {
        'report': 'Trend Report',
        'cards': 'Consumer Cards',
        'tendency': 'Pick',
        'market': 'Market',
        'odds': 'Odds',
        'confidence': 'Confidence',
        'risk': 'Risk',
        'proof': 'Proof ID',
        'workspace': 'Workspace',
        'no_rows': 'No picks available.',
        'disclaimer': 'Informational content only. Results are not guaranteed.',
        'probability': 'Probability',
        'status': 'Status',
        'source': 'Source',
        'summary': 'Summary',
        'official': 'Official',
        'research': 'Research',
        'unverified': 'Unverified',
        'quality': 'Quality',
        'generated': 'Generated',
    }


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _first_float(row: Mapping[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _safe_float(row.get(name))
        if value is not None:
            return value
    return None


def _pct(value: float | None) -> str:
    return '' if value is None else f'{value * 100:.1f}%'


def _decimal(value: Any) -> str:
    parsed = _safe_float(value)
    return safe_text(value) if parsed is None else f'{parsed:.2f}'


def _source_text(row: Mapping[str, Any]) -> str:
    return safe_text(row.get('bookmaker')) or safe_text(row.get('odds_source')) or safe_text(row.get('source_file'))


def _truthy(value: Any) -> bool:
    return safe_text(value).lower() in {'true', '1', 'yes', 'y', 'pass', 'passed'}


def _clean_list_text(values: list[str]) -> str:
    return '; '.join(item for item in values if safe_text(item))


def market_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    raw = safe_text(row.get('market_type') or row.get('market')).lower()
    line = safe_text(row.get('line_point') or row.get('point') or row.get('handicap'))
    prediction = safe_text(row.get('prediction')).lower()
    if raw in {'h2h', 'moneyline', 'ml', 'winner', 'ganador'}:
        label = 'Ganador' if lang == 'es' else 'Moneyline'
    elif 'spread' in raw or 'handicap' in raw or 'hándicap' in raw:
        label = 'Hándicap' if lang == 'es' else 'Spread'
    elif 'total' in raw or 'over' in raw or 'under' in raw or prediction.startswith(('over ', 'under ')):
        label = 'Total'
    elif 'btts' in raw or 'ambos' in raw:
        label = 'Ambos anotan' if lang == 'es' else 'Both teams to score'
    elif raw:
        label = raw.replace('_', ' ').title()
    else:
        label = 'Mercado' if lang == 'es' else 'Market'
    return f'{label} {line}'.strip() if line else label


def confidence_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    explicit = safe_text(row.get('public_confidence') or row.get('confidence_tier') or row.get('confidence'))
    if explicit:
        if lang == 'es':
            lookup = {
                'premium': 'Alta',
                'qualified': 'Calificada',
                'watch': 'En revisión',
                'watch only': 'En revisión',
                'research/test': 'Investigación',
                'strict ultra 80': 'Alta estricta',
                'high': 'Alta',
                'medium': 'Media',
                'low': 'Baja',
            }
            return lookup.get(explicit.lower(), explicit)
        return explicit
    probability = probability_value(row, 'model_probability')
    if probability is None:
        return 'Sin dato' if lang == 'es' else 'Unrated'
    if probability >= 0.70:
        return 'Alta+' if lang == 'es' else 'High+'
    if probability >= 0.62:
        return 'Alta' if lang == 'es' else 'High'
    if probability >= 0.57:
        return 'Media' if lang == 'es' else 'Medium'
    return 'Revisión' if lang == 'es' else 'Review'


def risk_label(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    probability = probability_value(row, 'model_probability')
    price = _first_float(row, ['decimal_price', 'average_price', 'best_price'])
    range_risk = _first_float(row, ['_price_range_risk', 'price_range_risk', 'price_range']) or 0.0
    research = safe_text(row.get('ledger_type')).lower().startswith('research') or safe_text(row.get('official_ev_pick')).lower() in {'false', '0', 'no'}
    if research:
        return 'Investigación' if lang == 'es' else 'Research'
    if range_risk > 0.50 or (price is not None and price >= 3.0) or (probability is not None and probability < 0.55):
        return 'Alto' if lang == 'es' else 'High'
    if range_risk > 0.25 or (price is not None and price >= 2.25) or (probability is not None and probability < 0.60):
        return 'Medio' if lang == 'es' else 'Medium'
    return 'Bajo' if lang == 'es' else 'Low'


def publish_status(row: Mapping[str, Any], language: str = 'en') -> str:
    lang = normalize_language(language)
    ledger = safe_text(row.get('ledger_type')).lower()
    official = _truthy(row.get('official_ev_pick')) or _truthy(row.get('official_lock_ready')) or 'official' in ledger
    research = ledger.startswith('research') or safe_text(row.get('official_ev_pick')).lower() in {'false', '0', 'no'}
    proof_id = safe_text(row.get('proof_id'))
    if official and proof_id:
        return 'Oficial con prueba' if lang == 'es' else 'Official proof'
    if official:
        return 'Oficial sin proof ID' if lang == 'es' else 'Official, missing proof ID'
    if research:
        return 'Investigación / prueba' if lang == 'es' else 'Research / test'
    if proof_id:
        return 'Bloqueado' if lang == 'es' else 'Locked'
    return 'Sin prueba' if lang == 'es' else 'Unverified'


def quality_flags(row: Mapping[str, Any], language: str = 'en') -> list[str]:
    lang = normalize_language(language)
    flags: list[str] = []
    if not safe_text(row.get('event')):
        flags.append('Falta evento' if lang == 'es' else 'Missing event')
    if not safe_text(row.get('prediction')):
        flags.append('Falta pick' if lang == 'es' else 'Missing pick')
    if probability_value(row, 'model_probability') is None:
        flags.append('Falta probabilidad' if lang == 'es' else 'Missing probability')
    price = _first_float(row, ['decimal_price', 'average_price', 'best_price'])
    if price is None or price <= 1.0:
        flags.append('Falta cuota válida' if lang == 'es' else 'Missing valid odds')
    if not safe_text(row.get('proof_id')):
        flags.append('Sin proof ID' if lang == 'es' else 'No proof ID')
    if safe_text(row.get('lock_blockers')):
        flags.append(('Bloqueadores: ' if lang == 'es' else 'Blockers: ') + safe_text(row.get('lock_blockers')))
    return flags


def _add_unique(items: list[str], value: str, limit: int) -> None:
    clean = ' '.join(safe_text(value).split())
    if clean and clean.lower() not in {item.lower() for item in items} and len(items) < limit:
        items.append(clean)


def _split_reason(value: Any) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [' '.join(chunk.strip(' .').split()) for chunk in text.replace(' | ', '; ').split(';') if chunk.strip()]


def explain_pick(row: Mapping[str, Any], language: str = 'en', max_bullets: int = 4) -> list[str]:
    lang = normalize_language(language)
    prediction = safe_text(row.get('prediction')) or ('la selección' if lang == 'es' else 'the selection')
    probability = probability_value(row, 'model_probability')
    edge = model_edge(row)
    ev = expected_value(row)
    robust_ev = robust_expected_value(row)
    price = _first_float(row, ['decimal_price', 'average_price', 'best_price'])
    source = _source_text(row)
    proof_id = safe_text(row.get('proof_id'))
    decision = safe_text(row.get('agent_decision') or row.get('decision')).replace('_', ' ')
    bullets: list[str] = []

    if lang == 'es':
        if probability is not None:
            _add_unique(bullets, f'El modelo favorece {prediction} con probabilidad estimada de {_pct(probability)}.', max_bullets)
        if edge is not None:
            _add_unique(bullets, f'Ventaja estimada frente a la cuota: {edge * 100:.1f}%.', max_bullets) if edge > 0 else _add_unique(bullets, 'Señal sin ventaja de cuota clara; revisar antes de publicar como oficial.', max_bullets)
        if ev is not None:
            _add_unique(bullets, f'EV estimado por unidad: {ev * 100:.1f}%.', max_bullets)
        if robust_ev is not None and robust_ev > 0:
            _add_unique(bullets, f'EV conservador positivo: {robust_ev * 100:.1f}%.', max_bullets)
        if price is not None:
            _add_unique(bullets, f'Cuota registrada: {_decimal(price)}' + (f' vía {source}.' if source else '.'), max_bullets)
        if decision:
            _add_unique(bullets, f'Decisión interna: {decision}.', max_bullets)
        if proof_id:
            _add_unique(bullets, f'Pick bloqueado con {proof_id}.', max_bullets)
    else:
        if probability is not None:
            _add_unique(bullets, f'The model favors {prediction} with an estimated probability of {_pct(probability)}.', max_bullets)
        if edge is not None:
            _add_unique(bullets, f'Estimated edge versus the listed price: {edge * 100:.1f}%.', max_bullets) if edge > 0 else _add_unique(bullets, 'No clear price edge; review before publishing as official.', max_bullets)
        if ev is not None:
            _add_unique(bullets, f'Estimated EV per unit: {ev * 100:.1f}%.', max_bullets)
        if robust_ev is not None and robust_ev > 0:
            _add_unique(bullets, f'Conservative EV is positive: {robust_ev * 100:.1f}%.', max_bullets)
        if price is not None:
            _add_unique(bullets, f'Logged price: {_decimal(price)}' + (f' via {source}.' if source else '.'), max_bullets)
        if decision:
            _add_unique(bullets, f'Internal decision: {decision}.', max_bullets)
        if proof_id:
            _add_unique(bullets, f'Pick locked with {proof_id}.', max_bullets)

    for reason in _split_reason(row.get('public_reason')):
        _add_unique(bullets, reason + '.', max_bullets)
    if not bullets:
        _add_unique(bullets, 'Revisión de modelo disponible; falta contexto público.' if lang == 'es' else 'Model review available; public context is limited.', max_bullets)
    return bullets[:max_bullets]


def _sort_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    probability = pd.to_numeric(out.get('model_probability', pd.Series(index=out.index, dtype=float)), errors='coerce')
    probability = probability.where(probability <= 1.0, probability / 100.0)
    agent = pd.to_numeric(out.get('agent_score', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0) / 100.0
    scanner = pd.to_numeric(out.get('scanner_strength_score', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0) / 100.0
    edge = pd.to_numeric(out.get('model_edge', pd.Series(index=out.index, dtype=float)), errors='coerce').fillna(0.0)
    out['_consumer_sort_score'] = probability.fillna(0.0) * 0.55 + agent * 0.18 + scanner * 0.12 + edge.clip(-0.20, 0.30) * 0.15
    return out.sort_values('_consumer_sort_score', ascending=False).drop(columns=['_consumer_sort_score'], errors='ignore')


def prepare_report_frame(
    frame: pd.DataFrame | list[dict[str, Any]],
    *,
    min_probability: float = 0.0,
    official_only: bool = False,
    pending_only: bool = False,
    max_rows: int = 12,
) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    out = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if out.empty:
        return pd.DataFrame()
    probabilities = pd.to_numeric(out.get('model_probability', pd.Series(index=out.index, dtype=float)), errors='coerce')
    probabilities = probabilities.where(probabilities <= 1.0, probabilities / 100.0)
    if min_probability > 0:
        out = out[probabilities.reindex(out.index).fillna(0.0) >= float(min_probability)].copy()
    if official_only and not out.empty:
        official = out.get('official_ev_pick', pd.Series(False, index=out.index)).astype(str).str.lower().isin({'true', '1', 'yes', 'y'})
        ready = out.get('official_lock_ready', pd.Series(False, index=out.index)).astype(str).str.lower().isin({'true', '1', 'yes', 'y'})
        ledger = out.get('ledger_type', pd.Series('', index=out.index)).astype(str).str.lower().str.contains('official')
        out = out[official | ready | ledger].copy()
    if pending_only and not out.empty:
        statuses = out.apply(lambda row: result_status(row.to_dict()), axis=1)
        out = out[statuses.isin({'pending', 'scheduled', 'live', ''})].copy()
    out = _sort_frame(out)
    return out.head(int(max_rows)).copy() if max_rows > 0 else out


def consumer_cards(frame: pd.DataFrame | list[dict[str, Any]], brand: BrandSettings | None = None, *, max_bullets: int = 4) -> pd.DataFrame:
    brand = (brand or BrandSettings()).normalized()
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    for item in normalized.to_dict('records'):
        bullets = explain_pick(item, language=brand.language, max_bullets=max_bullets)
        probability = probability_value(item, 'model_probability')
        flags = quality_flags(item, brand.language)
        card = {
            'workspace_id': brand.workspace_id,
            'brand_name': brand.brand_name,
            'sport': safe_text(item.get('sport')),
            'event': safe_text(item.get('event')),
            'market': market_label(item, brand.language),
            'prediction': safe_text(item.get('prediction')),
            'tendency': safe_text(item.get('prediction')),
            'decimal_price': _decimal(item.get('decimal_price')),
            'odds_label': _decimal(item.get('decimal_price')) or '-',
            'confidence': confidence_label(item, brand.language),
            'risk': risk_label(item, brand.language),
            'publish_status': publish_status(item, brand.language),
            'model_probability': probability,
            'probability_label': _pct(probability),
            'proof_id': safe_text(item.get('proof_id')),
            'proof_status': safe_text(item.get('proof_status')),
            'result_status': result_status(item),
            'source': _source_text(item),
            'quality_flags': _clean_list_text(flags),
            'publish_ready': not flags or flags == ['Sin proof ID'] or flags == ['No proof ID'],
            'short_summary': bullets[0] if bullets else '',
            'report_language': normalize_language(brand.language),
            'generated_at_utc': generated,
        }
        for index in range(max_bullets):
            card[f'bullet_{index + 1}'] = bullets[index] if index < len(bullets) else ''
        rows.append(card)
    return pd.DataFrame(rows)


def brand_payload(brand: BrandSettings) -> dict[str, str]:
    return {key: str(value) for key, value in asdict(brand.normalized()).items()}


def cards_to_json(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    payload = {
        'version': 'consumer_report_v2',
        'brand': brand_payload(brand),
        'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'cards': cards.fillna('').to_dict('records') if cards is not None and not cards.empty else [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def cards_to_app_feed(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    items: list[dict[str, Any]] = []
    if cards is not None and not cards.empty:
        for _, row in cards.fillna('').iterrows():
            items.append({
                'id': safe_text(row.get('proof_id')) or f"{safe_text(row.get('event'))}:{safe_text(row.get('market'))}:{safe_text(row.get('prediction'))}",
                'workspace_id': safe_text(row.get('workspace_id')),
                'sport': safe_text(row.get('sport')),
                'event': safe_text(row.get('event')),
                'market': safe_text(row.get('market')),
                'pick': safe_text(row.get('prediction') or row.get('tendency')),
                'odds': safe_text(row.get('decimal_price')),
                'confidence': safe_text(row.get('confidence')),
                'risk': safe_text(row.get('risk')),
                'status': safe_text(row.get('publish_status')),
                'proof_id': safe_text(row.get('proof_id')),
                'probability': row.get('model_probability'),
                'summary': safe_text(row.get('short_summary')),
                'bullets': [safe_text(row.get(f'bullet_{index}')) for index in range(1, 5) if safe_text(row.get(f'bullet_{index}'))],
            })
    payload = {
        'version': 'app_feed_v1',
        'brand': brand_payload(brand),
        'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'items': items,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def report_quality_summary(cards: pd.DataFrame) -> dict[str, Any]:
    if cards is None or cards.empty:
        return {'cards': 0, 'publish_ready': 0, 'with_proof': 0, 'warnings': 0}
    flags = cards.get('quality_flags', pd.Series('', index=cards.index)).fillna('').astype(str)
    ready = cards.get('publish_ready', pd.Series(False, index=cards.index)).astype(str).str.lower().isin({'true', '1', 'yes'})
    proof = cards.get('proof_id', pd.Series('', index=cards.index)).fillna('').astype(str).str.strip().ne('')
    return {
        'cards': int(len(cards)),
        'publish_ready': int(ready.sum()),
        'with_proof': int(proof.sum()),
        'warnings': int(flags.str.strip().ne('').sum()),
    }


def render_short_copy(cards: pd.DataFrame, brand: BrandSettings | None = None, *, max_picks: int = 8) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    if cards is None or cards.empty:
        return lab['no_rows']
    title = brand.report_title or lab['report']
    lines = [title, f'{brand.brand_name} — {brand.tagline}', '']
    view = cards.fillna('').head(max_picks)
    for _, row in view.iterrows():
        pick = safe_text(row.get('tendency') or row.get('prediction'))
        event = safe_text(row.get('event'))
        market = safe_text(row.get('market'))
        odds = safe_text(row.get('decimal_price')) or '-'
        confidence = safe_text(row.get('confidence'))
        risk = safe_text(row.get('risk'))
        proof = safe_text(row.get('proof_id'))
        lines.append(f'{event}')
        lines.append(f"{lab['tendency']}: {pick} | {lab['market']}: {market} | {lab['odds']}: {odds}")
        lines.append(f"{lab['confidence']}: {confidence} | {lab['risk']}: {risk}" + (f" | {lab['proof']}: {proof}" if proof else ''))
        summary = safe_text(row.get('short_summary'))
        if summary:
            lines.append(summary)
        lines.append('')
    disclaimer = brand.disclaimer or lab['disclaimer']
    if disclaimer:
        lines.append(disclaimer)
    return '\n'.join(lines).strip()


def render_magazine_markdown(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    if cards is None or cards.empty:
        return lab['no_rows']
    title = brand.report_title or lab['report']
    lines = [
        f'# {title}',
        f'**{brand.brand_name}** — {brand.tagline}',
        f"**{lab['workspace']}:** {brand.workspace_id}",
        '',
    ]
    for _, row in cards.fillna('').iterrows():
        heading = f"{safe_text(row.get('sport'))}: {safe_text(row.get('event'))}" if safe_text(row.get('sport')) else safe_text(row.get('event'))
        lines += [
            f'## {heading}',
            f"**{lab['tendency']}:** {safe_text(row.get('tendency') or row.get('prediction'))}",
            f"**{lab['market']}:** {safe_text(row.get('market'))} | **{lab['odds']}:** {safe_text(row.get('decimal_price')) or '-'} | **{lab['confidence']}:** {safe_text(row.get('confidence'))} | **{lab['risk']}:** {safe_text(row.get('risk'))}",
        ]
        probability = safe_text(row.get('probability_label'))
        status = safe_text(row.get('publish_status'))
        if probability or status:
            lines.append(f"**{lab['probability']}:** {probability or '-'} | **{lab['status']}:** {status or '-'}")
        for index in range(1, 5):
            bullet = safe_text(row.get(f'bullet_{index}'))
            if bullet:
                lines.append(f'- {bullet}')
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            lines.append(f"**{lab['proof']}:** {proof_id}")
        quality = safe_text(row.get('quality_flags'))
        if quality:
            lines.append(f"**{lab['quality']}:** {quality}")
        lines.append('')
    disclaimer = brand.disclaimer or lab['disclaimer']
    if disclaimer:
        lines += ['---', disclaimer]
    return '\n'.join(lines).strip() + '\n'


def _card_bullets_html(row: Mapping[str, Any]) -> str:
    items = [f'<li>{html.escape(safe_text(row.get(f"bullet_{index}")))}</li>' for index in range(1, 5) if safe_text(row.get(f'bullet_{index}'))]
    return '<ul>' + ''.join(items) + '</ul>' if items else ''


def render_consumer_cards_html(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    if cards is None or cards.empty:
        return f'<p>{html.escape(lab["no_rows"])}</p>'
    title = brand.report_title or lab['cards']
    parts = [
        '<style>.aba-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin:1rem 0}.aba-card{border:1px solid rgba(125,125,125,.35);border-radius:18px;padding:1rem;background:rgba(255,255,255,.045)}.aba-card h3{margin:.35rem 0 .55rem 0}.aba-pill{display:inline-block;border:1px solid rgba(125,125,125,.45);border-radius:999px;padding:.18rem .55rem;margin:.1rem .2rem .1rem 0;font-size:.78rem}.aba-card .pick{font-size:1.15rem;font-weight:800;margin:.45rem 0}.aba-muted{opacity:.74;font-size:.9rem}.aba-warning{border-color:rgba(255,180,80,.7)}</style>',
        f'<h2>{html.escape(title)}</h2>',
        f'<p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p>',
        '<div class="aba-card-grid">',
    ]
    for _, row in cards.fillna('').iterrows():
        proof_id = safe_text(row.get('proof_id'))
        proof = f'<span class="aba-pill">{html.escape(lab["proof"])}: {html.escape(proof_id)}</span>' if proof_id else ''
        quality = safe_text(row.get('quality_flags'))
        quality_html = f'<p class="aba-muted"><strong>{html.escape(lab["quality"])}:</strong> {html.escape(quality)}</p>' if quality else ''
        card_class = 'aba-card aba-warning' if quality else 'aba-card'
        parts += [
            f'<article class="{card_class}">',
            f'<div class="aba-muted">{html.escape(safe_text(row.get("sport")))} · {html.escape(safe_text(row.get("market")))}</div>',
            f'<h3>{html.escape(safe_text(row.get("event")))}</h3>',
            f'<div class="pick">{html.escape(lab["tendency"])}: {html.escape(safe_text(row.get("tendency") or row.get("prediction")))}</div>',
            f'<span class="aba-pill">{html.escape(lab["odds"])}: {html.escape(safe_text(row.get("decimal_price")) or "-")}</span>',
            f'<span class="aba-pill">{html.escape(lab["probability"])}: {html.escape(safe_text(row.get("probability_label")) or "-")}</span>',
            f'<span class="aba-pill">{html.escape(lab["confidence"])}: {html.escape(safe_text(row.get("confidence")))}</span>',
            f'<span class="aba-pill">{html.escape(lab["risk"])}: {html.escape(safe_text(row.get("risk")))}</span>',
            f'<span class="aba-pill">{html.escape(lab["status"])}: {html.escape(safe_text(row.get("publish_status")))}</span>',
            proof,
            _card_bullets_html(row),
            quality_html,
            '</article>',
        ]
    parts.append('</div>')
    disclaimer = brand.disclaimer or lab['disclaimer']
    if disclaimer:
        parts.append(f'<p>{html.escape(disclaimer)}</p>')
    return '\n'.join(parts)


def render_magazine_html(cards: pd.DataFrame, brand: BrandSettings | None = None) -> str:
    brand = (brand or BrandSettings()).normalized()
    lab = labels(brand.language)
    title = brand.report_title or lab['report']
    if cards is None or cards.empty:
        return f'<p>{html.escape(lab["no_rows"])}</p>'
    logo = f'<img src="{html.escape(brand.logo_url)}" alt="logo" style="max-height:54px">' if brand.logo_url else ''
    parts = [
        '<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:Georgia,serif;margin:0;background:#f3eadc;color:#1f1a14}.page{min-height:920px;padding:48px 58px;border-bottom:6px solid #1f1a14;page-break-after:always;box-sizing:border-box}.brand{display:flex;justify-content:space-between;align-items:center}.pill{display:inline-block;border:1px solid #1f1a14;border-radius:999px;padding:.28rem .7rem;margin:.15rem .25rem .15rem 0}.pick{font-size:2rem;font-weight:800;margin:1.8rem 0 .6rem 0}li{margin:.45rem 0;font-size:1.08rem;line-height:1.35}.muted{opacity:.72}</style></head><body>',
        '<section class="page"><div class="brand"><div>',
        f'<h1>{html.escape(title)}</h1><p><strong>{html.escape(brand.brand_name)}</strong> — {html.escape(brand.tagline)}</p><p>{html.escape(lab["workspace"])}: {html.escape(brand.workspace_id)}</p>',
        f'</div>{logo}</div></section>',
    ]
    for _, row in cards.fillna('').iterrows():
        parts += [
            '<section class="page">',
            f'<p class="muted">{html.escape(safe_text(row.get("sport")))}</p>',
            f'<h2>{html.escape(safe_text(row.get("event")))}</h2>',
            f'<span class="pill">{html.escape(lab["market"])}: {html.escape(safe_text(row.get("market")))}</span>',
            f'<span class="pill">{html.escape(lab["confidence"])}: {html.escape(safe_text(row.get("confidence")))}</span>',
            f'<span class="pill">{html.escape(lab["risk"])}: {html.escape(safe_text(row.get("risk")))}</span>',
            f'<span class="pill">{html.escape(lab["probability"])}: {html.escape(safe_text(row.get("probability_label")) or "-")}</span>',
            f'<div class="pick">{html.escape(lab["tendency"])}<br>{html.escape(safe_text(row.get("tendency") or row.get("prediction")))}</div>',
            f'<p><strong>{html.escape(lab["odds"])}:</strong> {html.escape(safe_text(row.get("decimal_price")) or "-")}</p>',
            _card_bullets_html(row),
        ]
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            parts.append(f'<p><strong>{html.escape(lab["proof"])}:</strong> {html.escape(proof_id)}</p>')
        status = safe_text(row.get('publish_status'))
        if status:
            parts.append(f'<p class="muted"><strong>{html.escape(lab["status"])}:</strong> {html.escape(status)}</p>')
        parts.append('</section>')
    parts.append(f'<section class="page"><h2>{html.escape(brand.brand_name)}</h2><p>{html.escape(brand.disclaimer or lab["disclaimer"])}</p></section></body></html>')
    return '\n'.join(parts)
