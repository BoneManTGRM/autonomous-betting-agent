# Accuracy filter plan

The next quality layer should reduce promoted rows instead of increasing volume.

Planned fields:
- model_probability
- implied_probability
- edge_percent
- volatility_score
- draw_risk
- surface_risk
- confidence_tier
- promoted_yes_no
- reason_for_downgrade

Planned behavior:
- require stronger model edge
- downgrade close projected margins
- downgrade high draw-risk soccer moneyline rows
- downgrade volatile tennis surface rows
- downgrade unclear injury or lineup context
- send downgraded rows to tracking only
