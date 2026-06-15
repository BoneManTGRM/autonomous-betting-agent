# Data Dictionary

## Core prediction fields

| Field | Meaning |
|---|---|
| `prediction_id` | Unique ID for the ledger row. |
| `prediction_timestamp` | Time the pick was recorded. |
| `event` | Matchup or event name. |
| `sport` | Sport or league. |
| `market_type` | Bet market, such as moneyline or winner. |
| `prediction` | Selected side/pick. |
| `model_probability` | Model probability for the pick. |
| `decimal_price` | Decimal odds used for ROI math. |
| `american_odds` | American odds equivalent. |
| `implied_probability` | Break-even probability from odds. |
| `bookmaker` | Sportsbook/source for price. |
| `odds_source` | Feed/source used for odds. |

## Decision/audit fields

| Field | Meaning |
|---|---|
| `decision` | Candidate, strong_candidate, watch_only, skip, etc. |
| `decision_reason` | Explanation for the decision. |
| `confidence_tier` | A+ High Confidence, A Strong, B Lean, Watch Only, No Bet. |
| `result_status` | win, loss, void, pending, review_needed. |
| `clean_grading_status` | graded_clean, void, review_needed, pending. |
| `audit_inclusion` | official, pending_until_final, excluded_review_needed, excluded_void, excluded_duplicate. |
| `stake_units` | Units risked. |
| `profit_units` | Profit/loss in units. |
| `roi_percent` | Return on stake percentage. |

## Proof fields

| Field | Meaning |
|---|---|
| `previous_hash` | Prior row hash in the ledger. |
| `row_hash` | SHA-256 hash of the current row contents. |
| `ledger_schema_version` | Proof ledger schema version. |
| `local_user_id` | Local profile ID. |
