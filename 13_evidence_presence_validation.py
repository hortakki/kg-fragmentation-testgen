#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
13_evidence_presence_validation.py — M3/T5: az integration-miss "present in evidence" lab
human validalasa.

Mit validal: a matcher azt allitja, hogy egy hianyzo (gherkinben nem fedett) elem TARTALMA
BENNE VAN az evidenceText-ben (ezert 'integration_miss' es nem 'retrieval_miss'). Ez a script
~90 ilyen esetet mintaz, MODONKENT stratifikalva (30/30/30 — mert a kontextusmeret modonkent
~5x kulonbozik), es minden sorhoz kiexportalja az elem szoveget + az evidence ABLAKOT a legjobb
anchor korul (+-500 kar) + a full_evidence flaget. A human eldonti:

  PRESENT_USABLE       — az elem tartalma ott van az evidenceben, egyben, hasznalhatoan
  PRESENT_SCATTERED    — ott van, de szetszorva (tobb helyen, nehezen integralhato)
  PRESENT_CONTRADICTED — ott van, de mas resz ellentmond neki (feloldando konfliktus)
  ABSENT               — valojaban NINCS ott (a matcher tevedett -> ez retrieval-miss volna)

FONTOS — mintaegyseg: (reqId, mode, model, element), NEM tesztsor. Az evidence cellankent
konstans (T4-ben verifikalva), es a verdict csak az (elem, evidence) partol fugg, ezert a
tesztsoronkenti mintavetel duplikatumokat adna. Az n_test_occurrences oszlop mutatja, hany
tesztsort erint az adott (cella, elem) par; a gherkin_test csak kontextus (a legkisebb testId-ju
sor tesztje).

Harom lepes (a 12_matcher_validation.py mintajara):

1) MINTA EXPORT:
   python 13_evidence_presence_validation.py --export \
       --judge-input "evaluations/llm_eval_runs_*.csv" \
       --typed-elements typed_elements.json --per-mode 30 --seed 20260714 \
       --out analysis/evidence_presence_sample.csv

2) KEZI ITELET: nyisd meg a CSV-t, es a human_verdict oszlopba ird a fenti 4 cimke egyiket.
   Csak a human_verdict (es opcionalisan a notes) oszlopot szerkeszd!
   Ha window_is_fallback=True, az ablak NEM anchor-alapu (az evidence eleje) — ABSENT elott
   nezd meg a teljes evidencet a nyers CSV-ben!

3) OSSZESITES:
   python 13_evidence_presence_validation.py --summarize --in analysis/evidence_presence_sample.csv

Megjegyzes a seedrol: a 20260714 UJ seed — regisztrald a deviations-tablaban. Ne hasznald ujra
a 20260712-t (az a 12-es miss-minta seedje volt).

[VERIFY] Az overlap-formula itt: |elem_termek ∩ szoveg_termek| / |elem_termek| >= thr (0.5),
exp_core.obj_tokenize + obj_stemish termekkel. Futtatas elott vesd ossze a 12-es /
exp_core-beli matcher formulaval — ha ott mas a szamlalo/nevezo, a mintazott halmaz nem
egyezik a pipeline miss-halmazaval.
"""
import argparse, csv, glob, json, random, sys, collections, re

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))  # hybrid evidence tail > 128k default limit

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_\-']{3,}")
VALID_VERDICTS = {"PRESENT_USABLE", "PRESENT_SCATTERED", "PRESENT_CONTRADICTED", "ABSENT"}
CORE_MODES = ("vector", "graph", "hybrid")

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
        # nincs anchor (a TOKEN_RE heurisztika nem talalta meg az obj_tokenize-talalatot)
        return ev[:2 * radius], (len(ev) <= 2 * radius), 0, True
    best_center, best_cov = pos_stem[0][0], -1
    for c, _ in pos_stem:
        stems = {s for p, s in pos_stem if c - radius <= p <= c + radius}
        if len(stems) > best_cov:
            best_cov, best_center = len(stems), c
    lo = max(0, best_center - radius); hi = min(len(ev), best_center + radius)
    return ev[lo:hi], (len(ev) <= 2 * radius), best_cov, False

def iter_integration_misses(rows, gt, term_set, thr):
    """Yield (row, element) where element is absent in gherkin (<thr) but present in evidence (>=thr)."""
    for r in rows:
        elements = gt.get(r.get("reqId", ""), [])
        ev = term_set(r.get("evidenceText", ""))
        gh = term_set(r.get("gherkin", ""))
        for el in elements:
            terms = term_set(el.get("text", ""))
            if not terms:
                continue
            if len(terms & gh) / len(terms) >= thr:   # covered in gherkin -> not a miss
                continue
            if len(terms & ev) / len(terms) >= thr:    # present in evidence -> integration miss
                yield r, el

def dedupe_to_cells(pairs):
    """(row, element) parok -> cella-szintu egysegek: (reqId, mode, model, element).
    Reprezentativ sor = legkisebb testId (determinisztikus). Visszaadja a tesztszamot is."""
    cells = {}
    for r, el in pairs:
        key = (r.get("reqId"), row_mode(r), r.get("model"),
               el.get("text", ""), el.get("element_type", "local"))
        cur = cells.get(key)
        if cur is None:
            cells[key] = {"row": r, "el": el, "n": 1}
        else:
            cur["n"] += 1
            if (r.get("testId") or "") < (cur["row"].get("testId") or ""):
                cur["row"] = r
    units = [(k, v) for k, v in cells.items()]
    units.sort(key=lambda kv: kv[0])  # determinisztikus sorrend a mintavetel elott
    return units

def do_export(args):
    tok, stem, term_set = load_core()
    rows = load_rows(args.judge_input)
    gt = load_gt(args.typed_elements)
    pairs = list(iter_integration_misses(rows, gt, term_set, args.thr))
    units = dedupe_to_cells(pairs)
    by_mode = collections.defaultdict(list)
    for key, v in units:
        by_mode[key[1]].append((key, v))
    print(f"integration-miss parok (tesztsor-szint): {len(pairs)}; "
          f"dedupe utan (cella x elem): {len(units)}")
    print("egysegek modonkent:", {m: len(v) for m, v in sorted(by_mode.items())})
    rnd = random.Random(args.seed)
    sample = []
    for mode in CORE_MODES:
        bucket = by_mode.get(mode, [])
        take = min(args.per_mode, len(bucket))
        if take < args.per_mode:
            print(f"FIGYELEM: {mode} modbol csak {take} elerheto (< {args.per_mode}).")
        sample += rnd.sample(bucket, take)
    rnd.shuffle(sample)
    cols = ["sample_id", "reqId", "model", "mode", "testId", "n_test_occurrences",
            "element_type", "element_text", "evidence_window", "full_evidence",
            "window_is_fallback", "anchor_terms_in_window", "gherkin_test",
            "matcher_verdict", "human_verdict", "notes"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for i, (key, v) in enumerate(sample, 1):
            r, el = v["row"], v["el"]
            win, full, cov, fb = anchor_window(r.get("evidenceText", ""),
                                               term_set(el.get("text", "")), stem, args.radius)
            w.writerow({
                "sample_id": i, "reqId": r.get("reqId"), "model": r.get("model"),
                "mode": row_mode(r), "testId": r.get("testId"),
                "n_test_occurrences": v["n"],
                "element_type": el.get("element_type", "local"),
                "element_text": el.get("text", ""),
                "evidence_window": win, "full_evidence": full,
                "window_is_fallback": fb, "anchor_terms_in_window": cov,
                "gherkin_test": r.get("gherkin", ""),
                "matcher_verdict": "present_in_evidence",
                "human_verdict": "", "notes": "",
            })
    comp = collections.Counter(key[1] for key, _ in sample)
    print(f"minta: {len(sample)} sor -> {args.out} (seed={args.seed})")
    print("mod-osszetetel:", dict(comp))
    print("Kovetkezo lepes: human_verdict = PRESENT_USABLE / PRESENT_SCATTERED / "
          "PRESENT_CONTRADICTED / ABSENT")

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
        print(f"  {k:<20} {v:>4}  ({v/n*100:.1f}%)")
    pu = verdicts.get("PRESENT_USABLE", 0); ps = verdicts.get("PRESENT_SCATTERED", 0)
    pc = verdicts.get("PRESENT_CONTRADICTED", 0); ab = verdicts.get("ABSENT", 0)
    present_any = pu + ps + pc
    print(f"\n'present in evidence' helyes (barmely PRESENT):  {present_any/n*100:.1f}%")
    print(f"  ebbol egyben hasznalhato (PRESENT_USABLE):      {pu/n*100:.1f}%")
    print(f"matcher tevedett (ABSENT -> valojaban retrieval-miss): {ab/n*100:.1f}%")
    print("Cikkbe: 'evidence-presence validation of N misses: X% truly present, of which "
          "Y% usable; Z% mislabeled (absent)'")
    # modonkent (a kontextusmeret hatasa)
    by_mode = collections.defaultdict(collections.Counter)
    for r in rows:
        v = r["human_verdict"].strip().upper()
        if v:
            by_mode[r["mode"]][v] += 1
    print("\nmodonkent (present_any %):")
    for m, c in sorted(by_mode.items()):
        tot = sum(c.values())
        pa = c.get("PRESENT_USABLE", 0) + c.get("PRESENT_SCATTERED", 0) + c.get("PRESENT_CONTRADICTED", 0)
        print(f"  {m:<8} n={tot:<4} present={pa/tot*100:.0f}%  usable={c.get('PRESENT_USABLE',0)/tot*100:.0f}%")
    fb = sum(1 for r in rows if r.get("window_is_fallback", "").strip() in ("True", "true", "1"))
    if fb:
        print(f"\nMEGJ.: {fb} sor ablaka fallback (nem anchor-alapu) volt — ezeknel a teljes "
              f"evidencet is erdemes volt megnezni.")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true")
    g.add_argument("--summarize", action="store_true")
    ap.add_argument("--judge-input")
    ap.add_argument("--typed-elements", default="typed_elements.json")
    ap.add_argument("--per-mode", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260714)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--radius", type=int, default=500)
    ap.add_argument("--out", default="analysis/evidence_presence_sample.csv")
    ap.add_argument("--in", dest="infile", default="analysis/evidence_presence_sample.csv")
    args = ap.parse_args()
    if args.export and not args.judge_input:
        ap.error("--judge-input kotelezo az exporthoz")
    if args.export: do_export(args)
    else: do_summarize(args)

if __name__ == "__main__":
    main()
