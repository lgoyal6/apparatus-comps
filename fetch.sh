#!/bin/sh
# How data/raw/ was collected on 2026-08-14. You do NOT need to run this;
# the snapshots are committed and build_dataset.py reads them offline.
#
# Guardrails actually followed:
#   - https://www.shopgarage.com/robots.txt was read first. It disallows
#     /api/ /checkout/ /edit/ /login /dashboard /onboarding /verifycode.
#     Nothing below touches any of those. Everything fetched is an
#     Allow-by-default, indexable, server-rendered marketing/browse page.
#   - read-only GETs, no auth, no forms, no POSTs
#   - >= 1.2 s between requests, single connection, no concurrency
#   - 55 requests to shopgarage.com in total across the whole session:
#     2 robots.txt, 4 sitemaps, 40 state pages, and a handful of one-off
#     verification loads (/appraisal, /, /faq, one listing, one facet page)
#
# Data all comes from each page's own __NEXT_DATA__ SSR payload, which is
# the same JSON the browser receives.

set -eu
UA='Mozilla/5.0 (research; read-only)'
OUT="$(dirname "$0")/data/raw"
mkdir -p "$OUT"

curl -sL -A "$UA" https://www.shopgarage.com/robots.txt
sleep 1.2
curl -sL -A "$UA" https://www.shopgarage.com/sitemap-listings-0.xml \
     -o "$OUT/sitemap-listings-0.xml"

for s in california texas florida new-york pennsylvania illinois ohio georgia \
         north-carolina michigan new-jersey virginia washington arizona \
         massachusetts tennessee indiana missouri maryland wisconsin colorado \
         minnesota south-carolina alabama louisiana kentucky oregon oklahoma \
         connecticut iowa mississippi arkansas kansas nevada new-mexico \
         nebraska west-virginia idaho new-hampshire maine; do
  sleep 1.2
  curl -sL -A "$UA" "https://www.shopgarage.com/state/$s" -o "$OUT/state_$s.html"
done
