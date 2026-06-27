from pathlib import Path

pkg = 'autonomous_' + 'betting_agent'
path = Path(pkg) / 'magazine_book_export.py'
text = path.read_text(encoding='utf-8')
old = '    ret' + 'urn [' + '_tr(item, lang) for item in _items_' + 'from_keys(row, keys, fallback, limit)]\n'
new_lines = [
    '    data = _row(row)',
    '    values: list[str] = []',
    '    for key in keys:',
    '        values.extend(_split(data.get(key)))',
    '    if not values:',
    '        values = list(fallback)',
    '    return [_tr(item, lang) for item in values[:limit]]',
]
new = '\n'.join(new_lines) + '\n'
if old not in text:
    raise SystemExit('target not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
