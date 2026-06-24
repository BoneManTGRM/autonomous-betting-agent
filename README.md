# ABA Signal Pro

**Powered by Reparodynamics**

[![CI](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BoneManTGRM/autonomous-betting-agent/actions/workflows/ci.yml)

ABA Signal Pro is a proprietary, source-available sports betting analytics and prediction-analysis platform built from the ARA/TGRM workflow: test available evidence, detect weak signals, repair the analysis, verify uncertainty, and produce auditable probability reports.

It is designed for sports analysts, betting-market researchers, prediction reviewers, private research groups, influencers, and commercial operators that need a repeatable decision layer instead of manual guesswork.

**Important:** this software does not execute transactions, does not guarantee winners, and does not guarantee returns. It is an analytics and research system. Any real-world betting or financial decision remains the responsibility of the user.

## Current product structure

The app is organized around a local-first commercial workflow:

```text
Deployment Health -> Scanner Pro -> ABA Signal Pro -> Pro Predictor / Pro Predictor Volume -> Odds Lock Pro -> Auto Result Grading -> Public Proof Dashboard -> Report Studio -> Local First Admin -> Learning Memory
```

| Tool | Main job |
| --- | --- |
| **Deployment Health** | Checks integration status, page/file presence, persistent ledger health, proof quality, monthly-license readiness, and action items. |
| **Scanner Pro** | Scans live odds feeds, normalizes markets, ranks market quality, and sends clean rows forward. |
| **ABA Signal Pro** | Builds model probabilities, applies learned memory, scores agent decisions, and produces prediction-ready rows. |
| **Pro Predictor** | Scans live Odds API feeds, applies model probability, adaptive learning, scanner strength, and sends ranked prediction rows forward. |
| **Pro Predictor Volume** | High-volume workflow using safer volume defaults plus the Pattern Points ranking layer for learned-pattern discovery. |
| **What Are the Odds** | Runs manual/uploaded market/value review, including a price-safety gate for uploaded CSV rows. |
| **Odds Lock Pro** | Creates timestamped proof ledgers, client-safe reports, bankroll controls, persistent-ledger saves, and audit-ready proof IDs. |
| **One-Click Daily Workflow** | Takes current/session/uploaded rows, locks qualified rows, optionally saves them, and generates report output in one guided flow. |
| **Auto Result Grading** | Grades the persistent proof ledger from finished-result CSV uploads or an explicit one-click score fetch. |
| **Public Proof Dashboard** | Displays no-login proof metrics, demo mode, proof audit, CLV, result uploads, persistent ledger storage, and report cards. |
| **Report Studio** | Generates client-ready performance reports with win/loss tracking, ROI summaries, filters, branded layouts, and custom background images. |
| **Report Studio Local Export** | Generates local Markdown, HTML, and messenger-ready report exports from local proof rows without a cloud server. |
| **Proof ID Verification** | Searches local proof IDs and verifies proof hash, lock time, event start time, grade, ledger type, and public-safe status. |
| **Local First Admin** | Reviews local SQLite/CSV storage, ledger counts, event-level and row-level summaries, audit logs, and CSV exports. |
| **Monthly License Readiness** | Scores whether the product is ready for private beta, operator licensing, or white-label licensing, then produces pricing and offer copy. |
| **Buyer Demo Mode** | Shows a polished buyer-ready dashboard with demo locked rows, audit, proof table, and report cards without API keys. |
| **Learning Memory** | Trains durable calibration and pattern memory from finished, graded results. |

Older duplicate scanner, market-finder, league-specific, and legacy self-learning pages were removed or consolidated.

## Local-first commercial agent layer

The local-first upgrade adds a safer commercial foundation without requiring a cloud server.

Local-first modules:

| Module | Purpose |
| --- | --- |
| `autonomous_betting_agent/ledger_types.py` | Separates official, research, all-high-confidence, quarantine, learning-only, and client-facing ledgers. |
| `autonomous_betting_agent/sqlite_store.py` | Saves proof rows and audit events into local SQLite at `data/aba_signal_pro.sqlite`. |
| `autonomous_betting_agent/storage.py` | Provides SQLite-first storage with CSV fallback in `data/ledgers`. |
| `autonomous_betting_agent/explanations.py` | Builds client-safe pick explanations covering Pattern Points, odds audit, probability, edge, book coverage, and risk. |
| `autonomous_betting_agent/report_exports.py` | Produces local Markdown, HTML, and copy/paste report output. |
| `autonomous_betting_agent/grading_rules.py` | Separates row-level and event-level summaries, including win/loss/push/cancel/pending counts. |
| `autonomous_betting_agent/bankroll.py` | Provides conservative risk-management stake helpers using flat stake or conservative Kelly-style sizing. |
| `autonomous_betting_agent/local_access.py` | Provides optional local access helper logic while keeping no-login mode as the default. |

Local-first pages:

| Page | Purpose |
| --- | --- |
| `pages/local_first_admin.py` | Local storage/admin overview, ledger counts, audit log, and exports. |
| `pages/report_studio_local_export.py` | Local Markdown, HTML, and messenger-ready Report Studio exports. |
| `pages/proof_id_verification.py` | Local proof ID verification and client-safe explanation display. |

No Supabase, Postgres, Firebase, OAuth, paid database, or cloud server is required for this layer. SQLite is preferred when available; CSV fallback is used if SQLite fails.

## Optional local access

The current default remains no-login/no-password mode so existing Streamlit workflows continue to work.

Optional local access can be enabled later with:

```text
ABA_REQUIRE_LOGIN=true
```

The helper in `autonomous_betting_agent/local_access.py` supports local admin/client/demo roles from environment variables or Streamlit secrets. It does not require OAuth, email verification, a cloud identity service, or a separate server.

## Current safety and scoring updates

The current recommended testing path is:

```text
Pro Predictor Volume -> Odds Lock Pro -> Public Proof Dashboard -> Auto Result Grading -> Report Studio Local Export -> Learning Memory
```

Recent updates added important protections and ranking layers:

1. **Consensus odds normalization**: live odds summaries normalize Pro Predictor outputs toward the market average/consensus price instead of trusting a single outlier best-book price.
2. **Price-safety audit**: `autonomous_betting_agent/odds_quality.py` defines an `audit_prices()` layer that uses the average price as the proof-safe price and flags suspicious price patterns.
3. **Pattern Points**: `pages/pro_predictor_volume.py` adds a dedicated learned-pattern score so the system can rank both obvious high-confidence picks and lower-confidence rows that match historically useful patterns.
4. **Ledger separation**: public proof metrics should only use rows eligible for official/client proof, not research, learning-only, or quarantine rows.
5. **Pick explanations**: report-ready rows can now include client-safe explanations without guaranteed-win language.
6. **Event-level summaries**: duplicate rows from one matchup can be summarized as one event when needed.

## Odds safety rules

The system separates proof-safe prices from diagnostic prices:

| Field | Purpose |
| --- | --- |
| `decimal_price` | Proof-safe decimal price used for implied probability, edge, EV, and proof exports. |
| `odds_at_pick` | Same proof-safe price used when the row is locked. |
| `best_price` | Diagnostic/reference price only. It should not be trusted as proof if it is far away from average market price. |
| `average_price` | Market consensus price. This is preferred for proof. |
| `worst_price` / `_robust_decimal_price` | Conservative price reference used for risk and robust EV checks. |
| `odds_audit_status` | `pass`, `quarantine`, or `fail` depending on price quality. |
| `odds_audit_reason` | Explanation for why a row passed or was flagged. |

A row should be reviewed or blocked when any of these appear:

- `best_price` is far above `average_price`.
- Average odds are below about `1.75`, but best price is `3.00+`.
- Price range across books is very wide.
- Average price is `3.00+` for a high-confidence proof row.
- Favorite probability is paired with underdog-style odds, or underdog probability is paired with favorite-style odds.
- Unsupported markets such as tennis/ATP/WTA/ITF/challenger enter the workflow.

This does not mean the pick is automatically bad. It means the **proof price is not trusted** until the market mapping is verified.

## Pattern Points scoring

`pattern_points` is a 0-100 score added by Pro Predictor Volume after Adaptive Learning runs. It is designed to answer this question:

> Does this row match patterns that have historically performed well, even if the raw model confidence is not extremely high?

Pattern Points is not a guarantee. It is a ranking and review score. It should be used to prioritize rows for testing and locking, not to claim certainty.

### Pattern Points tiers

| Tier | Score range | Meaning |
| --- | ---: | --- |
| **A+ Pattern Lock** | `85+` | Strongest learned-pattern profile. Candidate for strict review/locking if all odds and proof checks pass. |
| **A High Confidence** | `75-84` | High-confidence pattern edge. Strong candidate for lock-ready review. |
| **B Strong Pattern** | `65-74` | Good learned-pattern signal. Useful for research and selected proof testing. |
| **C Research Edge** | `55-64` | Research/watch candidate. Needs more results before trusting. |
| **D Review Only** | `<55` | Weak pattern profile or risk penalty. Usually do not lock without manual reason. |

## Report Studio and local exports

Report Studio is the dedicated reporting and presentation layer for ABA Signal Pro. It turns locked predictions, graded results, proof data, and performance metrics into cleaner client-facing reports.

Core Report Studio capabilities:

- Generate professional reports from locked proof rows and graded results.
- Show win/loss record, pending rows, ROI, units, performance summaries, and proof metrics.
- Filter report output by sport, league, market, date range, confidence level, and proof status when those fields are available.
- Build public-facing summaries for clients while keeping private audit details separate.
- Use custom branding and presentation layouts for sales, buyer demos, client updates, and internal review.
- Add nearly any user-selected image as the report background so reports can match a brand, theme, client, or campaign.
- Support export-ready report output for sharing, proof tracking, and record keeping.
- Connect reporting with Odds Lock Pro, Public Proof Dashboard, Auto Result Grading, One-Click Daily Workflow, and the local-first storage layer.

`pages/report_studio_local_export.py` adds local Markdown, HTML, and copy/paste report output without requiring PDF services, email services, or a cloud server.

Report Studio should be treated as a presentation and proof-reporting tool, not as a guarantee engine. It can make results easier to explain, but claims should still be based on timestamped locked proof, clean grading, ROI, sample size, and audit quality.

## No-password commercial mode

The app now includes the most valuable platform upgrades without requiring users to log in every time:

1. **Persistent ledger storage** through local CSV and local SQLite support.
2. **Auto-grading from finished-result uploads** by `proof_id` or event/pick matching.
3. **Optional explicit score fetch** for one sport key at a time from Auto Result Grading; this runs only when the button is pressed.
4. **Public proof dashboard** for record, ROI, units, pending picks, sport breakdowns, market breakdowns, and client-safe ledgers.
5. **Report-card generator** for Markdown, HTML, and daily copy/paste reports.
6. **Report Studio** for client-ready reports, performance summaries, branded layouts, and custom background images.
7. **Local Report Studio exports** for Markdown, HTML, and messenger-ready summaries.
8. **Proof ID Verification** for local proof lookup and proof-field review.
9. **Proof audit layer** that checks proof hashes and pre-start lock status.
10. **Proof quality score** for buyer/demo review.
11. **CLV tracking** from locked price vs closing price when closing odds are supplied.
12. **Demo ledger mode** so a buyer can see the dashboard without an API key or real locked picks.
13. **Deployment Health** so the operator can see readiness and blockers before daily use.
14. **One-Click Daily Workflow** so non-technical users can run the daily lock/report process.
15. **Monthly License Readiness** so the operator can package private beta, analyst, operator, or white-label offers.
16. **Public-safe exports** and private audit exports.

This is not a full password-protected client portal yet. Login, paid accounts, Stripe, and client roles can be added later. The new local access helper is optional and disabled by default.

## Recommended daily workflow

1. Open **Deployment Health** and confirm the deployment is usable.
2. Use **Pro Predictor Volume** for the main high-volume scan.
3. Review `pattern_points`, `pattern_confidence_tier`, `odds_audit_status`, `decimal_price`, and `average_price` before locking.
4. Use **Odds Lock Pro** to lock only rows that are future events and pass proof checks.
5. Save locked rows into the persistent proof ledger.
6. Use **Auto Result Grading** when finished results are available.
7. Use **Public Proof Dashboard** to review public metrics, proof audit, CLV, report cards, and exports.
8. Use **Local First Admin** to review local ledger counts, row-level/event-level records, and audit events.
9. Use **Proof ID Verification** to verify individual proof rows.
10. Use **Report Studio Local Export** to generate branded or client-ready Markdown/HTML/copy-paste summaries.
11. Use **Learning Memory** after results are graded and probabilities/prices are available.
12. Use **Monthly License Readiness** before pitching monthly clients or raising prices.

## Data proof rules

The system distinguishes between historical backfill, learning-only rows, result-only rows, future lock-ready rows, and official forward-proof rows.

A future prediction is strongest when it has event name, sport, market type, prediction, model probability, decimal price, bookmaker/odds source, event start time, lock timestamp before event start, proof ID, proof hash, and final result added later.

A row does not count as a public proof row unless it has both `proof_id` and `locked_at_utc`.

A high hit rate alone is not enough. ROI, average price, CLV, book coverage, sample size, duplicate control, and prospective timestamped proof matter more than headline accuracy.

For public proof, never advertise rows that are only research candidates as official +EV proof. Keep official proof, research/test proof, and quarantine/review rows separated.

## Monthly license readiness

The product should be sold as a monthly sports analytics and proof-tracking license, not as guaranteed betting income and not as a one-time code dump.

Minimum readiness for a private beta license:

| Requirement | Target |
| --- | --- |
| Future-only locked proof rows | 25+ |
| Resolved proof rows | 20+ |
| Proof quality | 90/100+ preferred |
| Hash mismatches | 0 |
| Product pages | Deployment Health, Odds Lock Pro, Public Proof Dashboard, Report Studio, Report Studio Local Export, Proof ID Verification, Local First Admin, Daily Workflow, Auto Result Grading, Buyer Demo Mode, Monthly License Readiness |
| Client outputs | public dashboard, Report Studio output, local HTML/Markdown report, daily report, proof card, branded background report, private audit export |
| Positioning | analytics/research only; no guaranteed wins or returns |

Suggested pricing path:

| Tier | Target price | When to use |
| --- | ---: | --- |
| Private beta license | $500-$1,000/mo | First 2-3 serious testers while proof sample is still growing. |
| Private analyst license | $1,000-$2,500/mo | After 100+ future-locked rows with clean audit and transparent ROI. |
| Operator license | $2,500-$5,000/mo | For paid communities, influencers, or private groups needing reports and proof exports. |
| White-label/private deployment | $10,000 setup + $5,000-$10,000/mo | For branded/private deployments after operator-ready proof and support workflow exist. |

Before pitching higher tiers, use the **Monthly License Readiness** page to generate the readiness checklist, next build queue, pricing table, client package list, and offer text.

## API and background behavior

The report/dashboard/demo pages do not scan live APIs by themselves.

Auto Result Grading only fetches score data when the user presses the fetch button for a specific sport key. Otherwise, result grading is done from uploaded result CSVs or already available rows.

The local-first SQLite/CSV storage layer does not require any API key.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the Streamlit app

```bash
streamlit run streamlit_app.py
```

If your deployment uses the older entrypoint, run:

```bash
streamlit run app_streamlit.py
```

## API keys and local settings

The app can read keys from Streamlit secrets, environment variables, or user input fields depending on the page.

Common secret names:

```text
THE_ODDS_API_KEY
ODDS_API_KEY
SPORTSDATAIO_API_KEY
WEATHERAPI_KEY
WEATHER_API_KEY
GITHUB_TOKEN
GH_TOKEN
GITHUB_REPOSITORY
GITHUB_BRANCH
ABA_REQUIRE_LOGIN
ABA_ADMIN_NAME
ABA_ADMIN_CODE
ABA_CLIENT_NAME
ABA_CLIENT_CODE
ABA_DEMO_NAME
ABA_DEMO_CODE
```

`GITHUB_TOKEN` is only needed if Learning Memory should save trained memory files back to GitHub from the deployed app.

Do not put real API keys, private access codes, secrets, screenshots with secrets, or private CSVs into GitHub.

## Run tests and CI

Run the local checks with:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m compileall autonomous_betting_agent pages tests
python -m pytest tests -q
```

GitHub Actions also runs these checks automatically on pushes to `main`, pull requests, and manual `workflow_dispatch` runs using `.github/workflows/ci.yml`.

A green badge or workflow run should be checked directly in GitHub before claiming that a deployment passed.

## Commercial positioning

This project is intended to become a licensable product, not a free open-source prediction bot. It can support private sports analytics dashboards, paid research tools, white-label prediction-review systems, Report Studio client-facing sports analytics reports, custom branded report backgrounds, internal research workflows, custom API integrations, private deployment, support, and model-tuning packages.

The repository is public for limited review and evaluation, but the code is governed by a proprietary evaluation license. Commercial use, resale, sublicensing, hosting, paid access, SaaS deployment, API access, white-label use, competing-product use, model-training use, or monetized derivative use requires written permission from Reparodynamics.

## Limitations

- The system is only as strong as the data supplied to it.
- Short samples can look excellent by luck and should not be sold as proof.
- Fallback probability rows are useful for rough learning, not serious validation.
- Result-only rows are not enough for calibration.
- A model can have a high hit rate and still perform poorly if the prices are too short.
- Pattern Points are a ranking signal, not a guarantee.
- Price audit flags data-quality risk; it does not prove the pick itself is wrong.
- API outages, missing keys, low quota, unsupported sports, or bad market coverage can reduce output quality.
- Local SQLite/CSV storage protects against cloud dependency but is not a replacement for backups.
- This software does not execute transactions or provide guarantees.
