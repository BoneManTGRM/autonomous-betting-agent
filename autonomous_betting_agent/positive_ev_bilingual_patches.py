from __future__ import annotations

import re
from typing import Any, Mapping

from .value_math import assess_value_pick


SPANISH_TERMS = {
    'Light rain': 'lluvia ligera',
    'Rain': 'lluvia',
    'Weather': 'Clima',
    'Wind': 'Viento',
    'Location': 'Ubicación',
    'Temperature': 'Temperatura',
    'Humidity': 'Humedad',
    'Forecast': 'Pronóstico',
    'News checked': 'Noticias revisadas',
    'No recent related articles': 'sin artículos recientes relacionados',
    'No injury/lineup headline': 'sin titular de lesiones/alineación',
    'Philadelphia': 'Filadelfia',
    'United States of America': 'Estados Unidos',
    'United States': 'Estados Unidos',
    'USA': 'Estados Unidos',
}


def _pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def _spanish_text(value: Any) -> str:
    text = str(value or '')
    for source, target in SPANISH_TERMS.items():
        text = re.sub(rf'\b{re.escape(source)}\b', target, text, flags=re.IGNORECASE)
    text = text.replace('PA, Estados Unidos', 'Pennsylvania, Estados Unidos')
    return text


def _install_report_value_gate() -> None:
    try:
        from . import report_product_layer as rpl
    except Exception:
        return
    if getattr(rpl, '_aba_positive_ev_gate_v2', False):
        return

    rpl.VALUE_ES.update({
        'Confidence': 'Confianza',
        'Edge': 'Ventaja',
        'EV': 'VE',
        'Expected value': 'Valor esperado',
        'Units': 'Unidades',
        'Risk': 'Riesgo',
        'Watchlist': 'Lista de seguimiento',
        'Avoid': 'Evitar',
        'No bet': 'No apostar',
        'Weather': 'Clima',
        'Injury notes': 'Lesiones',
        'Team snapshots': 'Resumen de equipos',
        'Match notes': 'Notas del partido',
        'Parlay notes': 'Notas parlay',
        'Better price needed': 'Se necesita mejor momio',
        'No positive-EV picks found': 'No se encontraron jugadas con EV positivo a los momios actuales',
        'Current odds are too low': 'El momio actual es demasiado bajo',
        'This pick becomes playable only at target odds or better': 'Esta jugada solo es viable con el momio objetivo o mejor',
        'Why confidence and edge disagree': 'Por qué la confianza y la ventaja no coinciden',
    })
    rpl.COUNTRY_ES.update({'philadelphia': 'Filadelfia', 'united states': 'Estados Unidos', 'usa': 'Estados Unidos'})

    def classify_lane(*, odds_ok: bool, model_prob: float | None, edge: float | None, ev: float | None, tennis: bool = False) -> str:
        if tennis or not odds_ok or model_prob is None or edge is None or ev is None:
            return 'no_play'
        if model_prob >= 0.50 and edge > 0 and ev > 0:
            return 'best_play'
        if model_prob >= 0.50 and (edge > -0.025 or ev > -0.025):
            return 'watchlist'
        return 'no_play'

    def action_label(lane: str, language: str = 'en') -> str:
        if rpl.lang_code(language) == 'es':
            return {'best_play': 'Jugar +EV', 'watchlist': 'Lista de seguimiento', 'no_play': 'No jugar'}.get(lane, 'Revisar')
        return {'best_play': 'Positive-EV play', 'watchlist': 'Watchlist', 'no_play': 'No play'}.get(lane, 'Review')

    def market_read(odds_ok: bool, model_prob: float | None, market_prob: float | None, edge: float | None, language: str = 'en') -> str:
        es = rpl.lang_code(language) == 'es'
        if not odds_ok:
            return 'Momios faltantes, no verificados o vencidos.' if es else 'Odds are missing, unverified, or stale.'
        if model_prob is None:
            return 'Hay momio, pero falta probabilidad independiente del modelo.' if es else 'Price is available, but no independent model probability was found.'
        if market_prob is None or edge is None:
            return 'No se pudo calcular la ventaja.' if es else 'Edge could not be calculated.'
        if edge > 0:
            return f'Ventaja positiva: modelo {_pct(model_prob)} vs mercado {_pct(market_prob)}.' if es else f'Positive edge: model {_pct(model_prob)} vs market {_pct(market_prob)}.'
        return f'La selección puede ser probable, pero el momio está caro: modelo {_pct(model_prob)} vs mercado {_pct(market_prob)}.' if es else f'The pick may be likely, but the price is too expensive: model {_pct(model_prob)} vs market {_pct(market_prob)}.'

    def why_it_matters(row: Mapping[str, Any], odds_ok: bool, edge: float | None, language: str = 'en') -> str:
        es = rpl.lang_code(language) == 'es'
        assessment = assess_value_pick(row)
        if assessment.color == 'GREEN':
            return 'Pasa ventaja, VE, momio verificado y controles de seguridad.' if es else 'Passes edge, EV, verified odds, and safety checks.'
        if assessment.color == 'YELLOW':
            target = 'N/A' if assessment.target_odds is None else f'{assessment.target_odds:.2f}'
            return f'Probable, pero necesita mejor momio. Objetivo: {target}+.' if es else f'Likely, but it needs a better price. Target: {target}+.'
        if assessment.color == 'DATA WARNING':
            return 'Advertencia de datos: falta momio, verificación o frescura.' if es else 'Data warning: missing odds, verification, or freshness.'
        return 'El momio actual no da VE positivo; no debe ponerse verde.' if es else 'The current price does not create positive EV; it should not be green.'

    rpl.classify_lane = classify_lane
    rpl.action_label = action_label
    rpl.market_read = market_read
    rpl.why_it_matters = why_it_matters
    rpl._aba_positive_ev_gate_v2 = True


def _install_weather_compaction() -> None:
    try:
        from . import magazine_api_sources as mas
    except Exception:
        return
    if getattr(mas, '_aba_spanish_weather_split_v1', False):
        return

    def compact_weather_message(text: str) -> list[str]:
        value = re.sub(r'\s+', ' ', str(text or '')).strip()
        lower = value.lower()
        if lower.startswith('weather:'):
            value = 'WeatherAPI:' + value.split(':', 1)[1]
            lower = value.lower()
        if not lower.startswith('weatherapi:'):
            return [value]
        body = value.split(':', 1)[1].strip()
        location = ''
        match = re.search(r'\bLocation:\s*(.+)$', body, flags=re.IGNORECASE)
        if match:
            location = match.group(1).strip(' .')
            body = body[:match.start()].strip(' .')
        bits = [part.strip(' .') for part in re.split(r'[;,]', body) if part.strip(' .')]
        temperature = next((bit for bit in bits if re.search(r'-?\d+(?:\.\d+)?\s*°\s*[CF]\b', bit, re.IGNORECASE)), '')
        wind = next((bit for bit in bits if re.search(r'\bwind\b', bit, re.IGNORECASE)), '')
        condition = next((bit for bit in bits if bit not in {temperature, wind}), '')
        lines: list[str] = []
        if condition or temperature:
            lines.append('Weather: ' + ' · '.join(part for part in (condition, temperature.replace(' ', '')) if part) + '.')
        if wind:
            lines.append('Wind: ' + re.sub(r'^wind\s*', '', wind, flags=re.IGNORECASE).strip() + '.')
        if location:
            lines.append('Location: ' + mas._shorten_location(location) + '.')
        return lines or ['Weather checked; no live payload.']

    mas._compact_weather_message = compact_weather_message
    mas._aba_spanish_weather_split_v1 = True


def _install_magazine_spanish_layout() -> None:
    try:
        from . import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_spanish_match_notes_patch_v1', False):
        return

    original_tr = m._tr
    original_render = m.render_full_pick_magazine_page

    def tr(value: Any, lang: str) -> str:
        text = original_tr(value, lang)
        return _spanish_text(text) if lang == 'es' else text

    def repaint_match_notes(image: Any, pick: Any, lang: str) -> None:
        if lang != 'es':
            return
        draw = m.ImageDraw.Draw(image, 'RGBA')
        x, y, width, height = 354, 1178, 344, 175
        m._section(draw, x, y, width, height, 'MATCHUP NOTES', m.BLUE, lang)
        font = m._font(14)
        cursor = y + 68
        bottom = y + height - 14
        for item in (m._matchup_items(pick) or [])[:3]:
            lines = m._wrap_text_to_box(draw, tr(item, lang), font, width - 84, 2)
            if cursor + m._line_height(font) > bottom:
                break
            draw.ellipse((x + 24, cursor + 7, x + 36, cursor + 19), fill=m.BLUE)
            for line in lines:
                if cursor + m._line_height(font) > bottom:
                    break
                draw.text((x + 49, cursor), m._ellipsize_to_width(draw, line, font, width - 88), font=font, fill=m.TEXT)
                cursor += m._line_height(font)
            cursor += 5

    def render(pick: Any, *args: Any, **kwargs: Any):
        explicit = kwargs.get('language') if 'language' in kwargs else (args[10] if len(args) >= 11 else None)
        lang = m._lang(pick, explicit)
        image = original_render(pick, *args, **kwargs)
        repaint_match_notes(image, pick, lang)
        return image

    m._tr = tr
    m.render_full_pick_magazine_page = render
    m._aba_spanish_match_notes_patch_v1 = True


def install() -> None:
    _install_report_value_gate()
    _install_weather_compaction()
    _install_magazine_spanish_layout()
