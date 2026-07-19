#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_matcher_validation.py — M1: az integration-miss matcher-ítéletek human validálása.

Három lépés:

1) MINTA EXPORT (~100 véletlen integration-miss, seed-elt):
   python 12_matcher_validation.py --export --judge-input "evaluations/llm_eval_runs_*.csv" ^
       --typed-elements typed_elements.json --n 100 --seed 20260712 ^
       --out analysis/matcher_validation_sample.csv

2) KÉZI ÍTÉLET: az exportált CSV-t Excelben/VS Code-ban megnyitod, és a
   human_verdict oszlopba soronként beírod:
     TRUE_MISS  — az elem tartalma tényleg NINCS a tesztben (sem átfogalmazva)
     PARAPHRASE — az elem tartalma BENNE VAN a tesztben, csak más szavakkal
                  (a matcher tévedett)
     PARTIAL    — részben fedett (az elem egyik fele igen, másik nem)
   A notes oszlopba rövid indoklás mehet (opcionális, de ajánlott).
   Csak a human_verdict oszlopot szerkeszd!

3) ÖSSZESÍTÉS:
   python 12_matcher_validation.py --summarize --in analysis/matcher_validation_sample.csv

Plusz: KÜSZÖB-ÉRZÉKENYSÉG (nem kell hozzá kézi munka):
   python 12_matcher_validation.py --threshold-curve --judge-input "evaluations/llm_eval_runs_*.csv" ^
       --typed-elements typed_elements.json
"""
import argparse, csv, glob, json, random, sys, collections

def load_core():
    try:
        import exp_core as E
    except ImportError:
        sys.exit("exp_core.py nem importalhato — a projektmappabol futtasd.")
    tok = E.obj_tokenize
    stem = getattr(E, "obj_stemish", lambda t: t)
    return lambda text: {stem(t) for t in tok(text or "")}

def load_rows(pattern):
    rows = []
    for f in glob.glob(pattern):
        with open(f, encoding="utf-8") as fh:
            rows += [r for r in csv.DictReader(fh)
                     if r.get("evalStatus") == "ok" and r.get("repeatIndex") == "0"
                     and r.get("pipeline") not in ("no_retrieval",)]
    return rows

def load_gt(path):
    d = json.load(open(path, encoding="utf-8"))
    return {k: v.get("elements") or v.get("canonical_points_typed") or [] for k, v in d.items()}

def iter_misses(rows, gt, term_set, thr):
    """Yield (row, element, kind) where kind in {'integration','retrieval'}."""
    for r in rows:
        elements = gt.get(r.get("reqId", ""), [])
        ev = term_set(r.get("evidenceText", ""))
        gh = term_set(r.get("gherkin", ""))
        for el in elements:
            terms = term_set(el.get("text", ""))
            if not terms:
                continue
            covered = len(terms & gh) / len(terms) >= thr
            if covered:
                continue
            present = len(terms & ev) / len(terms) >= thr
            yield r, el, ("integration" if present else "retrieval")

def do_export(args):
    term_set = load_core()
    rows = load_rows(args.judge_input)
    gt = load_gt(args.typed_elements)
    misses = [(r, el) for r, el, kind in iter_misses(rows, gt, term_set, args.thr)
              if kind == "integration"]
    print(f"osszes integration-miss (sor x elem) par: {len(misses)}")
    rnd = random.Random(args.seed)
    sample = rnd.sample(misses, min(args.n, len(misses)))
    cols = ["sample_id", "reqId", "model", "mode", "testId", "element_type",
            "element_text", "gherkin_test", "matcher_verdict", "human_verdict", "notes"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, (r, el) in enumerate(sample, 1):
            w.writerow({
                "sample_id": i, "reqId": r.get("reqId"), "model": r.get("model"),
                "mode": r.get("mode"), "testId": r.get("testId"),
                "element_type": el.get("element_type", "local"),
                "element_text": el.get("text", ""),
                "gherkin_test": r.get("gherkin", ""),
                "matcher_verdict": "integration_miss",
                "human_verdict": "", "notes": "",
            })
    comp = collections.Counter((el.get("element_type","local")) for _, el in sample)
    print(f"minta: {len(sample)} sor -> {args.out} (seed={args.seed})")
    print("tipus-osszetetel:", dict(comp))
    print("Kovetkezo lepes: toltsd ki a human_verdict oszlopot (TRUE_MISS/PARAPHRASE/PARTIAL).")

def do_summarize(args):
    rows = list(csv.DictReader(open(args.infile, encoding="utf-8")))
    verdicts = collections.Counter(r["human_verdict"].strip().upper() for r in rows)
    empty = verdicts.pop("", 0)
    n = sum(verdicts.values())
    if empty:
        print(f"FIGYELEM: {empty} sor meg nincs kitoltve.")
    if not n:
        sys.exit("Nincs kitoltott itelet.")
    print(f"kitoltott iteletek: {n}")
    for k, v in verdicts.most_common():
        print(f"  {k:<12} {v:>4}  ({v/n*100:.1f}%)")
    tm = verdicts.get("TRUE_MISS", 0); pa = verdicts.get("PARAPHRASE", 0); pt = verdicts.get("PARTIAL", 0)
    lo = tm / n
    hi = (tm + pt) / n
    print(f"\nValodi-miss arany (konzervativ, PARTIAL nelkul): {lo*100:.1f}%")
    print(f"Valodi-miss arany (PARTIAL-t missnek szamolva):  {hi*100:.1f}%")
    print("Cikkbe: 'human validation of N sampled integration misses: X% true misses'")
    # tipusonkent
    by_type = collections.defaultdict(collections.Counter)
    for r in rows:
        v = r["human_verdict"].strip().upper()
        if v:
            by_type[r["element_type"]][v] += 1
    print("\ntipusonkent:")
    for t, c in sorted(by_type.items()):
        tot = sum(c.values())
        print(f"  {t:<14} n={tot:<4} TRUE_MISS={c.get('TRUE_MISS',0)/tot*100:.0f}%")

def do_curve(args):
    term_set = load_core()
    rows = load_rows(args.judge_input)
    gt = load_gt(args.typed_elements)
    print(f"{'kuszob':>7}{'retr_miss':>11}{'integ_miss':>12}{'total':>8}{'integ%':>8}")
    for thr in (0.3, 0.4, 0.5, 0.6, 0.7):
        rm = im = tot_el = 0
        for r in rows:
            elements = gt.get(r.get("reqId", ""), [])
            ev = term_set(r.get("evidenceText", ""))
            gh = term_set(r.get("gherkin", ""))
            for el in elements:
                terms = term_set(el.get("text", ""))
                if not terms:
                    continue
                tot_el += 1
                if len(terms & gh) / len(terms) >= thr:
                    continue
                if len(terms & ev) / len(terms) >= thr:
                    im += 1
                else:
                    rm += 1
        miss = rm + im
        print(f"{thr:>7.1f}{rm/tot_el*100:>10.1f}%{im/tot_el*100:>11.1f}%{miss/tot_el*100:>7.1f}%{(im/miss*100 if miss else 0):>7.1f}%")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true")
    g.add_argument("--summarize", action="store_true")
    g.add_argument("--threshold-curve", action="store_true")
    ap.add_argument("--judge-input")
    ap.add_argument("--typed-elements", default="typed_elements.json")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260712)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--out", default="analysis/matcher_validation_sample.csv")
    ap.add_argument("--in", dest="infile", default="analysis/matcher_validation_sample.csv")
    args = ap.parse_args()
    if (args.export or args.threshold_curve) and not args.judge_input:
        ap.error("--judge-input kotelezo ehhez a lepeshez")
    if args.export: do_export(args)
    elif args.summarize: do_summarize(args)
    else: do_curve(args)

if __name__ == "__main__":
    main()
