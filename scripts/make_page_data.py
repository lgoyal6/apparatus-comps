"""Turn results/backtest.md into the JSON the results page reads.

backtest.py writes its tables straight to markdown, so that file is the
committed artifact. Parsing it, rather than reimplementing the model here,
means the page can only ever show what the back-test actually produced. Every
table is looked up by its heading and the parse asserts it found it, so a
change to the report breaks this loudly instead of silently dropping a section.

    python3 scripts/make_page_data.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "results/backtest.md"
OUT = ROOT / "docs" / "data"


def tables(text: str) -> dict[tuple[str, str], list[dict]]:
    """Every markdown table, keyed by (scope heading, sub-heading).

    The report covers two scopes and both contain a table called "Time-based
    split (primary)". Keying on the sub-heading alone lets the second silently
    overwrite the first, which puts the wrong numbers under the right label.
    """
    out: dict[tuple[str, str], list[dict]] = {}
    scope, heading = "", ""
    rows: list[list[str]] = []
    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            scope, heading, rows = line.lstrip("#").strip(), "", []
            continue
        if line.startswith("#"):
            heading, rows = line.lstrip("#").strip(), []
            continue
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):   # the separator row
                continue
            rows.append(cells)
            if len(rows) > 1:
                head = rows[0]
                out[(scope, heading)] = [dict(zip(head, r)) for r in rows[1:]]
        elif rows:
            rows = []
    return out


def num(v: str) -> float | None:
    v = v.replace(",", "").replace("$", "").replace("%", "").strip()
    if v in ("", "n/a"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def numeric(rows: list[dict], keep_text: tuple[str, ...]) -> list[dict]:
    out = []
    for r in rows:
        row = {}
        for k, v in r.items():
            key = k.strip()
            row[key] = v if key in keep_text else (num(v) if num(v) is not None else v)
        out.append(row)
    return out


def error_percentiles(rows: list[dict]) -> list[dict]:
    """Normalise the error-distribution table.

    Its header is `| percentile of |APE| | value (%) |`, which has pipe
    characters inside a cell, so splitting the row on pipes does not line the
    columns up. Read it positionally instead: first cell is the percentile,
    last is the number.
    """
    out = []
    for r in rows:
        cells = [str(v).strip() for v in r.values() if str(v).strip()]
        label, value = cells[0], num(cells[-1])
        assert value is not None, f"unparsable error percentile row: {r!r}"
        out.append({"percentile": label, "ape_pct": value})
    return out


def main() -> None:
    text = SRC.read_text()
    t = tables(text)

    # Only the headline scope. The report's second scope covers every priced
    # vehicle on the site, which is a different question.
    scopes = sorted({k[0] for k in t})
    HEADLINE = next(s for s in scopes if "emergency apparatus" in s)

    def need(name: str) -> list[dict]:
        key = (HEADLINE, name)
        assert key in t, f"table missing from backtest.md: {key!r}"
        return t[key]

    payload = {
        "scope_heading": HEADLINE,
        "models_time": numeric(need("Time-based split (primary)"), ("model",)),
        "models_random": numeric(need("Random split (optimistic, shown for contrast)"), ("model",)),
        "error_percentiles": error_percentiles(need("Error distribution, comps_k10, time-based test set")),
        "bands": numeric(need("Is the error bar honest?"), ("band", "median band width (hi/lo)")),
        "by_price": numeric(need("Where it is worst: asking-price quartile"), ("slice",)),
        "by_age": numeric(need("Where it is worst: vehicle age"), ("slice",)),
        "by_support": numeric(need("Where it is worst: how much training support the type had"), ("slice",)),
        "worst": numeric(need("Five worst single predictions (time-based test set)"), ("title", "type")),
        "scope": {
            # Read out of the prose so the page cannot claim a bigger sample
            # than the report does.
            "rows_parsed": int(re.search(r"snapshots: \*\*(\d+)\*\*", text).group(1)),
            "rows_in_scope": int(re.search(r"\*\*(\d+)\*\* are in the emergency-vehicle families", text).group(1)),
            "target": "asking price on an active listing, not a closed sale",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "backtest.json"
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} kB")
    for k, v in payload.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} rows")


if __name__ == "__main__":
    main()
