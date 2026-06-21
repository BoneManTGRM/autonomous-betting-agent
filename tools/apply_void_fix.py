from pathlib import Path

path = Path('autonomous_betting_agent/row_normalizer.py')
text = path.read_text()
old = "    'void': 'void', 'push': 'void', 'cancelled': 'void', 'canceled': 'void', 'postponed': 'void', 'abandoned': 'void',\n"
new = "    'void': 'void', 'push': 'void', 'pushed': 'void', 'draw_no_bet_push': 'void', 'cancelled': 'void', 'canceled': 'void', 'cancelation': 'void', 'cancellation': 'void', 'postponed': 'void', 'abandoned': 'void', 'no_action': 'void',\n"
if old not in text:
    raise SystemExit('Expected line not found; the file may already be updated.')
path.write_text(text.replace(old, new))
print('Done')
