"""Reproduce the hyperparameter choice baked into comps.py.

The sweep runs on TRAIN ONLY, split chronologically again into an inner
train/validation pair. The 30% held-out test set used by backtest.py is never
touched here, so the reported test numbers are not selection-inflated.

Run:  python tune.py
"""

import numpy as np

import comps as C
from backtest import load

TEST_FRACTION = 0.30
INNER_FRACTION = 0.30


def score(model, va):
    p, _ = model.predict(va)
    y = va["price"].to_numpy()
    ape = np.abs(p - y) / y
    return 100 * np.median(ape), 100 * np.mean(ape), np.mean(np.abs(p - y))


def main():
    d, _ = load()
    d = d[d["family"].isin(C.EMERGENCY_FAMILIES)]
    d = d.sort_values("last_modified").reset_index(drop=True)
    train = d.iloc[: int(len(d) * (1 - TEST_FRACTION))]
    icut = int(len(train) * (1 - INNER_FRACTION))
    itr, iva = train.iloc[:icut].copy(), train.iloc[icut:].copy()
    print(f"inner train {len(itr)}, inner validation {len(iva)}, "
          f"held-out test never touched here ({len(d) - len(train)} rows)")

    grid = []
    for k in (3, 5, 7, 10, 15, 20):
        for eps in (0.05, 0.25, 0.75):
            for wfam in (2.0, 3.0, 5.0):
                for wage in (0.6, 1.0, 1.8):
                    for wmi in (0.4, 0.8, 1.6):
                        C.EPS, C.W_FAMILY, C.W_AGE, C.W_MILEAGE = eps, wfam, wage, wmi
                        med, mape, mae = score(C.CompsModel(k=k).fit(itr), iva)
                        grid.append((med, mape, mae, k, eps, wfam, wage, wmi))

    grid.sort()
    print("\ntop 5 by inner-validation median APE:")
    print(f"{'MedAPE%':>8} {'MAPE%':>7} {'MAE$':>9}  k  eps  w_family w_age w_mileage")
    for g in grid[:5]:
        print(f"{g[0]:8.1f} {g[1]:7.1f} {g[2]:9,.0f}  {g[3]:<3}{g[4]:<5}"
              f"{g[5]:<9}{g[6]:<6}{g[7]}")
    print("\nbaked into comps.py: k=%d EPS=%.2f W_FAMILY=%.1f W_AGE=%.1f "
          "W_MILEAGE=%.1f" % (10, 0.75, 3.0, 1.8, 0.4))


if __name__ == "__main__":
    main()
