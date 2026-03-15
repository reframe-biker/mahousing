"""
audit_nza.py — NZA zoning data diagnostic for MA Housing Report Card
Run from repo root: python audit_nza.py > nza_audit.txt
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

NZA_PATH   = Path("data/MA_Zoning_Atlas_2023.geojson")
STATE_PATH = Path("data/statewide.json")

FOCUS_TOWNS = [
    "Rochester", "Norwell", "Plainfield", "Ayer",
    "Everett", "North Reading", "Middleborough", "Somerville",
]

print("Loading...", flush=True)
with open(NZA_PATH, encoding="utf-8") as f:
    features = json.load(f)["features"]
with open(STATE_PATH, encoding="utf-8") as f:
    statewide = json.load(f)
town_lookup = {t["name"]: t for t in statewide}
print(f"NZA: {len(features)} districts | statewide.json: {len(statewide)} towns\n")

def score_district(p):
    if p.get("overlay") == 1:      return False, None, "skip:overlay"
    if p.get("extinct") == 1:      return False, None, "skip:extinct"
    if p.get("published") != 1:    return False, None, "skip:unpublished"
    if p.get("status") != "done":  return False, None, f"skip:status={p.get('status')!r}"
    if not (p.get("acres") or 0) > 0: return False, None, "skip:zero-acres"
    if p.get("nonresidential_type"):
        return False, None, f"skip:nonresidential({p['nonresidential_type']})"
    if p.get("affordable_district") == 1:
        return True, 0.0, "affordable_district→0.0"
    f3 = p.get("family3_treatment")
    f4 = p.get("family4_treatment")
    s = max(1.0 if f3 == "allowed" else 0.0, 1.0 if f4 == "allowed" else 0.0)
    return True, s, f"f3={f3!r}  f4={f4!r}  →  {s}"

def recompute_town(props_list):
    res_acres, weighted = 0.0, 0.0
    for p in props_list:
        inc, s, _ = score_district(p)
        if inc:
            a = float(p.get("acres") or 0)
            res_acres += a
            weighted  += s * a
    return round(weighted / res_acres * 100, 1) if res_acres else None

by_town = defaultdict(list)
for feat in features:
    j = feat["properties"].get("jurisdiction")
    if j:
        by_town[j].append(feat["properties"])

# ── SECTION 1: All family3/4 treatment values ────────────────────────────────
print("=" * 68)
print("SECTION 1: All family3/family4 treatment values in dataset")
print("=" * 68)
f3_counts, f4_counts = defaultdict(int), defaultdict(int)
for feat in features:
    p = feat["properties"]
    f3_counts[str(p.get("family3_treatment"))] += 1
    f4_counts[str(p.get("family4_treatment"))] += 1
print("\nfamily3_treatment:")
for val, n in sorted(f3_counts.items(), key=lambda x: -x[1]):
    print(f"  {val:30s}  {n:6,}")
print("\nfamily4_treatment:")
for val, n in sorted(f4_counts.items(), key=lambda x: -x[1]):
    print(f"  {val:30s}  {n:6,}")

# ── SECTION 2: District breakdown for suspicious towns ───────────────────────
print("\n\n" + "=" * 68)
print("SECTION 2: District-by-district breakdown for suspicious towns")
print("  ✓ = 1.0 (allowed)  ✗ = 0.0  – = filtered out")
print("=" * 68)
for town in FOCUS_TOWNS:
    districts = by_town.get(town, [])
    td = town_lookup.get(town, {})
    reported = td.get("metrics", {}).get("pct_land_multifamily_byright", "?")
    print(f"\n{'─'*60}")
    print(f"  {town}  (reported: {reported}%  source: {td.get('zoning_source')}  mbta: {td.get('mbta_status')})")
    if not districts:
        print("  *** NOT IN NZA ***")
        continue
    res_acres, weighted = 0.0, 0.0
    for p in sorted(districts, key=lambda p: -(p.get("acres") or 0)):
        acres = float(p.get("acres") or 0)
        inc, s, reason = score_district(p)
        dname = (p.get("name") or p.get("district_name") or "(unnamed)")[:35]
        if inc:
            res_acres += acres
            weighted  += s * acres
            flag = "✓" if s == 1.0 else "✗"
        else:
            flag = "–"
        print(f"  {flag} {dname:36s}  {acres:8.1f} ac  {reason}")
    recomp = round(weighted / res_acres * 100, 1) if res_acres else None
    print(f"\n  → Residential denominator: {res_acres:.1f} ac")
    print(f"  → Recomputed: {recomp}%  (reported: {reported}%)")

# ── SECTION 3: All NZA towns > 50% ──────────────────────────────────────────
print("\n\n" + "=" * 68)
print("SECTION 3: All NZA-sourced towns with reported pct > 50%")
print("=" * 68)
rows = []
for name, td in town_lookup.items():
    if td.get("zoning_source") != "nza": continue
    reported = td.get("metrics", {}).get("pct_land_multifamily_byright")
    if not reported or reported <= 50: continue
    rows.append((name, reported, recompute_town(by_town.get(name, [])),
                 len(by_town.get(name, [])), td.get("mbta_status") or "n/a"))
rows.sort(key=lambda r: -(r[1] or 0))
print(f"\n  {'Town':28s}  {'Reported':>9}  {'Recomputed':>11}  {'Dists':>6}  {'MBTA':>14}")
print("  " + "─" * 76)
for name, rep, recomp, n, mbta in rows:
    print(f"  {name:28s}  {rep:>8}%  {str(recomp)+'%' if recomp else 'n/a':>11}  {n:>6}  {mbta:>14}")

# ── SECTION 4: Acre breakdown for focus towns ────────────────────────────────
print("\n\n" + "=" * 68)
print("SECTION 4: Acre breakdown for focus towns")
print("  (Is nonresidential exclusion shrinking the denominator?)")
print("=" * 68)
for town in FOCUS_TOWNS:
    districts = by_town.get(town, [])
    if not districts: continue
    buckets = defaultdict(float)
    for p in districts:
        a = float(p.get("acres") or 0)
        if p.get("overlay") == 1:           buckets["skip:overlay"] += a
        elif p.get("extinct") == 1:         buckets["skip:extinct"] += a
        elif p.get("published") != 1:       buckets["skip:unpublished"] += a
        elif p.get("status") != "done":     buckets["skip:status"] += a
        elif not a > 0:                     buckets["skip:zero-acres"] += a
        elif p.get("nonresidential_type"):  buckets["nonresidential (excl. from denom)"] += a
        elif p.get("affordable_district") == 1: buckets["residential (affordable→0.0)"] += a
        else:
            f3, f4 = p.get("family3_treatment"), p.get("family4_treatment")
            s = max(1.0 if f3 == "allowed" else 0.0, 1.0 if f4 == "allowed" else 0.0)
            buckets[f"residential (scores {s})"] += a
    total = sum(buckets.values())
    print(f"\n  {town}  (total: {total:.1f} ac)")
    for bucket, acres in sorted(buckets.items()):
        print(f"    {bucket:44s}  {acres:8.1f} ac  ({acres/total*100:.1f}%)")

print("\n\nDone.")