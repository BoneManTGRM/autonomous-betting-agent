# Market Snapshots

The repo includes a line-movement capture flow using The Odds API only.

## Streamlit

Open the page:

```text
Market Snapshot Capture
```

Choose a sport feed and press `Capture snapshot`.

The page writes:

```text
data/market_snapshots.csv
data/latest_market_movement.csv
```

## Command line

```bash
python capture_market_snapshots.py baseball_mlb
```

or:

```bash
python capture_market_snapshots.py baseball_mlb --api-key YOUR_ODDS_API_KEY
```

## Why this matters

Repeated snapshots create a market tape. The system can compare opening price, current price, probability movement, best price movement, bookmaker count, and overround.

This helps measure whether ARA is getting ahead of the market instead of only checking win or loss after the game.
