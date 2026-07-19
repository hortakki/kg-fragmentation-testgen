#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
14_conflict_supersede_misses.py — M3/T5: a conflict/supersede tipusu integration-miss-ek
integracios-hiba tipusanak human validalasa.

Mit validal: azoknal az elemeknel, amelyek tipusa 'conflict' vagy 'supersede' ES a generalt
tesztben nincsenek fedve (gherkin-coverage < thr), a human eldonti, MILYEN integracios hiba ez:

  UNREFLECTED               — a konfliktus/feluliras egyaltalan nincs tukrozve a tesztben
  WRONG_DIRECTION_RESOLUTION — feloldva, de ROSSZ iranyba (a felulirt/regi allapot szerint,
                              vagy a konfliktus rossz agat valasztva)
  SUBTHRESHOLD_PARAPHRASE   — valojaban BENNE VAN atfogalmazva, csak a matcher kuszob alatt maradt
                              (a matcher tul szigoru volt)

Mintaegyseg: (tesztsor, elem) — itt a verdict a KONKRET gherkinrol szol (irany, paraphrase),
ezert tesztsor-szinten mintazunk, NEM cella-szinten (ellentetben a 13-assal).

Supersede ritka (~6% a parok kozott), ezert arányos 60-as huzasbol csak ~3-4 supersede jonne.
A --min-supersede N opcio garantalt supersede-lefedest ad (default 0 = tisztan aranyos, a
regisztralt spec szerint; ha hasznalod, a deviations-tablaban dokumentald a stratifikalast).

Harom lepes (a 12_matcher_validation.py mintajara):

1) EXPORT:
   python 14_conflict_supersede_misses.py --export \
       --judge-input "evaluations/llm_eval_runs_*.csv" \
       --typed-elements typed_elements.json --n 60 --seed 20260715 \
       --out analysis/conflict_supersede_sample.csv
   # garantalt supersede-lefedessel:  --min-supersede 15

2) KEZI ITELET: human_verdict = UNREFLECTED / WRONG_DIRECTION_RESOLUTION / SUBTHRESHOLD_PARAPHRASE.
   Csak a human_verdict (es opcionalisan notes) oszlopot szerkeszd!
   Ha window_is_fallback=True, az ablak NEM anchor-alapu (az evidence eleje) — dontes elott
   nezd meg a teljes evidencet a nyers CSV-ben!

3) OSSZESITES:
   python 14_conflict_supersede_misses.py --summarize --in analysis/conflict_supersede_sample.csv

Seed: a 20260715 UJ seed — regisztrald a deviations-tablaban.

[VERIFY] Az overlap-formula itt: |elem_termek ∩ gherkin_termek| / |elem_termek| < thr (0.5) a
miss-definiciohoz, exp_core.obj_tokenize + obj_stemish termekkel. Futtatas elott vesd ossze a
12-es / exp_core-beli matcher formulaval.
"""
import argparse, csv, glob, json, random, sys, collections, re

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))  # hybrid evidence tail > 128k default limit

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_\-']{3,}")
TARGET_TYPES = ("conflict", "supersede")
VALID_VERDICTS = {"UNREFLECTED", "WRONG_DIRECTION_RESOLUTION", "SUBTHRESHOLD_PARAPHRASE"}

def load_core():
    try:
        import exp_core as E
    except ImportError:
        sys.exit("exp_core.py nem importalhato — a projektmappabol futtasd.")
    tok = E.obj_tokenize
    stem = getattr(E, "obj_stemish", lambda t: t)
    term_set = lambda text: {stem(t) for t in tok(text or "")}
    return tok, stem, term_set

def row_mode(r):
    # a mod oszlop neve fajlonkent lehet 'mode' vagy 'pipeline' — mindkettot kezeljuk
    return r.get("mode") or r.get("pipeline") or ""

def load_rows(pattern):
    files = sorted(glob.glob(pattern))  # determinisztikus sorrend a seed-reprodukalhatosaghoz
    if not files:
        sys.exit(f"Nincs talalat a mintara: {pattern}")
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            rows += [r for r in csv.DictReader(fh)
                     if r.get("evalStatus") == "ok" and r.get("repeatIndex") == "0"
                     and row_mode(r) != "no_retrieval"]
    return rows

def load_gt(path):
    d = json.load(open(path, encoding="utf-8"))
    gt = {k: v.get("elements") or v.get("canonical_points_typed") or [] for k, v in d.items()}
    if not any(gt.values()):
        sys.exit("typed_elements.json: egyetlen elem sem talalhato ('elements' / "
                 "'canonical_points_typed' kulcs alatt kerestem) — ellenorizd a strukturat.")
    return gt

def anchor_window(evidence, elem_stems, stem, radius=500):
    """Return (window_text, full_evidence_flag, distinct_elem_stems_in_window, is_fallback)."""
    ev = evidence or ""
    low = ev.lower()
    pos_stem = [(m.start(), stem(m.group())) for m in TOKEN_RE.finditer(low)
                if stem(m.group()) in elem_stems]
    if not pos_stem:
        return ev[:2 * radius], (len(ev) <= 2 * radius), 0, True
    best_center, best_cov = pos_stem[0][0], -1
    for c, _ in pos_stem:
        stems = {s for p, s in pos_stem if c - radius <= p <= c + radius}
        if len(stems) > best_cov:
            best_cov, best_center = len(stems), c
    lo = max(0, best_center - radius); hi = min(len(ev), best_center + radius)
    return ev[lo:hi], (len(ev) <= 2 * radius), best_cov, False

def iter_cs_misses(rows, gt, term_set, thr):
    """Yield (row, element) for conflict/supersede elements not covered in gherkin (<thr)."""
    for r in rows:
        elements = gt.get(r.get("reqId", ""), [])
        gh = term_set(r.get("gherkin", ""))
        for el in elements:
            if el.get("element_type") not in TARGET_TYPES:
                continue
            terms = term_set(el.get("text", ""))
            if not terms:
                continue
            if len(terms & gh) / len(terms) < thr:      # not covered -> a miss
                yield r, el

def sort_key(pair):
    r, el = pair
    return (r.get("reqId") or "", row_mode(r), r.get("model") or "",
            r.get("testId") or "", el.get("text") or "")

def do_export(args):
    tok, stem, term_set = load_core()
    rows = load_rows(args.judge_input)
    gt = load_gt(args.typed_elements)
    pairs = sorted(iter_cs_misses(rows, gt, term_set, args.thr), key=sort_key)
    comp_all = collections.Counter(el.get("element_type") for _, el in pairs)
    print(f"conflict/supersede miss-parok osszesen: {len(pairs)}  {dict(comp_all)}")
    n_sup = comp_all.get("supersede", 0)
    exp_sup = round(args.n * n_sup / len(pairs)) if pairs else 0
    if args.min_supersede == 0 and exp_sup < 5:
        print(f"FIGYELEM: aranyos huzasbol varhatoan csak ~{exp_sup} supersede kerul a mintaba — "
              f"fontold meg a --min-supersede opciot (dokumentald a deviations-tablaban).")
    rnd = random.Random(args.seed)
    if args.min_supersede > 0:
        sup = [p for p in pairs if p[1].get("element_type") == "supersede"]
        take_sup = min(args.min_supersede, len(sup))
        if take_sup < args.min_supersede:
            print(f"FIGYELEM: csak {take_sup} supersede par elerheto (< {args.min_supersede}).")
        chosen_sup = rnd.sample(sup, take_sup)
        chosen_ids = {id(p) for p in chosen_sup}
        pool = [p for p in pairs if id(p) not in chosen_ids]
        rest = rnd.sample(pool, min(max(args.n - take_sup, 0), len(pool)))
        sample = chosen_sup + rest
        print(f"stratifikalt huzas: {take_sup} supersede garantalva + {len(rest)} aranyos.")
    else:
        sample = rnd.sample(pairs, min(args.n, len(pairs)))
    rnd.shuffle(sample)
    cols = ["sample_id", "reqId", "model", "mode", "testId", "element_type",
            "element_text", "evidence_window", "full_evidence", "window_is_fallback",
            "anchor_terms_in_window", "gherkin_test",
            "matcher_verdict", "human_verdict", "notes"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for i, (r, el) in enumerate(sample, 1):
            win, full, cov, fb = anchor_window(r.get("evidenceText", ""),
                                               term_set(el.get("text", "")), stem, args.radius)
            w.writerow({
                "sample_id": i, "reqId": r.get("reqId"), "model": r.get("model"),
                "mode": row_mode(r), "testId": r.get("testId"),
                "element_type": el.get("element_type"),
                "element_text": el.get("text", ""),
                "evidence_window": win, "full_evidence": full,
                "window_is_fallback": fb, "anchor_terms_in_window": cov,
                "gherkin_test": r.get("gherkin", ""),
                "matcher_verdict": "integration_miss",
                "human_verdict": "", "notes": "",
            })
    comp = collections.Counter(el.get("element_type") for _, el in sample)
    print(f"minta: {len(sample)} sor -> {args.out} (seed={args.seed})")
    print("tipus-osszetetel:", dict(comp))
    print("Kovetkezo lepes: human_verdict = UNREFLECTED / WRONG_DIRECTION_RESOLUTION / "
          "SUBTHRESHOLD_PARAPHRASE")

def do_summarize(args):
    rows = list(csv.DictReader(open(args.infile, encoding="utf-8")))
    verdicts = collections.Counter(r["human_verdict"].strip().upper() for r in rows)
    empty = verdicts.pop("", 0)
    unknown = {k: v for k, v in verdicts.items() if k not in VALID_VERDICTS}
    if unknown:
        sys.exit(f"HIBA: ismeretlen verdict-cimke(k) a fajlban: {unknown} — "
                 f"javitsd elgepeles lehet ({sorted(VALID_VERDICTS)}).")
    n = sum(verdicts.values())
    if empty:
        print(f"FIGYELEM: {empty} sor meg nincs kitoltve.")
    if not n:
        sys.exit("Nincs kitoltott itelet.")
    print(f"kitoltott iteletek: {n}")
    for k, v in verdicts.most_common():
        print(f"  {k:<26} {v:>4}  ({v/n*100:.1f}%)")
    sp = verdicts.get("SUBTHRESHOLD_PARAPHRASE", 0)
    true_integ = n - sp
    print(f"\nvalodi integracios hiba (nem paraphrase-artefakt): {true_integ/n*100:.1f}%")
    print(f"  ebbol UNREFLECTED:                {verdicts.get('UNREFLECTED',0)/n*100:.1f}%")
    print(f"  ebbol WRONG_DIRECTION_RESOLUTION: {verdicts.get('WRONG_DIRECTION_RESOLUTION',0)/n*100:.1f}%")
    print(f"matcher-artefakt (SUBTHRESHOLD_PARAPHRASE): {sp/n*100:.1f}%")
    by_type = collections.defaultdict(collections.Counter)
    for r in rows:
        v = r["human_verdict"].strip().upper()
        if v:
            by_type[r["element_type"]][v] += 1
    print("\ntipusonkent:")
    for t, c in sorted(by_type.items()):
        tot = sum(c.values())
        print(f"  {t:<12} n={tot:<4} UNREFLECTED={c.get('UNREFLECTED',0)/tot*100:.0f}%  "
              f"WRONG_DIR={c.get('WRONG_DIRECTION_RESOLUTION',0)/tot*100:.0f}%  "
              f"PARAPHRASE={c.get('SUBTHRESHOLD_PARAPHRASE',0)/tot*100:.0f}%")
    fb = sum(1 for r in rows if r.get("window_is_fallback", "").strip() in ("True", "true", "1"))
    if fb:
        print(f"\nMEGJ.: {fb} sor ablaka fallback (nem anchor-alapu) volt.")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true")
    g.add_argument("--summarize", action="store_true")
    ap.add_argument("--judge-input")
    ap.add_argument("--typed-elements", default="typed_elements.json")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--min-supersede", type=int, default=0,
                    help="garantalt supersede-darabszam a mintaban (0 = tisztan aranyos)")
    ap.add_argument("--seed", type=int, default=20260715)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--radius", type=int, default=500)
    ap.add_argument("--out", default="analysis/conflict_supersede_sample.csv")
    ap.add_argument("--in", dest="infile", default="analysis/conflict_supersede_sample.csv")
    args = ap.parse_args()
    if args.export and not args.judge_input:
        ap.error("--judge-input kotelezo az exporthoz")
    if args.export: do_export(args)
    else: do_summarize(args)

if __name__ == "__main__":
    main()
