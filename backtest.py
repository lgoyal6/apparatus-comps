"""Back-test the comparable-sales estimator and write results/backtest.md.

Primary split is TIME-BASED on each listing's <lastmod> date: the model may only
see listings that were already on the site. A random split is also reported, and
it is optimistic, which is exactly why both are shown.

Two scopes are evaluated:
  apparatus - the vehicle families the appraisal page names (fire apparatus,
              ambulances, command, rescue). This is the headline scope.
  all       - every priced vehicle on the site, including refuse, sewer and
              dump trucks, which Garage also lists.

Run:  python backtest.py
"""

import os
import sys

import numpy as np
import pandas as pd

from comps import (CompsModel, GbtModel, MedianBaseline, GlobalMedian,
                   prepare, EMERGENCY_FAMILIES)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "dataset.csv")
OUTDIR = os.path.join(HERE, "results")
MIN_PRICE = 5000          # below this the listing is gear, not a vehicle
TEST_FRACTION = 0.30

MODELS = {
    "comps_k10 (this)": CompsModel,
    "gbt_log": GbtModel,
    "median(type,age-decade)": MedianBaseline,
    "global_median": GlobalMedian,
}


def load():
    d = pd.read_csv(DATA)
    d["last_modified"] = pd.to_datetime(d["last_modified"], utc=True)
    n_raw = len(d)
    kept = d[
        d["type"].notna() & d["model_year"].notna() & (d["price"] >= MIN_PRICE)
    ].copy()
    return prepare(kept), n_raw


def metrics(y, p):
    err = p - y
    ape = np.abs(err) / y
    return {
        "n": len(y),
        "MAE_$": np.mean(np.abs(err)),
        "RMSE_$": np.sqrt(np.mean(err ** 2)),
        "MAPE_%": 100 * np.mean(ape),
        "MedAPE_%": 100 * np.median(ape),
        "P90_APE_%": 100 * np.percentile(ape, 90),
        "within_20%": 100 * np.mean(ape <= 0.20),
        "within_30%": 100 * np.mean(ape <= 0.30),
        "bias_$": np.mean(err),
    }


def fmt(rows):
    df = pd.DataFrame(rows).set_index("model")
    for c in df.columns:
        if c == "n":
            df[c] = df[c].astype(int)
        elif c.endswith("_$"):
            df[c] = df[c].map(lambda v: f"{v:,.0f}")
        else:
            df[c] = df[c].map(lambda v: f"{v:.1f}")
    return df


def run_split(train, test, label, lines):
    lines.append(f"\n#### {label}\n")
    lines.append(f"train n = {len(train)}, test n = {len(test)}\n")
    rows, preds = [], {}
    for name, cls in MODELS.items():
        p, _ = cls().fit(train).predict(test)
        preds[name] = p
        rows.append({"model": name, **metrics(test["price"].to_numpy(), p)})
    lines.append(fmt(rows).to_markdown())
    lines.append("")
    return preds


def error_distribution(y, p, lines):
    ape = 100 * np.abs(p - y) / y
    lines.append("\n#### Error distribution, comps_k10, time-based test set\n")
    lines.append("| percentile of |APE| | value (%) |")
    lines.append("|---|---|")
    for q in [10, 25, 50, 75, 90, 95, 99]:
        lines.append(f"| p{q} | {np.percentile(ape, q):.1f} |")
    lines.append(f"| max | {ape.max():.1f} |")
    lines.append("")
    lines.append(
        f"Mean APE {ape.mean():.1f}% against median APE {np.median(ape):.1f}%. "
        "The gap is the right tail, and the right tail is what costs a "
        "marketplace a deal.\n")


def band_calibration(test, p, sd, lines):
    y = test["price"].to_numpy()
    lines.append("\n#### Is the error bar honest?\n")
    lines.append("Band from the weighted spread of the comparables used, in log "
                 "space. Nominal coverage assumes log-normal; actual coverage is "
                 "measured on the held-out set.\n")
    lines.append("| band | nominal | actual coverage | median band width (hi/lo) |")
    lines.append("|---|---|---|---|")
    for z, nom in [(1.0, "68%"), (1.645, "90%"), (1.96, "95%")]:
        lo, hi = p * np.exp(-z * sd), p * np.exp(z * sd)
        cov = 100 * np.mean((y >= lo) & (y <= hi))
        lines.append(f"| +/-{z} sd | {nom} | {cov:.1f}% | "
                     f"{np.median(hi / np.maximum(lo, 1)):.1f}x |")
    lines.append("")


def block(title, groups, lines):
    lines.append(f"\n#### {title}\n")
    rows = []
    for name, sub in groups:
        rows.append({
            "slice": name, "n": len(sub),
            "MedAPE_%": sub["ape"].median() if len(sub) else float("nan"),
            "MAPE_%": sub["ape"].mean() if len(sub) else float("nan"),
            "MAE_$": sub["abs_err"].mean() if len(sub) else float("nan"),
        })
    df = pd.DataFrame(rows).set_index("slice")
    df["n"] = df["n"].astype(int)
    for c, f in [("MedAPE_%", "{:.1f}"), ("MAPE_%", "{:.1f}"), ("MAE_$", "{:,.0f}")]:
        df[c] = df[c].map(lambda v, f=f: "n/a" if pd.isna(v) else f.format(v))
    lines.append(df.to_markdown())
    lines.append("")


def slices(test, p, train, lines):
    y = test["price"].to_numpy()
    t = test.copy()
    t["ape"] = 100 * np.abs(p - y) / y
    t["abs_err"] = np.abs(p - y)
    t["pred"] = p
    t["type_support"] = t["type"].map(train["type"].value_counts()).fillna(0)

    block("Where it is worst: how much training support the type had", [
        ("rare type (<10 train rows)", t[t.type_support < 10]),
        ("thin type (10-29)", t[(t.type_support >= 10) & (t.type_support < 30)]),
        ("common type (30+)", t[t.type_support >= 30]),
    ], lines)
    block("Where it is worst: vehicle age", [
        ("0-9 yr", t[t.age < 10]),
        ("10-19 yr", t[(t.age >= 10) & (t.age < 20)]),
        ("20-29 yr", t[(t.age >= 20) & (t.age < 30)]),
        ("30+ yr", t[t.age >= 30]),
    ], lines)
    block("Where it is worst: fields the seller did not fill in", [
        ("mileage present", t[t.mileage.notna()]),
        ("mileage missing", t[t.mileage.isna()]),
        ("pump gpm present", t[t.pump_gpm.notna()]),
        ("pump gpm missing", t[t.pump_gpm.isna()]),
        ("body builder present", t[t.body_make != "__missing__"]),
        ("body builder missing", t[t.body_make == "__missing__"]),
    ], lines)
    q = t["price"].quantile([0.25, 0.5, 0.75]).to_list()
    block("Where it is worst: asking-price quartile", [
        (f"Q1 <= ${q[0]:,.0f}", t[t.price <= q[0]]),
        (f"Q2 ${q[0]:,.0f} to ${q[1]:,.0f}", t[(t.price > q[0]) & (t.price <= q[1])]),
        (f"Q3 ${q[1]:,.0f} to ${q[2]:,.0f}", t[(t.price > q[1]) & (t.price <= q[2])]),
        (f"Q4 > ${q[2]:,.0f}", t[t.price > q[2]]),
    ], lines)

    worst = t.nlargest(5, "ape")[["title", "type", "model_year", "price",
                                  "pred", "ape"]].copy()
    worst["model_year"] = worst["model_year"].map(lambda v: f"{v:.0f}")
    worst["price"] = worst["price"].map(lambda v: f"{v:,.0f}")
    worst["pred"] = worst["pred"].map(lambda v: f"{v:,.0f}")
    worst["ape"] = worst["ape"].map(lambda v: f"{v:.0f}")
    worst.columns = ["title", "type", "year", "asking $", "estimate $", "APE %"]
    lines.append("\n#### Five worst single predictions (time-based test set)\n")
    lines.append(worst.to_markdown(index=False))
    lines.append("")


def worked_example(train, test, lines):
    m = CompsModel().fit(train)
    row = test.sort_values("price", ascending=False).iloc[0]
    pred, sd = m.predict_one(row)
    mi = ("no mileage reported" if pd.isna(row["mileage"])
          else f"{int(row['mileage']):,} mi")
    lines.append("\n#### Worked example: what a seller would actually see\n")
    lines.append(f"Subject: **{row['title']}** ({row['type']}, {row['region']}, "
                 f"{row['model_year']:.0f}, {mi})\n")
    lines.append(f"Estimate **${pred:,.0f}**, 90% band "
                 f"${pred * np.exp(-1.645 * sd):,.0f} to "
                 f"${pred * np.exp(1.645 * sd):,.0f}. "
                 f"Actual asking price ${row['price']:,.0f}.\n")
    ex = m.explain(row)
    ex["price"] = ex["price"].map(lambda v: f"{v:,.0f}")
    ex["model_year"] = ex["model_year"].map(lambda v: f"{v:.0f}")
    lines.append(ex.to_markdown(index=False))
    lines.append("")


def evaluate(d, scope, lines, deep):
    d = d.sort_values("last_modified").reset_index(drop=True)
    cut = int(len(d) * (1 - TEST_FRACTION))
    cut_date = d.loc[cut, "last_modified"]
    tr_t, te_t = d.iloc[:cut].copy(), d.iloc[cut:].copy()

    lines.append(f"\n## Scope: {scope}\n")
    lines.append(f"rows **{len(d)}**, "
                 f"mileage present on {100*d['mileage'].notna().mean():.0f}%, "
                 f"pump gpm on {100*d['pump_gpm'].notna().mean():.0f}%, "
                 f"tank size on {100*d['tank_gal'].notna().mean():.0f}%, "
                 f"engine hours on {100*d['engine_hours'].notna().mean():.0f}%.  ")
    lines.append(f"asking price median ${d['price'].median():,.0f}, "
                 f"range ${d['price'].min():,.0f} to ${d['price'].max():,.0f}.  ")
    lines.append(f"time split cut date **{cut_date.date()}** "
                 f"(train = listings last updated before it).")

    preds = run_split(tr_t, te_t, "Time-based split (primary)", lines)
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(d))
    run_split(d.iloc[perm[:cut]].copy(), d.iloc[perm[cut:]].copy(),
              "Random split (optimistic, shown for contrast)", lines)

    if deep:
        p = preds["comps_k10 (this)"]
        error_distribution(te_t["price"].to_numpy(), p, lines)
        _, sd = CompsModel().fit(tr_t).predict(te_t)
        band_calibration(te_t, p, sd, lines)
        slices(te_t, p, tr_t, lines)
        worked_example(tr_t, te_t, lines)


def main():
    d, n_raw = load()
    app = d[d["family"].isin(EMERGENCY_FAMILIES)].copy()

    lines = ["# Back-test results", ""]
    lines.append(f"Rows parsed from the 40 cached state-page snapshots: **{n_raw}**.  ")
    lines.append(f"After filtering to listings with a vehicle type, a model year "
                 f"and an asking price >= ${MIN_PRICE:,}: **{len(d)}**.  ")
    lines.append(f"Of those, **{len(app)}** are in the emergency-vehicle families "
                 f"the appraisal page names.  ")
    lines.append(f"Listing dates span {d['last_modified'].min().date()} to "
                 f"{d['last_modified'].max().date()}.  ")
    lines.append("Target is the **asking price on an active listing**, not a "
                 "closed sale price. Everything below inherits that limitation.")

    evaluate(app, "emergency apparatus and ambulances (headline)", lines, deep=True)
    evaluate(d, "all priced vehicles on the site", lines, deep=False)

    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "backtest.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
