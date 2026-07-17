#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
export_h1h2.py — tiszta h1_export.csv + h2_export.csv a H1 konfirmatorikus teszthez.
- Bíráló-forrás: evaluations/llm_eval_runs_*.csv (a keresztbírálói fájlok
  karanténban, de biztonsági övként a 20260711_163447 mintát így is kizárjuk).
- Objektív forrás: EXPLICIT fájl (nem glob).
- Szűrés: evalStatus==ok, repeatIndex==0, pipeline==full, mode in {vector,graph,hybrid}.
- Join: szigorú 6-kulcs (reqId,testId,mode,pipeline,model,repeatIndex), 1:1 ellenőrzéssel.
- h2_export: CSAK objektív oszlopok (coverage_score, support_score, objective_score)
  — bírálói pontszám nem kerül bele.
Futtatás:  python export_h1h2.py
"""
import csv, glob, sys, collections

JUDGE_GLOB = "evaluations/llm_eval_runs_*.csv"
OBJ_FILE = "evaluations/objective_evaluation_details_runs_.csv_20260709_183209.csv"
QUARANTINE_MARK = "20260711_163447"
KEY6 = ("reqId", "testId", "mode", "pipeline", "model", "repeatIndex")
DIMS = ("requirement_alignment", "target_specificity", "evidence_grounding",
        "executability", "gherkin_quality", "coverage")
OBJ_COLS = ("coverage_score", "support_score", "objective_score")


def load_judge():
    rows = []
    files = sorted(glob.glob(JUDGE_GLOB))
    used = []
    for f in files:
        if QUARANTINE_MARK in f or "summary" in f.lower():
            print(f"KIHAGYVA (biztonsagi ov): {f}")
            continue
        used.append(f)
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("evalStatus") == "ok" and r.get("repeatIndex") == "0"
                        and r.get("pipeline") == "full"
                        and r.get("mode") in ("vector", "graph", "hybrid")):
                    rows.append(r)
    print("Biralo-fajlok:", *used, sep="\n  ")
    return rows


def key(r):
    return tuple(str(r.get(k, "")) for k in KEY6)


def main():
    judge = load_judge()
    print(f"Biraloi sorok a szures utan: {len(judge)} (vart ~3846)")
    dup = [k for k, c in collections.Counter(map(key, judge)).items() if c > 1]
    if dup:
        sys.exit(f"HIBA: {len(dup)} duplikalt 6-kulcs a biraloi sorokban, pl. {dup[:3]}")

    try:
        with open(OBJ_FILE, encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            obj_cols = rd.fieldnames or []
            missing = [c for c in KEY6 + OBJ_COLS if c not in obj_cols]
            if missing:
                sys.exit(f"HIBA: az objektiv CSV-bol hianyzo oszlopok: {missing}\n"
                         f"Tenyleges oszlopok: {obj_cols}")
            obj = {}
            for r in rd:
                if (r.get("repeatIndex") == "0" and r.get("pipeline") == "full"
                        and r.get("mode") in ("vector", "graph", "hybrid")):
                    k = key(r)
                    if k in obj:
                        sys.exit(f"HIBA: duplikalt 6-kulcs az objektiv CSV-ben: {k}")
                    obj[k] = r
    except FileNotFoundError:
        sys.exit(f"HIBA: nem talalom: {OBJ_FILE} — igazitsd az OBJ_FILE utvonalat.")

    unmatched = [k for k in map(key, judge) if k not in obj]
    if unmatched:
        sys.exit(f"HIBA: {len(unmatched)} biraloi sornak nincs objektiv parja, "
                 f"pl. {unmatched[:3]}")

    with open("h1_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reqId", "testId", "mode", "model"] + list(DIMS))
        for r in judge:
            w.writerow([r["reqId"], r["testId"], r["mode"], r["model"]]
                       + [r.get(d, "") for d in DIMS])
    with open("h2_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reqId", "testId", "mode", "model"] + list(OBJ_COLS))
        for r in judge:
            o = obj[key(r)]
            w.writerow([r["reqId"], r["testId"], r["mode"], r["model"]]
                       + [o.get(c, "") for c in OBJ_COLS])
    print(f"Kiirva: h1_export.csv ({len(judge)} sor), h2_export.csv ({len(judge)} sor)")
    print("Join: 1:1, unmatched=0. h2_export CSAK objektiv oszlopokat tartalmaz.")


if __name__ == "__main__":
    main()
