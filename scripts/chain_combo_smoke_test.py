from __future__ import annotations

from autonomous_betting_agent import chain_notes


def main() -> None:
    assert chain_notes.classify({'risk': 'RESEARCH ONLY'}, 'en') == 'Research only'
    assert chain_notes.classify({'model_market_edge': '-0.02'}, 'en') == 'Do not combine'
    assert chain_notes.classify({'risk': 'THIN EDGE FAVORITE'}, 'en') == 'Straight only'
    assert chain_notes.classify({'model_probability': '0.62', 'model_market_edge': '0.04', 'expected_value': '0.06', 'risk': 'LOW', 'odds_source': 'verified'}, 'en') == 'Possible anchor leg'
    assert chain_notes.classify({'model_probability': '0.57', 'model_market_edge': '0.015', 'expected_value': '0.02', 'risk': 'MEDIUM', 'odds_source': 'verified'}, 'en') in {'Small combo only', 'Straight preferred'}
    spanish = ' '.join(chain_notes.notes({'risk': 'RESEARCH ONLY'}, 'es')).lower()
    for token in ('directa', 'combinada', 'momio', 'selección', 'verificación'):
        assert token in spanish
    warning = chain_notes.detect_correlation_warning({'event_name': 'A vs B'}, [{'event_name': 'A vs B'}], 'en')
    assert 'same-game' in warning.lower()
    print('chain combo smoke test passed')


if __name__ == '__main__':
    main()
