from __future__ import annotations


def safe_float(value):
    try:
        return float(str(value).replace('%', '').replace(',', ''))
    except Exception:
        return None


def notes(row, language='en'):
    if str(language).startswith('es'):
        return ['Directa preferida', 'Solo combinar con otra ventaja verificada']
    return ['Straight preferred', 'Only combine with another verified edge']
