"""Build the comparable-sales dataset from cached shopgarage.com facet-page snapshots.

Input : data/raw/state_<slug>.html          (40 SSR snapshots, one per US state)
        data/raw/sitemap-listings-0.xml     (4,180 listing URLs + <lastmod>)
Output: data/dataset.csv

Every field is read out of the page's own __NEXT_DATA__ payload. Nothing is
imputed, invented, or scraped from behind a login. Prices are ASKING prices on
ACTIVE listings, not closed sale prices; see README.
"""

import csv
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data", "dataset.csv")

# attributeId -> column name, read off the category-attribute definitions that
# ship in the listing page payload (label/slug pairs are in the site's own JSON).
ATTR = {
    "cf994aac-a927-4724-8e06-e2ce203e1b4c": "type",          # "Vehicle type"
    "76720e50-0ae7-4eb7-91a7-5647f81e875c": "chassis_make",   # "Chassis"
    "adacd047-7eb8-4200-a1fc-b31c916728e6": "body_make",      # "Body"
    "7d794d55-f1dd-4b5d-90ab-b277e202ceed": "mileage",        # "Mileage"
    "97200a37-b9fc-49eb-ac7b-a0e42093a77d": "engine_hours",   # "Engine hours"
    "ec64460c-d0b9-47aa-87d6-c410d3fbe26c": "pump_hours",     # "Pump hours"
    "7f168d23-ba9b-4f9e-89e3-dcf6116ba1f7": "pump_gpm",       # "Pump size (gpm)"
    "b26315c4-77ca-43f8-bb1f-6b0415ff7ce7": "tank_gal",       # "Tank size (gal)"
    "c032cee3-6023-47e3-9e2e-2a878d19c1e7": "chassis_type",   # "Chassis type"
    "bf1e0441-ad13-4f8e-9c8f-bee12b50c235": "fuel",           # "Fuel Type"
    "c993fd59-8f8b-4800-abd8-b82664f84c61": "is_4wd",         # "4WD"
}

# US Census regions, used as the coarse "region" feature.
REGION = {}
for _r, _states in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for _s in _states.split():
        REGION[_s] = _r

NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
YEAR = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
UUID = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I
)

COLUMNS = [
    "id", "state", "region", "title", "model_year", "price",
    "type", "chassis_make", "body_make", "chassis_type", "fuel", "is_4wd",
    "mileage", "engine_hours", "pump_hours", "pump_gpm", "tank_gal",
    "last_modified", "category_id",
]


def listing_dates():
    """listing uuid -> <lastmod> ISO timestamp, from the public sitemap."""
    path = os.path.join(RAW, "sitemap-listings-0.xml")
    xml = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for loc, mod in re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", xml):
        m = UUID.search(loc)
        if m:
            out[m.group(1).lower()] = mod
    return out


def main():
    dates = listing_dates()
    rows, seen = [], set()
    files = sorted(glob.glob(os.path.join(RAW, "state_*.html")))
    for path in files:
        html = open(path, encoding="utf-8", errors="replace").read()
        m = NEXT_DATA.search(html)
        if not m:
            continue
        props = json.loads(m.group(1))["props"]["pageProps"]
        params = (props.get("page") or {}).get("searchParams", {})
        state = (params.get("stateQuery") or [None])[0]
        for p in props.get("initialListingPreviews") or []:
            if p["id"] in seen or p.get("status") != "ACTIVE":
                continue
            if p.get("isAuction"):          # auctions are a different price process
                continue
            seen.add(p["id"])
            r = {c: "" for c in COLUMNS}
            r["id"] = p["id"]
            r["state"] = state or ""
            r["region"] = REGION.get(state, "")
            r["title"] = p["listingTitle"]
            r["price"] = p["sellingPrice"]
            r["category_id"] = p.get("categoryId", "")
            r["last_modified"] = dates.get(p["id"].lower(), "")
            y = YEAR.search(p["listingTitle"] or "")
            r["model_year"] = y.group(1) if y else ""
            for a in p.get("listingAttributes") or []:
                col = ATTR.get(a["attributeId"])
                if col:
                    r[col] = a["value"]
            rows.append(r)

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"snapshots parsed : {len(files)}")
    print(f"rows written     : {len(rows)}  -> {OUT}")


if __name__ == "__main__":
    main()
