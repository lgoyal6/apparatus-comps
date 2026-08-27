// The estimator, actually estimating.
//
// comps.py and the 903-row dataset are copied verbatim into docs/ and loaded
// through pyodide with numpy and pandas, so the model pricing your truck is the
// one the back-test scored. It is a heavier load than the other pages here
// because pandas is, and the page says so while it waits.
//
// The comparables table is the point. An estimate with a range attached is only
// as good as the ten rows it came from, and those rows are usually hidden.
(() => {
  const el = (id) => document.getElementById(id);
  const usd = (v) => `$${Math.round(v).toLocaleString('en-US')}`;
  let api = null;

  const FIELDS = ['t-type', 't-year', 't-miles', 't-region', 't-chassis', 't-body', 't-pump', 't-tank'];

  function fillSelect(id, values, preferred) {
    const sel = el(id);
    sel.innerHTML = values.map((v) => `<option>${v}</option>`).join('');
    if (preferred && values.includes(preferred)) sel.value = preferred;
  }

  function currentRow() {
    const num = (id) => {
      const v = el(id).value.trim();
      return v === '' ? null : Number(v);
    };
    return {
      type: el('t-type').value,
      model_year: num('t-year'),
      mileage: num('t-miles'),
      region: el('t-region').value,
      chassis_make: el('t-chassis').value,
      body_make: el('t-body').value,
      pump_gpm: num('t-pump'),
      tank_gal: num('t-tank'),
    };
  }

  function estimate() {
    if (!api) return;
    let out;
    try {
      out = JSON.parse(api.predict(JSON.stringify(currentRow())));
    } catch (e) {
      el('est-banner').className = 'banner alarm';
      el('est-banner').textContent = `The model could not price that: ${e}`;
      return;
    }
    el('e-point').textContent = usd(out.point);
    el('e-band').textContent = `${usd(out.lo)} to ${usd(out.hi)}`;
    const width = out.hi / Math.max(out.lo, 1);
    const w = el('e-width');
    w.textContent = `${width.toFixed(1)}x`;
    w.className = width > 5 ? 'wide' : '';
    el('e-k').textContent = out.comps.length;

    const head =
      '<tr><th>comparable</th><th>year</th><th>miles</th><th>asking</th><th>weight</th></tr>';
    el('comps').innerHTML =
      `<thead>${head}</thead><tbody>` +
      out.comps
        .map(
          (c) =>
            `<tr><td class="title">${c.title}</td><td class="num">${c.model_year ?? '-'}</td>` +
            `<td class="num">${c.mileage == null ? '-' : Math.round(c.mileage).toLocaleString('en-US')}</td>` +
            `<td class="num">${usd(c.price)}</td>` +
            `<td class="num">${(c.weight * 100).toFixed(0)}%</td></tr>`,
        )
        .join('') +
      '</tbody>';

    const b = el('est-banner');
    // The width is the honest headline, so the banner leads with it.
    if (width > 6) {
      b.className = 'banner alarm';
      b.textContent =
        `${usd(out.point)}, and the range that actually covers nine cases in ten runs from ` +
        `${usd(out.lo)} to ${usd(out.hi)}. That is ${width.toFixed(1)}x wide, which means the ` +
        `ten comparables disagree badly. Read them, not the number.`;
    } else {
      b.className = 'banner';
      b.textContent =
        `${usd(out.point)}, within ${usd(out.lo)} to ${usd(out.hi)}. The comparables agree ` +
        `unusually well for this set, which is worth as much as the estimate itself.`;
    }
  }

  async function boot() {
    try {
      const py = await loadPyodide();
      el('est-engine').textContent = 'loading numpy and pandas';
      await py.loadPackage(['numpy', 'pandas']);
      py.FS.writeFile('comps.py', await (await fetch('./data/comps.py')).text());
      py.FS.writeFile('dataset.csv', await (await fetch('./data/dataset.csv')).text());
      const built = py.runPython(`
import json, math
import pandas as pd, numpy as np
import comps

_raw = pd.read_csv("dataset.csv")
_train = comps.prepare(_raw)
_model = comps.CompsModel().fit(_train)

def _vocab():
    def top(col, n):
        return [str(v) for v in _raw[col].value_counts().head(n).index]
    return json.dumps({
        "type": top("type", 24),
        "region": top("region", 8),
        "chassis_make": top("chassis_make", 18),
        "body_make": top("body_make", 18),
    })

def _predict(payload):
    q = json.loads(payload)
    row = pd.Series({
        "type": q["type"], "region": q["region"],
        "chassis_make": q["chassis_make"], "body_make": q["body_make"],
        "model_year": q["model_year"], "mileage": q["mileage"],
        "pump_gpm": q["pump_gpm"], "tank_gal": q["tank_gal"],
        "price": 1.0,
    })
    frame = comps.prepare(pd.DataFrame([row]))
    r = frame.iloc[0]
    point, sd = _model.predict_one(r)
    # The published band: 1.645 sd each way in log space is the 90% one the
    # back-test measured coverage for.
    lo, hi = point * math.exp(-1.645 * sd), point * math.exp(1.645 * sd)
    ex = _model.explain(r)
    comps_out = [
        {
            "title": str(x["title"])[:64],
            "model_year": None if pd.isna(x["model_year"]) else int(x["model_year"]),
            "mileage": None if pd.isna(x["mileage"]) else float(x["mileage"]),
            "price": float(x["price"]),
            "weight": float(x["weight"]),
        }
        for _, x in ex.iterrows()
    ]
    return json.dumps({"point": float(point), "lo": float(lo), "hi": float(hi),
                       "comps": comps_out})

{"vocab": _vocab, "predict": _predict}
`).toJs({ dict_converter: Object.fromEntries });
      api = built;

      const v = JSON.parse(api.vocab());
      fillSelect('t-type', v.type, 'aerial-ladder');
      fillSelect('t-region', v.region, 'Northeast');
      fillSelect('t-chassis', v.chassis_make, 'Pierce');
      fillSelect('t-body', v.body_make, 'Pierce');
      el('est-engine').textContent = 'comps.py running in your tab, via pyodide';
      FIELDS.forEach((id) => el(id).addEventListener('input', estimate));
      FIELDS.forEach((id) => el(id).addEventListener('change', estimate));
      estimate();
    } catch (e) {
      el('est-engine').textContent = 'the engine did not start';
      el('est-banner').className = 'banner alarm';
      el('est-banner').textContent = `Could not start the estimator: ${e}`;
    }
  }
  boot();
})();
