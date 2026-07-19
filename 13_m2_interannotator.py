#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
13_m2_interannotator.py — M2: masodik annotator minta + Cohen-kappa.

HAROM RESZ (mindharom kappa-kepes, mert van valtozatossag):
  A) REFERENCE: megtartott (622) + torolt (draft 642 - 622 = torolt) pontok
     keverve -> az annotator VALID/NOISE itelete vs a te dontesed (kept/removed).
  B) TYPED ELEMENTS: az annotator maga sorolja tipusba az elemeket
     (local/conflict/cross_module/supersede/refine/gap) -> vs a tarolt tipusok.
  C) M1 RESZMINTA: 30 sor a kitoltott matcher-validacios mintadbol, a te
     iteleteid NELKUL -> TRUE_MISS/PARAPHRASE/PARTIAL vs a te iteleteid.

1) EXPORT (a te gepeden, projektmappaból):
   python 13_m2_interannotator.py --export ^
     --reference evaluations/reference.json ^
     --reference-draft evaluations/reference_draft_20260707_183716.json ^
     --typed typed_elements.json ^
     --m1-filled analysis/matcher_validation_sample_kitoltott.csv ^
     --out-dir m2_annotation
   -> m2_annotation/A_reference.csv, B_typed.csv, C_m1.csv (annotatornak)
   -> m2_annotation/_answer_key.json (NE add oda! a kappa-hoz kell)

2) Az annotator kitolti a harom CSV verdict oszlopat (instrukcio kulon lapon).

3) KAPPA:
   python 13_m2_interannotator.py --kappa --out-dir m2_annotation
"""
import argparse, csv, json, random, sys, collections, unicodedata
from pathlib import Path

SEED = 20260713
TYPES = ["local", "conflict", "cross_module", "supersede", "refine", "gap"]

def norm(s): return " ".join(unicodedata.normalize("NFC", s).split())

def cohen_kappa(pairs):
    n = len(pairs)
    if not n: return float("nan"), 0.0
    agree = sum(1 for a, b in pairs if a == b) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    k = (agree - pe) / (1 - pe) if pe < 1 else float("nan")
    return k, agree

def do_export(args):
    rnd = random.Random(SEED)
    out = Path(args.out_dir); out.mkdir(exist_ok=True)
    key = {}

    # --- A) reference: kept vs removed ---
    ref = json.load(open(args.reference, encoding="utf-8"))
    draft = json.load(open(args.reference_draft, encoding="utf-8"))
    kept, removed = [], []
    for req, prof in draft.items():
        final_pts = {norm(p) for p in ref.get(req, {}).get("canonical_points", [])}
        for p in prof.get("canonical_points", []):
            (kept if norm(p) in final_pts else removed).append((req, norm(p)))
    a_kept = rnd.sample(kept, min(45, len(kept)))
    a_rem = removed if len(removed) <= 20 else rnd.sample(removed, 20)
    items = a_kept + a_rem
    rnd.shuffle(items)
    with open(out / "A_reference.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item_id", "reqId", "point_text", "verdict_VALID_or_NOISE"])
        for i, (req, p) in enumerate(items, 1):
            w.writerow([i, req, p, ""])
    key["A"] = {str(i): ("VALID" if (req, p) in a_kept else "NOISE")
                for i, (req, p) in enumerate(items, 1)}
    print(f"A_reference.csv: {len(items)} sor ({len(a_kept)} kept + {len(a_rem)} removed, kevert)")

    # --- B) typed: tipus-hozzarendeles ---
    typed = json.load(open(args.typed, encoding="utf-8"))
    els = [(req, e["text"], e["element_type"]) for req, v in typed.items() for e in v["elements"]]
    b_sample = rnd.sample(els, min(40, len(els)))
    with open(out / "B_typed.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item_id", "reqId", "element_text",
                    "verdict_type(" + "/".join(TYPES) + ")"])
        for i, (req, txt, _t) in enumerate(b_sample, 1):
            w.writerow([i, req, txt, ""])
    key["B"] = {str(i): t for i, (_r, _x, t) in enumerate(b_sample, 1)}
    print(f"B_typed.csv: {len(b_sample)} sor")

    # --- C) M1 reszminta ---
    with open(args.m1_filled, encoding="utf-8-sig") as f:
        sniff = f.read(2048); f.seek(0)
        delim = ";" if sniff.count(";") > sniff.count(",") else ","
        rows = [r for r in csv.DictReader(f, delimiter=delim) if r.get("human_verdict", "").strip()]
    c_sample = rnd.sample(rows, min(30, len(rows)))
    with open(out / "C_m1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["item_id", "reqId", "element_text", "gherkin_test",
                    "verdict_TRUE_MISS_PARAPHRASE_PARTIAL"])
        for i, r in enumerate(c_sample, 1):
            w.writerow([i, r["reqId"], r["element_text"], r["gherkin_test"], ""])
    key["C"] = {str(i): r["human_verdict"].strip().upper() for i, r in enumerate(c_sample, 1)}
    print(f"C_m1.csv: {len(c_sample)} sor")

    with open(out / "_answer_key.json", "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=1)
    print(f"\nKesz: {out}/ — az A/B/C CSV-ket add at, az _answer_key.json NALAD marad.")

def read_filled(path, verdict_col_idx=-1):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))
    hdr, body = rows[0], rows[1:]
    return {r[0]: r[verdict_col_idx].strip().upper() for r in body if r and r[verdict_col_idx].strip()}

def do_kappa(args):
    out = Path(args.out_dir)
    key = json.load(open(out / "_answer_key.json", encoding="utf-8"))
    norm_map = {"PARA": "PARAPHRASE", "TM": "TRUE_MISS", "PART": "PARTIAL"}
    for part, fname, label in [("A", "A_reference.csv", "reference VALID/NOISE"),
                               ("B", "B_typed.csv", "typed element_type"),
                               ("C", "C_m1.csv", "M1 TRUE_MISS/PARA/PARTIAL")]:
        try:
            got = read_filled(out / fname)
        except FileNotFoundError:
            print(f"{part}: {fname} nem talalhato — kihagyva"); continue
        pairs = []
        missing = 0
        for item_id, truth in key[part].items():
            v = got.get(item_id, "")
            v = norm_map.get(v, v)
            if not v: missing += 1; continue
            pairs.append((truth, v))
        k, agree = cohen_kappa(pairs)
        print(f"{part} ({label}): n={len(pairs)} (ures: {missing})  egyezes={agree*100:.1f}%  Cohen-kappa={k:.3f}")
        conf = collections.Counter(pairs)
        for (t, v), c in sorted(conf.items()):
            if t != v: print(f"    elteres: te={t} <> annotator={v}  x{c}")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true")
    g.add_argument("--kappa", action="store_true")
    ap.add_argument("--reference"); ap.add_argument("--reference-draft")
    ap.add_argument("--typed", default="typed_elements.json")
    ap.add_argument("--m1-filled")
    ap.add_argument("--out-dir", default="m2_annotation")
    args = ap.parse_args()
    if args.export and not (args.reference and args.reference_draft and args.m1_filled):
        ap.error("--export: --reference, --reference-draft es --m1-filled kotelezo")
    (do_export if args.export else do_kappa)(args)

if __name__ == "__main__":
    main()
