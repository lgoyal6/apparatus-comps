// Draws docs/data/backtest.json, which scripts/make_page_data.py parses out of
// results/backtest.md. That file is what backtest.py wrote, so every number
// here is one the back-test produced rather than one recomputed in a browser.

const el = (id) => document.getElementById(id);
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const state = { data: null, split: 'models_time', pct: 2, slice: 'by_price' };

const SLICES = {
  by_price: { label: 'asking price', note: 'Cheap vehicles are the hard ones.' },
  by_age: { label: 'vehicle age', note: 'The oldest trucks are the worst, and the thinnest slice.' },
  by_support: { label: 'training support', note: 'More examples of a type did not help.' },
};

const usd = (v) => `$${Math.round(v).toLocaleString('en-US')}`;

function labelOnPaper(ctx, text, x, y, align = 'center') {
  const w = ctx.measureText(text).width;
  const left = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
  const prev = ctx.fillStyle;
  ctx.fillStyle = css('--paper');
  ctx.fillRect(left - 3, y - 11, w + 6, 14);
  ctx.fillStyle = prev;
  ctx.textAlign = align;
  ctx.fillText(text, x, y);
}

function fitCanvas(canvas, h0) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w0 = canvas.clientWidth || 1200;
  canvas.width = Math.round(w0 * dpr);
  canvas.height = Math.round(h0 * dpr);
  canvas.style.height = h0 + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w0, h0);
  return { ctx, w: w0, h: h0 };
}

const pcts = () => state.data.error_percentiles;
const key = (r) => r.percentile;
const val = (r) => r.ape_pct;

function draw() {
  const rows = pcts();
  const { ctx, w, h } = fitCanvas(el('plot'), 260);
  const pad = { l: 62, r: 26, t: 22, b: 48 };
  const iw = w - pad.l - pad.r;
  const ih = h - pad.t - pad.b;
  // Clipped at 200%: p99 and max are 477% and 858% and would squash everything
  // below p90 into the axis. The two clipped points are labelled where they go.
  const top = 200;
  const X = (i) => pad.l + (i / (rows.length - 1)) * iw;
  const Y = (v) => pad.t + ih - (Math.min(v, top) / top) * ih;

  ctx.strokeStyle = css('--hair');
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, pad.t + ih); ctx.lineTo(pad.l + iw, pad.t + ih);
  ctx.stroke();
  ctx.font = "11px 'Courier New', monospace";
  ctx.textAlign = 'right';
  for (let v = 0; v <= top; v += 50) {
    ctx.fillStyle = css('--faint');
    ctx.fillText(`${v}%`, pad.l - 8, Y(v) + 3);
    if (v) {
      ctx.strokeStyle = css('--grid');
      ctx.beginPath(); ctx.moveTo(pad.l, Y(v)); ctx.lineTo(pad.l + iw, Y(v)); ctx.stroke();
    }
  }

  const slot = iw / rows.length;
  const bw = slot * 0.56;
  rows.forEach((r, i) => {
    const x = pad.l + slot * i + (slot - bw) / 2;
    const v = val(r);
    const y = Y(v);
    ctx.fillStyle = css('--ox');
    ctx.fillRect(x, y, bw, pad.t + ih - y);
    if (v > top) {
      // Hatch the two that run off the top, so a clipped bar cannot be read as
      // a bar that stopped there.
      ctx.save();
      ctx.beginPath(); ctx.rect(x, pad.t, bw, ih); ctx.clip();
      ctx.strokeStyle = css('--paper');
      ctx.lineWidth = 1.6;
      for (let k = -ih; k < bw + ih; k += 7) {
        ctx.beginPath(); ctx.moveTo(x + k, pad.t + ih); ctx.lineTo(x + k + ih, pad.t); ctx.stroke();
      }
      ctx.restore();
    }
    ctx.font = "12px 'Times New Roman', serif";
    ctx.fillStyle = v > top ? css('--bad') : css('--sub');
    labelOnPaper(ctx, `${v.toFixed(0)}%`, x + bw / 2, y - 7);
    ctx.fillStyle = i === state.pct ? css('--ink') : css('--faint');
    ctx.font = "11px 'Courier New', monospace";
    ctx.textAlign = 'center';
    ctx.fillText(key(r), x + bw / 2, pad.t + ih + 16);
  });

  ctx.textAlign = 'left';
  ctx.fillStyle = css('--faint');
  ctx.font = "11px 'Courier New', monospace";
  ctx.fillText('absolute percentage error, held-out set (hatched bars run past 200%)', pad.l, h - 8);
}

function render() {
  const rows = pcts();
  const r = rows[state.pct];
  const models = state.data[state.split];
  const comps = models.find((m) => m.model.startsWith('comps'));
  el('r-pct').textContent = key(r);
  el('r-ape').textContent = `${val(r).toFixed(1)}%`;
  el('r-med').textContent = `${comps['MedAPE_%'].toFixed(1)}%`;
  el('r-mean').textContent = `${comps['MAPE_%'].toFixed(1)}%`;
  el('cap-what').textContent =
    `${state.data.scope.rows_in_scope} listings in scope, ${comps.n} held out`;
  el('cap-target').textContent = state.data.scope.target;
  draw();

  const b = el('banner');
  const v = val(r);
  if (v > 100) {
    b.className = 'banner alarm';
    b.textContent =
      `At ${key(r)}, the estimate is off by ${v.toFixed(1)}%. That is the tail an appraisal ` +
      `tool never shows you, and it is ${(rows.length - state.pct)} of these bars wide.`;
  } else if (v >= 30) {
    b.className = 'banner alarm';
    b.textContent =
      `At ${key(r)}, off by ${v.toFixed(1)}%. On the median $50,000 listing that is a miss of ` +
      `about ${usd(50000 * v / 100)}.`;
  } else {
    b.className = 'banner calm';
    b.textContent = `At ${key(r)}, off by ${v.toFixed(1)}%. This is the good end of the distribution.`;
  }
}

function bands() {
  el('bands').innerHTML = state.data.bands
    .map(
      (b) =>
        `<div class="band"><dt>${b.nominal}% nominal</dt>` +
        `<div class="w">${b['median band width (hi/lo)']}</div>` +
        `<div class="sub">wide, and it actually covers ${b['actual coverage']}%</div></div>`,
    )
    .join('');
  const b90 = state.data.bands.find((b) => b.nominal === 90);
  el('band-banner').textContent =
    `Covering nine cases in ten takes a range whose top is ${b90['median band width (hi/lo)']} its bottom. ` +
    `The interval is honest, measured at ${b90['actual coverage']}% coverage, and it is very nearly useless.`;
}

function slices() {
  const rows = state.data[state.slice];
  const head = '<tr><th>slice</th><th>n</th><th>median error</th><th>mean error</th><th>mean $ error</th></tr>';
  const worstRow = rows.reduce((a, b) => (b['MedAPE_%'] > a['MedAPE_%'] ? b : a));
  const body = rows
    .map(
      (r) =>
        `<tr><td class="name">${r.slice}</td><td class="num">${r.n}</td>` +
        `<td class="num ${r === worstRow ? 'bad' : ''}">${r['MedAPE_%'].toFixed(1)}%</td>` +
        `<td class="num">${r['MAPE_%'].toFixed(1)}%</td>` +
        `<td class="num">${usd(r['MAE_$'])}</td></tr>`,
    )
    .join('');
  el('slice').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  el('slice-banner').textContent =
    `Worst here: ${worstRow.slice}, at ${worstRow['MedAPE_%'].toFixed(1)}% median error. ` +
    SLICES[state.slice].note;
}

function worst() {
  const head = '<tr><th>listing</th><th>year</th><th>asking</th><th>estimate</th><th>off by</th></tr>';
  const body = state.data.worst
    .map(
      (r) =>
        `<tr><td class="name">${r.title}</td><td class="num">${r.year}</td>` +
        `<td class="num">${usd(r['asking $'])}</td><td class="num">${usd(r['estimate $'])}</td>` +
        `<td class="num bad">${r['APE %'].toFixed(0)}%</td></tr>`,
    )
    .join('');
  el('worst').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
}

function picker(node, items, current, onPick) {
  node.innerHTML = '';
  items.forEach(({ key, label }) => {
    const b = document.createElement('button');
    b.textContent = label;
    b.setAttribute('aria-pressed', String(key === current()));
    b.addEventListener('click', () => {
      onPick(key);
      [...node.children].forEach((c) => c.setAttribute('aria-pressed', String(c === b)));
    });
    node.appendChild(b);
  });
}

async function main() {
  const res = await fetch('./data/backtest.json');
  if (!res.ok) {
    el('banner').textContent = `Could not load the back-test (HTTP ${res.status}).`;
    return;
  }
  state.data = await res.json();

  picker(
    el('split'),
    [{ key: 'models_time', label: 'Time-based (primary)' }, { key: 'models_random', label: 'Random (for contrast)' }],
    () => state.split,
    (k) => { state.split = k; render(); },
  );
  picker(
    el('slices'),
    Object.entries(SLICES).map(([k, v]) => ({ key: k, label: v.label })),
    () => state.slice,
    (k) => { state.slice = k; slices(); },
  );
  const pct = el('pct');
  pct.max = String(pcts().length - 1);
  pct.value = String(state.pct);
  pct.addEventListener('input', (e) => { state.pct = Number(e.target.value); render(); });
  window.addEventListener('resize', draw);

  render();
  bands();
  slices();
  worst();
}

main();
