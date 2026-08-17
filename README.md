# apparatus-comps

A comparable-sales estimator for emergency vehicles, with a real back-test, so
that a price estimate can be quoted with an error bar instead of on its own.

Everything runs offline from cached page snapshots. No API keys, no network, no
paid services.

---

## The short version

**What I noticed.** Garage runs an AI appraisal on fire apparatus and ambulances, equipment
that trades from five to seven figures, and publishes no accuracy figure anywhere. Their own
FAQ answers "how accurate is the appraisal?" without a number. That is not unusual and it is
not a criticism; almost nobody in appraisal publishes one, because the honest number is
uncomfortable.

**So I measured what a comparable-sales model can actually do here.** 903 listings parsed
from 40 cached state pages, filtered to 577 emergency apparatus rows with a type, a model
year and a price. Split by time rather than randomly, because a random split leaks future
prices into the past.

**What I found**, on 174 held-out listings:

| model | MAE | median APE | within 20% | within 30% |
|---|---:|---:|---:|---:|
| comparables, k=10 | $32,342 | **36.0%** | 30.5% | 41.4% |
| gradient-boosted trees | $29,916 | 37.0% | 29.9% | 40.2% |
| median by type and decade | $45,454 | 42.8% | 21.3% | 36.8% |
| global median | $41,230 | 47.5% | 18.4% | 32.8% |

**A median error of 36% is the honest headline, and it is the point.** Comparables beat both
naive baselines by a wide margin and still miss by a third on the median listing. This
equipment is too heterogeneous and too thinly traded for a point estimate to mean much, which
is exactly why an appraisal that returns a single number without a range is hard to act on.

**The number I would actually ship is the interval.** A band built from the weighted spread
of the comparables covers **93.7% of held-out prices against a nominal 90%**, so it is
slightly conservative and roughly calibrated. A seller can act on "somewhere in this range,
and here are the six trucks it is based on." Nobody can act on a wrong point estimate.

**I published where my own model loses too.** Gradient-boosted trees beat my comparables
model on MAE and RMSE. I kept comparables as the headline anyway, because a seller can see
the six trucks behind the number and cannot see inside a tree ensemble, and for an appraisal
that is worth more than $2,400 of MAE.

**What it is not, and this matters.** The target is **asking price on active listings, not
closed sale prices.** Public listings do not expose what anything sold for. So this measures
agreement with what sellers ask, not with what buyers pay, and every number above inherits
that. With real closed-sale data the whole thing re-runs unchanged and the numbers would
mean considerably more.

## Run it

```bash
uv venv --python 3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install numpy pandas scikit-learn tabulate
.venv/bin/python build_dataset.py     # data/raw/*.html -> data/dataset.csv
.venv/bin/python tune.py              # reproduces the hyperparameter choice
.venv/bin/python backtest.py          # writes results/backtest.md
```

`backtest.py` regenerates every number in `results/backtest.md` and in
`../RESULTS.md`.

## What the data is, and what it is not

`data/raw/` holds 40 server-rendered `shopgarage.com/state/<state>` pages plus
the public listings sitemap, all fetched read-only on 2026-08-14 after reading
`robots.txt` (see `fetch.sh` for the exact guardrails). Each page ships its own
`__NEXT_DATA__` payload with up to 32 listing previews; the parser reads the
fields out of that JSON and does no imputation.

- **903** listing rows parsed
- **766** priced vehicles after dropping gear and parts (`price >= $5,000`, a
  vehicle type and a model year present)
- **577** of those are in the vehicle families the appraisal page names: fire
  apparatus, ambulances, rescue, command

**The target is the asking price on an active listing, not a closed sale
price.** Public listings do not expose what a unit finally sold for. That is the
single biggest limitation here and it is stated everywhere the numbers appear.
Asking prices are noisier than sale prices, particularly at the bottom of the
market where a $10k listing may be a non-runner or a parts unit, so treat these
error figures as an upper bound on what the same model would produce against
real closed sales.

## Features

Read straight out of Garage's own category-attribute schema, which is in the
listing payload:

| feature | source field | coverage in the 577-row apparatus set |
|---|---|---|
| vehicle type | `Vehicle type` (required) | 100% |
| chassis make | `Chassis` (required) | 100% |
| body builder | `Body` (required) | 100% |
| model year | parsed from listing title | 100% (rows without a year are dropped) |
| mileage | `Mileage` (required) | 100% |
| pump size, gpm | `Pump size (gpm)` | 66% |
| tank size, gal | `Tank size (gal)` | 67% |
| engine hours | `Engine hours` | 40% |
| region | listing state, grouped into 4 Census regions | 100% |

Engine hours are collected but too sparse to carry weight in the distance
function, so they are read and reported rather than used.

## The model

`CompsModel` in `comps.py`: k-nearest comparables, k = 10, with a hand-written
distance function whose weights are all visible constants at the top of the
file. Prediction is a distance-weighted mean of the comparables' log prices; the
band is the weighted spread of those same comparables, which makes it a
multiplicative interval rather than a fixed dollar range.

Vehicle types are grouped into families (pumper, aerial, tanker, brush, rescue,
command, ambulance, refuse, sewer, dump). A different type inside the same
family costs 1.2 penalty units, a different family costs 3.0, so a rescue-pumper
can borrow from pumpers but never from ambulances. Without that, rare types have
no neighbours at all.

The point of the design is that `model.explain(row)` returns the exact
comparables used, their distances and their weights. A seller who disagrees with
the number can see which ten trucks produced it. An appraisal a seller cannot
argue with is not an appraisal they will trust.

Controls published next to it: gradient-boosted trees on log price, a
median-by-(type, age decade) lookup table, and a flat market median.

## Back-test

Primary split is **time-based** on each listing's sitemap `<lastmod>` date: the
newest 30% by date is held out and the model only ever sees listings that
already existed. A random split is reported alongside and is optimistic, which
is the reason both are shown.

Hyperparameters (k, weight softening, family/age/mileage weights) were chosen by
`tune.py` on a train-only inner chronological split. The held-out test set is
never used for selection.

## Pointing this at real sales data

`build_dataset.py` is the only file that knows where data comes from. Replace it
with anything that emits `data/dataset.csv` with the same columns and a `price`
column holding closed-sale prices, and `backtest.py` prints the same MAE, RMSE,
MAPE, error-percentile, band-coverage and failure-slice tables against real
sales. Nothing else changes.
