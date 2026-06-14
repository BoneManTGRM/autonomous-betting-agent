# ARA Filters

The package now includes `autonomous_betting_agent/ara_filters.py`.

It enriches prediction CSV files with:

- record keys
- sport groups
- probability buckets
- implied probability from best price
- proxy edge
- smoothed calibration
- soccer draw flags
- baseball volatility flags
- optional outdoor weather flags
- live decision labels
- proxy filter labels

Run it with:

```bash
python apply_ara_decision_layer.py predictions.csv --output enriched.csv --deduped-output enriched_deduped.csv
```

Current external inputs remain limited to odds data and optional WeatherAPI-derived columns already present in the CSV.

The filter does not fetch extra providers. Add independent model probabilities to the CSV before expecting non-watch live decisions.
