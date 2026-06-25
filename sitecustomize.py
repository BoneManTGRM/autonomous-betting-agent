from __future__ import annotations

import builtins
import os
import re
from contextlib import contextmanager


def get_secret(*names: str) -> str:
    """Read a secret from Streamlit secrets first, then environment variables."""
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _normalize_magazine_language(value: object = None) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def _active_magazine_language(row: object = None, explicit: object = None) -> str:
    if explicit:
        return _normalize_magazine_language(explicit)
    try:
        if isinstance(row, dict):
            for key in ('report_language', 'language', 'lang'):
                if row.get(key):
                    return _normalize_magazine_language(row.get(key))
    except Exception:
        pass
    try:
        import streamlit as st
        for key in ('aba_global_language', 'report_studio_language', 'aba_radio_report_studio_language'):
            value = st.session_state.get(key)
            if value:
                return _normalize_magazine_language(value)
    except Exception:
        pass
    return 'en'


STATIC_TRANSLATIONS = {
    'en': {
        'TENDENCIA': 'TREND',
    },
    'es': {
        'DAILY SPORTS ANALYSIS': 'ANÁLISIS DEPORTIVO DIARIO',
        'TREND': 'TENDENCIA',
        'ODDS': 'CUOTA',
        'CONFIDENCE': 'CONFIANZA',
        'EDGE': 'VENTAJA',
        'UNITS': 'UNIDADES',
        'RISK': 'RIESGO',
        'MARKET': 'MERCADO',
        'WHY WE PICKED IT': 'POR QUÉ LO ELEGIMOS',
        'PRO BETTOR EVIDENCE': 'EVIDENCIA PRO',
        'TEAM SNAPSHOTS': 'RESUMEN EQUIPOS',
        'PLAYER / INJURY NOTES': 'JUGADORES / LESIONES',
        'RISK DESK': 'RIESGO',
        'MATCHUP NOTES': 'NOTAS DEL PARTIDO',
        'CHAIN BETTING NOTES': 'NOTAS PARLAY',
        'RECOMMENDATION': 'RECOMENDACIÓN',
        'SOURCE:': 'FUENTE:',
        'BOOK:': 'CASA:',
        'LINE:': 'LÍNEA:',
        'PUBLIC:': 'PÚBLICO:',
        'Context unavailable.': 'Contexto no disponible.',
        'Confirm price and lineup news before entry.': 'Confirma precio y alineaciones antes de entrar.',
        'Data not available from uploaded row': 'Datos del equipo no disponibles en la fila cargada',
        'Player data not available in uploaded row': 'Datos de jugadores no disponibles en la fila cargada',
        'Use team form, injuries, and market movement before publishing.': 'Usa forma del equipo, lesiones y movimiento del mercado antes de publicar.',
        'Confirm lineup/injury news before placing the bet.': 'Confirma alineaciones y lesiones antes de apostar.',
        'Market and model evidence support this read.': 'El mercado y el modelo respaldan esta lectura.',
        'Recheck odds before entry.': 'Revisa la cuota antes de entrar.',
        'Avoid if major lineup/weather news changes.': 'Evita si cambian alineaciones, clima o noticias clave.',
        'Confirm venue and start time.': 'Confirma sede y hora de inicio.',
        'Recheck market movement before publishing.': 'Revisa el movimiento del mercado antes de publicar.',
        'Better as an individual straight analysis unless another verified edge exists.': 'Mejor como análisis individual salvo que exista otra ventaja verificada.',
        'Do not add weak legs just to increase payout.': 'No agregues selecciones débiles solo para subir el pago.',
        'Use only if the line remains playable and key news does not change.': 'Usar solo si la línea sigue jugable y no cambia la información clave.',
        'No guarantees. Bet responsibly. This analysis is for informational purposes only.': 'No garantizamos resultados. Apuesta responsablemente. Este análisis es solo informativo.',
        'VOLUME OK': 'VOLUMEN OK',
        'VOLUME_OK': 'VOLUMEN OK',
        'LOW': 'BAJO',
        'MEDIUM': 'MEDIO',
        'HIGH': 'ALTO',
        'TOTALS': 'TOTALES',
        'MONEYLINE': 'GANADOR',
        'SPREAD': 'HÁNDICAP',
        'PLAY SMALL': 'JUGAR PEQUEÑO',
        'PLAY STANDARD': 'JUGAR NORMAL',
        'NO PLAY': 'NO JUGAR',
        'GAME TOTAL: OVER 2.5': 'TOTAL DEL PARTIDO: MÁS DE 2.5',
        'GAME TOTAL: OVER 2': 'TOTAL DEL PARTIDO: MÁS DE 2',
    },
}


def _translate_magazine_text(value: object, language: str) -> object:
    if not isinstance(value, str):
        return value
    text = value
    if language == 'en':
        return STATIC_TRANSLATIONS['en'].get(text, text)

    if text in STATIC_TRANSLATIONS['es']:
        return STATIC_TRANSLATIONS['es'][text]
    if text.startswith('PAGE ') and ' OF ' in text:
        return text.replace('PAGE ', 'PÁGINA ', 1).replace(' OF ', ' DE ')
    if text.endswith(' REGULAR SEASON'):
        return text.replace(' REGULAR SEASON', ' TEMPORADA REGULAR')
    if text.startswith('Risk status:'):
        return text.replace('Risk status:', 'Estado de riesgo:').replace('VOLUME OK', 'VOLUMEN OK').replace('VOLUME_OK', 'VOLUMEN OK')
    if text.startswith('Model projects '):
        return re.sub(r'Model projects ([^ ]+) probability for (.+)\.', r'El modelo proyecta \1 de probabilidad para \2.', text)
    if text.startswith('Market-implied probability checks at '):
        return text.replace('Market-implied probability checks at ', 'La probabilidad implícita del mercado es ')
    if text.startswith('Measured edge:'):
        return text.replace('Measured edge:', 'Ventaja medida:')
    if text.startswith('Expected value:'):
        return text.replace('Expected value:', 'Valor esperado:')
    text = re.sub(r'\bGAME TOTAL\b', 'TOTAL DEL PARTIDO', text)
    text = re.sub(r'\bOVER\b', 'MÁS DE', text)
    text = re.sub(r'\bUNDER\b', 'MENOS DE', text)
    return text


@contextmanager
def _magazine_language_context(language: str):
    previous = getattr(builtins, '_aba_magazine_language', None)
    builtins._aba_magazine_language = language
    try:
        yield
    finally:
        if previous is None:
            try:
                delattr(builtins, '_aba_magazine_language')
            except Exception:
                pass
        else:
            builtins._aba_magazine_language = previous


def _patch_pillow_text_for_magazine() -> None:
    try:
        from PIL import ImageDraw
    except Exception:
        return
    if getattr(ImageDraw.ImageDraw.text, '_aba_magazine_text_patch', False):
        return
    original_text = ImageDraw.ImageDraw.text

    def text_with_magazine_language(self, xy, text, *args, **kwargs):
        language = getattr(builtins, '_aba_magazine_language', None)
        if language:
            text = _translate_magazine_text(text, language)
        return original_text(self, xy, text, *args, **kwargs)

    text_with_magazine_language._aba_magazine_text_patch = True
    ImageDraw.ImageDraw.text = text_with_magazine_language


def _patch_magazine_renderer() -> None:
    try:
        from autonomous_betting_agent import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_language_patch_applied', False):
        return

    original_page = m.render_full_pick_magazine_page
    original_png = m.render_full_pick_magazine_page_png
    original_pages = m.render_full_magazine_book_pages
    original_book_png = m.render_full_magazine_book_png
    original_pdf = m.render_full_magazine_book_pdf
    original_zip = m.render_full_magazine_zip

    def page_with_language(pick, *args, **kwargs):
        language = _active_magazine_language(pick, kwargs.pop('language', None))
        with _magazine_language_context(language):
            return original_page(pick, *args, **kwargs)

    def png_with_language(pick, *args, **kwargs):
        language = _active_magazine_language(pick, kwargs.pop('language', None))
        with _magazine_language_context(language):
            return original_png(pick, *args, **kwargs)

    def pages_with_language(picks, *args, **kwargs):
        language = _active_magazine_language(None, kwargs.pop('language', None))
        rows = list(picks)
        if language:
            for row in rows:
                if isinstance(row, dict):
                    row.setdefault('report_language', language)
        with _magazine_language_context(language):
            return original_pages(rows, *args, **kwargs)

    def book_png_with_language(picks, *args, **kwargs):
        language = _active_magazine_language(None, kwargs.pop('language', None))
        rows = list(picks)
        for row in rows:
            if isinstance(row, dict):
                row.setdefault('report_language', language)
        with _magazine_language_context(language):
            return original_book_png(rows, *args, **kwargs)

    def pdf_with_language(picks, *args, **kwargs):
        language = _active_magazine_language(None, kwargs.pop('language', None))
        rows = list(picks)
        for row in rows:
            if isinstance(row, dict):
                row.setdefault('report_language', language)
        with _magazine_language_context(language):
            return original_pdf(rows, *args, **kwargs)

    def zip_with_language(picks, *args, **kwargs):
        language = _active_magazine_language(None, kwargs.pop('language', None))
        rows = list(picks)
        for row in rows:
            if isinstance(row, dict):
                row.setdefault('report_language', language)
        with _magazine_language_context(language):
            return original_zip(rows, *args, **kwargs)

    m.render_full_pick_magazine_page = page_with_language
    m.render_full_pick_magazine_page_png = png_with_language
    m.render_full_magazine_book_pages = pages_with_language
    m.render_full_magazine_book_png = book_png_with_language
    m.render_full_magazine_book_pdf = pdf_with_language
    m.render_full_magazine_zip = zip_with_language
    m._aba_language_patch_applied = True


_patch_pillow_text_for_magazine()
_patch_magazine_renderer()
