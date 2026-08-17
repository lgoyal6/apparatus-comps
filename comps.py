"""Comparable-sales estimator for emergency-vehicle listings.

Two models, both deliberately small:

  CompsModel  - k-nearest-comparables with an explicit, hand-written distance
                function. Every prediction can be shown to a seller as "here are
                the 10 units we priced you against, and here is how far each one
                is from yours". That is the whole point.
  GbtModel    - HistGradientBoostingRegressor on log price, as the "does a
                black box do better" control.

Both predict log(price) and exponentiate, because apparatus prices span
$5k to $3.2M and absolute error on a raw-dollar fit is dominated by the top end.
"""

import numpy as np
import pandas as pd

CURRENT_YEAR = 2026

# Vehicle types grouped into families. A rescue-pumper is a sensible comparable
# for a pumper; an ambulance is not. Without this, rare types have no neighbours
# at all and fall back to whatever happens to be closest in age.
FAMILY = {}
for _fam, _types in {
    "pumper": "pumper-engine pumper-tanker rescue-pumper mini-pumper quick-attack telesquirt",
    "aerial": "aerial-ladder quint platform",
    "tanker": "tanker-tender",
    "brush": "brush-truck wildland-unit",
    "rescue": "heavy-rescue medium-rescue light-rescue mini-rescue squad",
    "command": "command-unit command-truck",
    "ambulance": "type-1 type-2 type-3",
    "refuse": "rear_loader front_loader automated_side side_loader roll_off hooklift",
    "sewer": "hydrovac jetter septic combination",
    "dump": "dump-truck boom-truck",
}.items():
    for _t in _types.split():
        FAMILY[_t] = _fam

# The vehicle types the appraisal page actually names: "fire trucks, ambulances,
# command vehicles, and specialized emergency vehicles".
EMERGENCY_FAMILIES = {"pumper", "aerial", "tanker", "brush", "rescue",
                      "command", "ambulance"}

# ---------------------------------------------------------------- distance ---
# Weights are in "penalty units". Read them as: a different vehicle family costs
# as much as ~24 model years of age difference, i.e. we essentially never
# compare a ladder truck to an ambulance.
W_TYPE = 1.2        # same family, different type (pumper vs rescue-pumper)
W_FAMILY = 3.0      # different family (pumper vs ambulance)
W_MAKE = 0.6        # chassis manufacturer
W_BODY = 0.5        # apparatus body builder (Pierce, E-One, ...)
W_REGION = 0.4
W_AGE = 1.8         # per AGE_SCALE years, capped
W_MILEAGE = 0.4     # per MILE_SCALE in log-miles, capped
W_PUMP = 0.5        # per PUMP_SCALE gpm, capped
W_TANK = 0.4        # per TANK_SCALE gal, capped

AGE_SCALE, MILE_SCALE, PUMP_SCALE, TANK_SCALE = 8.0, 1.0, 500.0, 500.0
CAP = 2.0           # no single numeric axis can dominate
MISSING_PEN = 0.5   # cost of "one side does not report this field"

K = 10              # comparables per prediction
EPS = 0.75          # weight softening: w = 1 / (EPS + distance)

NUMERIC = ["age", "log_mileage", "pump_gpm", "tank_gal"]
CATEGORICAL = ["type", "family", "chassis_make", "body_make", "region"]


def prepare(df):
    """Frame -> modelling frame. No imputation; missing stays missing."""
    d = df.copy()
    d["age"] = CURRENT_YEAR - d["model_year"]
    d["log_mileage"] = np.log1p(d["mileage"])
    d["log_price"] = np.log(d["price"])
    d["family"] = d["type"].map(FAMILY).fillna("other")
    for c in CATEGORICAL:
        d[c] = d[c].astype("object").where(d[c].notna(), "__missing__")
    return d


def _num_pen(q, c, scale, weight):
    """Penalty for one numeric axis, vectorised over the candidate array c."""
    if pd.isna(q):
        return np.full(len(c), weight * MISSING_PEN)
    out = np.where(
        np.isnan(c),
        weight * MISSING_PEN,
        weight * np.minimum(np.abs(c - q) / scale, CAP),
    )
    return out


class CompsModel:
    """k-nearest comparables with a documented distance function."""

    def __init__(self, k=K):
        self.k = k

    def fit(self, train):
        self.tr = train.reset_index(drop=True)
        self._age = self.tr["age"].to_numpy(dtype=float)
        self._mi = self.tr["log_mileage"].to_numpy(dtype=float)
        self._pump = self.tr["pump_gpm"].to_numpy(dtype=float)
        self._tank = self.tr["tank_gal"].to_numpy(dtype=float)
        self._type = self.tr["type"].to_numpy()
        self._family = self.tr["family"].to_numpy()
        self._make = self.tr["chassis_make"].to_numpy()
        self._body = self.tr["body_make"].to_numpy()
        self._region = self.tr["region"].to_numpy()
        self._logp = self.tr["log_price"].to_numpy(dtype=float)
        return self

    def distances(self, row):
        same_fam = self._family == row["family"]
        same_type = self._type == row["type"]
        d = np.where(same_type, 0.0, np.where(same_fam, W_TYPE, W_FAMILY))
        d = d + W_MAKE * (self._make != row["chassis_make"]).astype(float)
        d = d + W_BODY * (self._body != row["body_make"]).astype(float)
        d = d + W_REGION * (self._region != row["region"]).astype(float)
        d = d + _num_pen(row["age"], self._age, AGE_SCALE, W_AGE)
        d = d + _num_pen(row["log_mileage"], self._mi, MILE_SCALE, W_MILEAGE)
        d = d + _num_pen(row["pump_gpm"], self._pump, PUMP_SCALE, W_PUMP)
        d = d + _num_pen(row["tank_gal"], self._tank, TANK_SCALE, W_TANK)
        return d

    def explain(self, row):
        """Return the comparables actually used, for showing to a seller."""
        d = self.distances(row)
        idx = np.argsort(d)[: self.k]
        w = 1.0 / (EPS + d[idx])
        out = self.tr.iloc[idx][
            ["title", "price", "type", "chassis_make", "body_make", "region",
             "model_year", "mileage", "pump_gpm", "tank_gal"]
        ].copy()
        out["distance"] = d[idx].round(3)
        out["weight"] = (w / w.sum()).round(3)
        return out

    def predict_one(self, row):
        d = self.distances(row)
        idx = np.argsort(d)[: self.k]
        w = 1.0 / (EPS + d[idx])
        w = w / w.sum()
        lp = self._logp[idx]
        mu = float(np.sum(w * lp))
        # weighted sd of the comparables, in log space -> a multiplicative band
        var = float(np.sum(w * (lp - mu) ** 2))
        sd = float(np.sqrt(max(var, 0.0)))
        return np.exp(mu), sd

    def predict(self, test):
        preds, sds = [], []
        for _, row in test.iterrows():
            p, s = self.predict_one(row)
            preds.append(p)
            sds.append(s)
        return np.array(preds), np.array(sds)


class GbtModel:
    """Gradient-boosted trees on log price. Control, not the deliverable."""

    def __init__(self, seed=0):
        from sklearn.ensemble import HistGradientBoostingRegressor

        self.m = HistGradientBoostingRegressor(
            max_depth=4, max_iter=300, learning_rate=0.06,
            min_samples_leaf=8, l2_regularization=1.0, random_state=seed,
        )

    def _X(self, d, fit=False):
        cats = d[CATEGORICAL].astype(str)
        if fit:
            self.levels = {c: {v: i for i, v in enumerate(sorted(cats[c].unique()))}
                           for c in CATEGORICAL}
        enc = np.column_stack(
            [cats[c].map(self.levels[c]).fillna(-1).to_numpy(dtype=float)
             for c in CATEGORICAL]
        )
        return np.column_stack([enc, d[NUMERIC].to_numpy(dtype=float)])

    def fit(self, train):
        self.m.fit(self._X(train, fit=True), train["log_price"].to_numpy())
        return self

    def predict(self, test):
        return np.exp(self.m.predict(self._X(test))), np.zeros(len(test))


class MedianBaseline:
    """Median asking price within (type, age decade), backing off to type, then all."""

    def fit(self, train):
        t = train.copy()
        t["decade"] = (t["age"] // 10).astype("Int64")
        self.g2 = t.groupby(["type", "decade"], observed=True)["price"].median()
        self.g1 = t.groupby("type", observed=True)["price"].median()
        self.g0 = float(t["price"].median())
        return self

    def predict(self, test):
        out = []
        for _, r in test.iterrows():
            dec = int(r["age"] // 10) if pd.notna(r["age"]) else None
            v = self.g2.get((r["type"], dec), np.nan) if dec is not None else np.nan
            if pd.isna(v):
                v = self.g1.get(r["type"], np.nan)
            if pd.isna(v):
                v = self.g0
            out.append(float(v))
        return np.array(out), np.zeros(len(test))


class GlobalMedian:
    def fit(self, train):
        self.v = float(train["price"].median())
        return self

    def predict(self, test):
        return np.full(len(test), self.v), np.zeros(len(test))
