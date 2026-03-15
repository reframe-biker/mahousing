"""
find_nza_errors.py — Identify NZA towns that are likely miscoded
Run from repo root: python find_nza_errors.py > nza_candidates.txt

Applies four suspicion signals to every NZA-sourced town and outputs
a ranked candidate list for manual bylaw review. You do NOT need to
check all 244 NZA towns — just the ones this script flags.

SIGNALS
-------
1. score_after_fix > 50%
   Applies the proposed scoring fix (f4 full credit, f3 = 0.5 * f3).
   Towns that stay above 50% after the fix are worth scrutinising —
   they have large f4='allowed' districts that may be miscoded.

2. MBTA signal
   Towns in active bylaw development, non-compliant, or interim are
   building new multifamily zoning — which they wouldn't need if they
   already had it across most of their land. Strongest signal.
   Weight: 2 points.

3. Production signal
   High zoning score + low/failing production grade is suspicious.
   Genuinely permissive zoning should produce housing.
   Weight: 1 point.

4. Simple district structure
   One or two large f4='allowed' districts is the classic rural bylaw
   misread pattern (Rochester). Complex urban towns with many districts
   are less likely to be miscoded.
   Weight: 1 point.

SUSPICION SCORE: 0–4. Towns scoring 3–4 are strong candidates.
Towns scoring 2 are worth a quick look. Below 2, likely fine.

OUTPUT
------
Ranked table, then a JSON block ready to paste into
data/zoning_nza_known_errors.json after manual review.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

NZA_PATH   = Path("data/MA_Zoning_Atlas_2023.geojson")
STATE_PATH = Path("data/statewide.json")

if not NZA_PATH.exists():
    sys.exit(f"ERROR: {NZA_PATH} not found. Run from repo root.")

print("Loading...", flush=True)
with open(NZA_PATH, encoding="utf-8") as f:
    features = json.load(f)["features"]
with open(STATE_PATH, encoding="utf-8") as f:
    statewide = json.load(f)
town_lookup = {t["fips"]: t for t in statewide}
name_to_fips = {t["name"]: t["fips"] for t in statewide}
print(f"NZA: {len(features)} districts | statewide.json: {len(statewide)} towns\n")


# ── Scoring functions ─────────────────────────────────────────────────────────

def score_current(p):
    """Current pipeline scoring: f3 or f4 'allowed' = 1.0."""
    f3, f4 = p.get("family3_treatment"), p.get("family4_treatment")
    return max(1.0 if f3 == "allowed" else 0.0,
               1.0 if f4 == "allowed" else 0.0)

def score_fixed(p):
    """Proposed scoring: f4 full credit, f3 half credit."""
    f3, f4 = p.get("family3_treatment"), p.get("family4_treatment")
    return max(1.0 if f4 == "allowed" else 0.0,
               0.5 if f3 == "allowed" else 0.0)

def is_filtered(p):
    """Returns True if the pipeline would skip this district."""
    if p.get("overlay") == 1:      return True
    if p.get("extinct") == 1:      return True
    if p.get("published") != 1:    return True
    if p.get("status") != "done":  return True
    if not (p.get("acres") or 0) > 0: return True
    if p.get("nonresidential_type"): return True
    return False

def aggregate(props_list, score_fn):
    """Area-weighted average score for a town, 0-100."""
    res_acres = weighted = 0.0
    for p in props_list:
        if is_filtered(p): continue
        if p.get("affordable_district") == 1:
            res_acres += float(p.get("acres") or 0)
            continue
        a = float(p.get("acres") or 0)
        res_acres += a
        weighted  += score_fn(p) * a
    if res_acres == 0:
        return None
    return round(weighted / res_acres * 100, 1)


# ── Group districts by jurisdiction ──────────────────────────────────────────

by_jurisdiction = defaultdict(list)
for feat in features:
    j = feat["properties"].get("jurisdiction")
    if j:
        by_jurisdiction[j].append(feat["properties"])


# ── Grade helpers ─────────────────────────────────────────────────────────────

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0, None: None}

def production_grade(td):
    return td.get("grades", {}).get("production")


# ── Score every NZA town ──────────────────────────────────────────────────────

results = []

for name, props_list in by_jurisdiction.items():
    fips = name_to_fips.get(name)
    if not fips:
        continue
    td = town_lookup.get(fips, {})
    if td.get("zoning_source") != "nza":
        continue

    score_now   = aggregate(props_list, score_current)
    score_after = aggregate(props_list, score_fixed)

    if score_now is None or score_now <= 50:
        continue  # not a high scorer, skip

    # ── Count residential districts with f4='allowed' ─────────────────────
    res_districts = [p for p in props_list if not is_filtered(p)
                     and not p.get("affordable_district") == 1]
    f4_allowed_districts = [p for p in res_districts
                             if p.get("family4_treatment") == "allowed"]
    n_res = len(res_districts)
    n_f4  = len(f4_allowed_districts)

    # Only flag towns where f4='allowed' is driving the score.
    # If score_after is still high purely from f3 half-credit (no f4 at all),
    # the scoring fix handles it — no error filing needed.
    if n_f4 == 0:
        continue

    # ── Signal 1: Still high after fix ────────────────────────────────────
    sig_still_high = 1 if (score_after is not None and score_after > 50) else 0

    # ── Signal 2: MBTA activity ───────────────────────────────────────────
    mbta = td.get("mbta_status")
    # Non-compliant or interim means they're actively building new MF zoning
    sig_mbta = 2 if mbta in ("non_compliant", "interim") else 0
    # Compliant is ambiguous — could be newly compliant *because* of NZA data,
    # or could be genuinely compliant. Don't penalise.

    # ── Signal 3: Low production despite high zoning ──────────────────────
    prod = production_grade(td)
    prod_val = GRADE_ORDER.get(prod)
    sig_production = 1 if (prod_val is not None and prod_val <= 1) else 0  # D or F

    # ── Signal 4: Simple district structure ───────────────────────────────
    # Few residential districts + f4='allowed' on most of them = rural misread risk
    sig_simple = 1 if (n_res <= 3 and n_f4 >= 1) else 0

    suspicion = sig_still_high + sig_mbta + sig_production + sig_simple

    results.append({
        "name":         name,
        "fips":         fips,
        "score_now":    score_now,
        "score_after":  score_after,
        "n_res_dist":   n_res,
        "n_f4_allowed": n_f4,
        "mbta":         mbta or "n/a",
        "production":   prod or "n/a",
        "suspicion":    suspicion,
        "signals": {
            "still_high_after_fix": bool(sig_still_high),
            "mbta_active":          bool(sig_mbta),
            "low_production":       bool(sig_production),
            "simple_structure":     bool(sig_simple),
        },
    })

results.sort(key=lambda r: (-r["suspicion"], -(r["score_now"] or 0)))


# ── Print table ───────────────────────────────────────────────────────────────

print("=" * 80)
print("CANDIDATE TOWNS FOR MANUAL BYLAW REVIEW")
print("Suspicion score 0-4. Check towns scoring 3-4 first; 2 is worth a look.")
print("Only NZA towns scoring >50% with at least one f4='allowed' district.")
print("=" * 80)
print()
print(f"  {'Town':22s}  {'Now':>6}  {'After fix':>10}  "
      f"{'Res dists':>10}  {'f4 dists':>9}  {'MBTA':>12}  {'Prod':>5}  {'Score':>6}  Signals")
print("  " + "─" * 100)

for r in results:
    sigs = []
    if r["signals"]["still_high_after_fix"]: sigs.append("still-high")
    if r["signals"]["mbta_active"]:          sigs.append("mbta-active")
    if r["signals"]["low_production"]:       sigs.append("low-prod")
    if r["signals"]["simple_structure"]:     sigs.append("simple-struct")

    after_s = f"{r['score_after']}%" if r["score_after"] is not None else "n/a"
    marker  = " ◀ REVIEW" if r["suspicion"] >= 3 else (" ·" if r["suspicion"] == 2 else "")

    print(f"  {r['name']:22s}  {r['score_now']:>5}%  {after_s:>10}  "
          f"{r['n_res_dist']:>10}  {r['n_f4_allowed']:>9}  {r['mbta']:>12}  "
          f"{r['production']:>5}  {r['suspicion']:>5}/4  "
          f"{', '.join(sigs)}{marker}")

# ── Summary ───────────────────────────────────────────────────────────────────

strong    = [r for r in results if r["suspicion"] >= 3]
moderate  = [r for r in results if r["suspicion"] == 2]
low       = [r for r in results if r["suspicion"] <= 1]

print()
print(f"  Strong candidates (3-4):  {len(strong)}")
print(f"  Moderate (2):             {len(moderate)}")
print(f"  Low suspicion (0-1):      {len(low)}")
print()

# ── JSON skeleton for known_errors file ──────────────────────────────────────

print("=" * 80)
print("JSON SKELETON — paste into data/zoning_nza_known_errors.json")
print("after manual review. Remove towns that check out fine.")
print("=" * 80)
print()

nza_filename = NZA_PATH.name
skeleton = {
    "_comment": (
        "Known NZA coding errors by dataset filename. "
        "Entries are automatically ignored when a new dataset is used — "
        "no manual cleanup needed on dataset update."
    ),
    nza_filename: {
        "_comment": "Towns verified as miscoded in this dataset. Add 'reason' after reviewing bylaw.",
        "towns": {}
    }
}

for r in strong:
    skeleton[nza_filename]["towns"][r["fips"]] = {
        "town": r["name"],
        "suspicion": r["suspicion"],
        "score_now": r["score_now"],
        "score_after_fix": r["score_after"],
        "signals": [k for k, v in r["signals"].items() if v],
        "reason": "TODO — verify bylaw before adding",
        "treatment": "null"
    }

print(json.dumps(skeleton, indent=2))
print()
print("Done.")