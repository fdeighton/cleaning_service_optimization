"""Data-quality audit: reduce false 'Unknown' values using only in-schedule evidence.

Targets three buckets across every CSV in schedule_data/:
  * Unknown area type   (derived classifier returns Unknown)
  * No Explicit Task     (task text = '(no explicit task ...)')
  * Unknown frequency    (frequency = 'Unknown')

For each, infers a value ONLY from data already present:
  - the location string itself (a facility keyword the classifier vocab missed)
  - the row's own source_text (which often states the task / cadence)
  - sibling rows in the same schedule block (identical source_text)
  - other occurrences of the same location (+ task) elsewhere in the schedule

No external knowledge, no invented values. Auto-fill applies HIGH confidence only.

Outputs:
  output/data_quality/inference_log.csv     every inference + reason + confidence
  output/data_quality/manual_review.csv     records still requiring human classification
and prints a Before/After validation report.
"""
from __future__ import annotations

import csv
import glob
import os
import re
from collections import Counter, defaultdict

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULE_DIR = os.path.join(REPO, "schedule_data")
OUT_DIR = os.path.join(REPO, "output", "data_quality")

# classifier vocabulary = the same one the dashboard uses
_kw = pd.read_csv(os.path.join(REPO, "config", "area_type_keywords.csv"), dtype=str)
KW = [(str(a).strip().lower(), str(b).strip()) for a, b in zip(_kw.iloc[:, 0], _kw.iloc[:, 1]) if str(a).strip()]
LABELS = sorted({b for _, b in KW})


def classify(loc):
    t = str(loc).lower()
    for kw, at in KW:
        if kw in t:
            return at
    return "Unknown"


# HIGH-confidence area keywords the base vocab lacks — each term is literally
# present in the location name (no external inference).
EXTRA_AREA = [
    ("bar", "Amenity - Indoor"), ("coffee", "Amenity - Indoor"), ("lounge", "Amenity - Indoor"),
    ("bicycle", "Back-of-House"), ("bike", "Back-of-House"), ("locker", "Back-of-House"),
    ("electrical", "Back-of-House"), ("janitor", "Back-of-House"), ("sitting area", "Amenity - Indoor"),
    ("terrace", "Amenity - Outdoor"), ("balcony", "Amenity - Outdoor"), ("courtyard", "Amenity - Outdoor"),
    ("security", "Lobby / Entrance"), ("concierge", "Lobby / Entrance"), ("reception", "Lobby / Entrance"),
    ("stair", "Circulation"),
]
# surface / building-wide tokens that legitimately have no area type
SURFACE_TOKENS = ("carpet", "baseboard", "ventilation", "glass", "door", "fire cabinet",
                  "threshold", "wallpaper", "metal", "building-wide", "all mopped", "mirror",
                  "lighting", "window", "floors (", "floor (")

GEN_VERBS = [("squeegee", "Squeegee Glass"), ("shampoo", "Shampoo Carpet"), ("steam", "Steam Clean"),
             ("scrub", "Scrub"), ("polish", "Polish"), ("strip", "Strip & Wax"), ("wax", "Strip & Wax"),
             ("pick up", "Debris Pick Up"), ("debris", "Debris Pick Up"), ("sweep", "Sweep"),
             ("vacuum", "Vacuum"), ("mop", "Mop"), ("wipe", "Wipe Down"), ("sanitize", "Sanitize")]


def infer_area(loc):
    low = str(loc).lower()
    for kw, at in EXTRA_AREA:
        if kw in low:
            return at, f"location name contains '{kw}'", "High"
    if any(s in low for s in SURFACE_TOKENS) or low.strip("() ") in ("", "back", "front", "various"):
        return None, "surface/feature or building-wide reference — no discrete area", "Low"
    return None, "location name has no recognizable area keyword", "Low"


def infer_task(row, siblings):
    """siblings = rows sharing this row's source_text.

    HIGH only when the row's OWN source_text states a full general-cleaning scope
    (which genuinely applies to every area in that bundle). Sibling-derived tasks
    are downgraded to Medium: a block can list location-specific tasks (e.g. a
    'Clean Barbeque' row alongside a 'Dog Run' row), so they cannot be auto-assigned.
    """
    src = (row["source_text"] + " " + row["task"]).lower()
    if "empty trash" in src or ("dust" in src and "disinfect" in src):
        return "Empty trash, replenish supplies, clean, dust, disinfect etc.", \
               "source_text describes general cleaning (applies to whole bundle)", "High"
    explicit = [r["task"] for r in siblings
                if r["task"] and "no explicit" not in r["task"].lower()]
    if explicit:
        uniq = set(explicit)
        note = ("sibling rows specify a single task" if len(uniq) == 1
                else "shared block has mixed tasks — dominant shown")
        return Counter(explicit).most_common(1)[0][0], note + " — needs review", "Medium"
    for kw, label in GEN_VERBS:
        if kw in src:
            return label, f"source_text contains action '{kw}'", "Medium"
    return None, "no task verb in source_text or sibling rows", "Low"


def cadence_from_text(text):
    t = text.lower()
    if re.search(r"\b(bi-?weekly|twice a week|2x|two times)\b", t):
        return "2x/week"
    if re.search(r"every (mon|tue|wed|thu|fri|sat|sun)", t) or "every friday" in t:
        return "Weekly"
    for w, val in (("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"),
                   ("seasonal", "Seasonal")):
        if re.search(rf"\b{w}\b", t):
            return val
    if re.search(r"\bas (needed|required|requested)\b", t):
        return "As needed"
    return None


def infer_freq(row, loc_rows, locTask_rows):
    txt = row["notes"] + " " + row["source_text"]
    cad = cadence_from_text(txt)
    if cad:
        return cad, f"notes/source_text state cadence ('{cad}')", "High"
    defined = lambda rs: [r["frequency"] for r in rs if r["frequency"] and r["frequency"].lower() != "unknown"]
    dt = set(defined(locTask_rows))
    if len(dt) == 1:
        v = next(iter(dt))
        return v, f"same location + task scheduled '{v}' elsewhere", "High"
    dl = set(defined(loc_rows))
    if len(dl) == 1:
        v = next(iter(dl))
        return v, f"same location scheduled '{v}' elsewhere (different task)", "Medium"
    return None, "no cadence stated and no consistent frequency for this location", "Low"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SCHEDULE_DIR, "*.csv")))
    log, manual = [], []
    before = Counter(); after = Counter()

    for path in files:
        fname = os.path.basename(path)
        prop = fname.replace("_cleaning_responsibilities.csv", "")
        rows = []
        for i, r in enumerate(csv.DictReader(open(path, newline="", encoding="utf-8-sig"))):
            rows.append({k: (v or "").strip() for k, v in r.items()} | {"_i": i})
        by_src = defaultdict(list)
        by_loc = defaultdict(list)
        by_loctask = defaultdict(list)
        for r in rows:
            by_src[r["source_text"]].append(r)
            by_loc[r["location"]].append(r)
            by_loctask[(r["location"], r["task"])].append(r)

        for r in rows:
            # --- Area ---
            if classify(r["location"]) == "Unknown":
                before["area"] += 1
                val, reason, conf = infer_area(r["location"])
                if val and conf == "High":
                    after_fill = True
                else:
                    after["area"] += 1; after_fill = False
                    manual.append([prop, "Area Type", r["location"], "Unknown",
                                   val or "—", reason, conf])
                log.append([prop, r["_i"], "Area Type", r["location"], "Unknown",
                            val or "", reason, conf, "yes" if (val and conf == "High") else "no"])
            # --- Task ---
            if "no explicit" in r["task"].lower():
                before["task"] += 1
                val, reason, conf = infer_task(r, by_src[r["source_text"]])
                if val and conf == "High":
                    pass
                else:
                    after["task"] += 1
                    manual.append([prop, "Task", r["location"], r["task"],
                                   val or "—", reason, conf])
                log.append([prop, r["_i"], "Task", r["location"], r["task"],
                            val or "", reason, conf, "yes" if (val and conf == "High") else "no"])
            # --- Frequency ---
            if r["frequency"].lower() == "unknown":
                before["freq"] += 1
                val, reason, conf = infer_freq(r, by_loc[r["location"]],
                                               by_loctask[(r["location"], r["task"])])
                if val and conf == "High":
                    pass
                else:
                    after["freq"] += 1
                    manual.append([prop, "Frequency", r["location"], "Unknown",
                                   val or "—", reason, conf])
                log.append([prop, r["_i"], "Frequency", r["location"], "Unknown",
                            val or "", reason, conf, "yes" if (val and conf == "High") else "no"])

    pd.DataFrame(log, columns=["property", "row", "field", "location", "original",
                               "inferred", "reason", "confidence", "auto_filled"]).to_csv(
        os.path.join(OUT_DIR, "inference_log.csv"), index=False)
    pd.DataFrame(manual, columns=["property", "field", "location", "original",
                                  "best_guess", "reason", "confidence"]).to_csv(
        os.path.join(OUT_DIR, "manual_review.csv"), index=False)

    def line(name, key):
        b, a = before[key], after[key]
        return f"  {name:22} {b:4}  ->  {a:4}   ({b - a} auto-filled, high confidence)"

    print("DATA-QUALITY AUDIT — Before / After (high-confidence auto-fill)\n")
    print("BEFORE -> AFTER (still Unknown):")
    print(line("Unknown Area Types", "area"))
    print(line("No Explicit Task", "task"))
    print(line("Unknown Frequencies", "freq"))
    hi = sum(1 for r in log if r[8] == "yes")
    print(f"\ntotal high-confidence auto-fills: {hi}")
    print(f"records still needing manual review: {len(manual)}")
    print(f"\nlogs written to {os.path.relpath(OUT_DIR, REPO)}/")
    print("manual_review reasons (top):")
    for (field, reason), n in Counter((m[1], m[5]) for m in manual).most_common(8):
        print(f"  {n:4}  [{field}] {reason}")


if __name__ == "__main__":
    main()
