from __future__ import annotations

import os

from autonomous_betting_agent.sports_context import ApiMmaContextProvider, build_context, sport_family


class MockMmaProvider(ApiMmaContextProvider):
    def _api_key(self) -> str:
        return 'test-key'

    def _api_get(self, path, params):
        if path == '/fights':
            return {'response': [{'fighters': [{'name': 'Charles Johnson'}, {'name': 'Asu Almabaev'}], 'venue': 'Mock Arena', 'promotion': 'Mock MMA'}]}
        if path == '/fighters' and params.get('search') == 'Charles Johnson':
            return {'response': [{'name': 'Charles Johnson', 'wins': 17, 'losses': 6, 'stance': 'Orthodox', 'reach': '70 in', 'recent_fights': 'Won 3 of last 5'}]}
        if path == '/fighters' and params.get('search') == 'Asu Almabaev':
            return {'response': [{'name': 'Asu Almabaev', 'wins': 21, 'losses': 2, 'stance': 'Southpaw', 'reach': '65 in', 'recent_fights': 'Won 5 of last 5'}]}
        return {'response': []}


def main() -> None:
    assert sport_family('UFC MMA') == 'mma'
    assert sport_family('FIFA World Cup') == 'soccer'
    row = {'sport': 'MMA', 'event_name': 'Charles Johnson vs Asu Almabaev', 'away_team': 'Charles Johnson', 'home_team': 'Asu Almabaev'}
    ctx = build_context(row, language='en', providers=[MockMmaProvider(language='en')])
    assert ctx['api_mma_configured'] == 'true'
    assert ctx['api_mma_called'] == 'true'
    assert ctx['api_mma_match_found'] == 'true'
    assert ctx['away_record'] == '17-6'
    assert ctx['home_record'] == '21-2'
    assert 'Charles Johnson' in ctx['away_player_notes'] or 'Stance' in ctx['away_player_notes']
    assert 'Mock' in ctx['matchup_notes']
    non_mma = MockMmaProvider(language='en').lookup({'sport': 'MLB', 'event_name': 'A at B'})
    assert non_mma == {}
    for key in ('API_MMA_KEY', 'APISPORTS_API_KEY', 'API_SPORTS_KEY', 'API_FOOTBALL_KEY'):
        os.environ.pop(key, None)
    missing = ApiMmaContextProvider(language='en').lookup(row)
    assert missing['api_mma_configured'] == 'false'
    assert missing['api_mma_called'] == 'false'
    assert 'key missing' in missing['api_mma_unavailable_reason'].lower()
    print('sports context mma smoke test passed')


if __name__ == '__main__':
    main()
