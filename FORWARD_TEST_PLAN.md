# Forward Test Plan

## Goal

Create proof that is stronger than historical screenshots or manually edited CSVs.

The goal is not just a high win rate. The goal is timestamped ROI proof.

## Official-pick rule

A pick is official only when it has all of the following before the event starts:

- `event`
- `prediction`
- `model_probability`
- `decimal_price`
- `bookmaker` or odds source
- `prediction_timestamp` or `locked_at_utc`
- `lock_hash` or proof-ledger hash

Rows missing odds or probability must remain `not_official`, `watch_only`, or `learning_only_backfill`.

## Recommended sample goals

| Stage | Target | Purpose |
|---|---:|---|
| Smoke test | 25 locked picks | Confirm the pipeline works. |
| Early proof | 100 locked picks | Show first meaningful signal. |
| Serious proof | 500 locked picks | Better buyer conversation. |
| Strong proof | 1,000+ locked picks | More credible valuation case. |

## Metrics to report

- Win rate
- ROI
- Units won/lost
- Average odds
- Closing-line value
- A+ record
- Sport-by-sport record
- Pending/review-needed count
- Duplicate count
- Missing-odds count

## Rules for trust

- Never count unresolved rows as wins.
- Never count review-needed rows as official.
- Never count duplicate rows as official.
- Never claim ROI when odds are missing.
- Separate historical learning rows from official forward proof.

## Buyer-safe claim after 100+ locked picks

> The system has begun a forward-locked proof test. Every official pick includes timestamp, model probability, odds, source, and result tracking. Performance should be judged by ROI and units, not just win rate.
