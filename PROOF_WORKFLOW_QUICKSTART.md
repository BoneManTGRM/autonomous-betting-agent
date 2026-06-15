# Proof Workflow Quickstart

## Purpose

This workflow keeps the app honest and easier to use. It separates raw exports, learning rows, statistical results, official locked rows, and buyer-facing proof.

## Recommended order

1. **Export Templates**
   - Download the official-pick template.
   - Use it for future exports so the app does not have to guess column names.

2. **Data Intake Gate**
   - Upload every new CSV here first.
   - Check whether the file is blocked, limited, usable, or strong.

3. **CSV Doctor**
   - Use this when a file does not behave correctly.
   - It shows column mapping, normalized fields, blockers, warnings, and next actions.

4. **Odds Lock**
   - Use only for new predictions before events start.
   - Do not use it to make historical rows look forward-locked.

5. **Statistical Validation**
   - Use after rows have win/loss results.
   - Review observed hit rate, sample-size warning, confidence interval, and ROI scenarios.

6. **Proof Readiness**
   - Use before showing results to a buyer or serious user.
   - It separates official proof from historical learning/backfill.

7. **Forward Test Tracker**
   - Use during the live proof test.
   - Tracks progress toward 25, 100, 500, and 1,000 locked rows.

8. **Live Command Center**
   - Use as the daily operating view.

9. **Executive Demo Mode**
   - Use for a polished buyer-facing view after proof rows are ready.

## Current safest claim

The current high-confidence learning sample has 10 resolved historical rows and went 8-2. It is useful for calibration, but it is not yet full ROI proof because future official proof needs locked odds, timestamps, model probability, and clean results.

## Best next technical step

Use the Export Template format for all future prediction exports, then lock new predictions before events start using Odds Lock.
