# Quality filter verification

A conservative quality filter utility was added in `autonomous_betting_agent/quality_filter.py`.

The utility reviews rows and adds:
- `quality_filter_pass`
- `quality_tier`
- `quality_risk_score`
- `reason_for_downgrade`

It is intended to help reduce weak promoted rows before a clean validation period.
