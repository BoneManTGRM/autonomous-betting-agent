# Player Props Layer

The player props layer scores individual player outcomes while still using market odds.

Supported examples include:

- anytime touchdown
- home run
- goal
- shot on goal
- assist
- hit
- strikeout
- reception
- rushing yards
- receiving yards
- passing yards

## Core idea

The layer does not throw away the market. It uses the market as a baseline, then compares it against an independent player probability.

```text
market probability + player model probability -> blended probability -> edge -> status
```

Market probability can come from:

- decimal price such as `best_price`
- direct `market_probability`
- binary no-vig prices such as `over_price` and `under_price`

Player probability can come from:

- direct `model_probability`
- recent player rate
- season player rate
- opponent allowed rate
- usage rate

## Command

```bash
python tools/run_player_props.py player_props.csv
```

Default outputs:

```text
data/player_props_checked.csv
data/player_props_ranked.csv
```

Use this when you want to inspect watch/reject rows too:

```bash
python tools/run_player_props.py player_props.csv --include-watch
```

## Important output columns

- `prop_player_name`
- `prop_type_normalized`
- `prop_market_probability`
- `prop_model_probability`
- `prop_blended_probability`
- `prop_implied_edge`
- `prop_fair_decimal_price`
- `prop_status`
- `prop_stake_units`
- `prop_reasons`
- `prop_required_data`

## Final statuses

Candidate statuses:

```text
QUALIFIED_STRONG
QUALIFIED
QUALIFIED_SMALL
```

Not-ready statuses:

```text
WATCH
TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA
REJECT
```

## Required caution

Player props are volatile. A player can be limited by injury, playing time, lineup role, game script, weather, defense, substitutions, foul trouble, or coaching decisions. Use the output as a research shortlist, not as proof of edge.
