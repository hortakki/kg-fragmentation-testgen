#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
14_review_response.py — EMSE review M2/M4/M6 szamitasok egy futasban.

Futtatas (projektmappaból):
  python 14_review_response.py --judge-input "evaluations/llm_eval_runs_*.csv" ^
      --typed-elements typed_elements.json

Kimenet: stdout tablak (masold be a beszelgetesbe) + analysis/review_response.json

Reszek:
  [A] SUITE-SZINTU H4 (review-M2): elem fedett-e a cella BARMELY tesztjeben;
      retrieval/integration miss cella-szinten, mode x model + tipusonkent N-ekkel.
  [B] NO_RESOLUTION kar (review-M6): hybrid full vs no_resolution — judged
      atlagok + H4 dekompozicio mindket karon (teszt- es suite-szinten).
  [C] RETRIEVAL-TELITETTSEG (review-M4): per-mode evidencia-recall a typed
      elemek ellen, kontextushossz-statisztikak, pozicio-analizis (a hit vs
      integration-missed elemek relativ pozicioja az evidenceText-ben).
"""
import argparse, csv, glob, json, collections, statistics as st
from pathlib import Path

THR = 0.5

def load_core():
    import exp_core as E
    tok = E.obj_tokenize
    stem = getattr(E, "obj_stemish", lambda t: t)
    return lambda text: {stem(t) for t in tok(text or "")}

def load_rows(pattern, pipelines):
    rows = []
    for f in glob.glob(pattern):
        with open(f, encoding="utf-8") as fh:
            rows += [r for r in csv.DictReader(fh)
                     if r.get("evalStatus") == "ok" and r.get("repeatIndex") == "0"
                     and r.get("pipeline") in pipelines]
    return rows

def load_gt(path):
    d = json.load(open(path, encoding="utf-8"))
    return {k: v.get("elements") or [] for k, v in d.items()}

def elem_status(el_terms, gh_terms, ev_terms):
    covered = len(el_terms & gh_terms) / len(el_terms) >= THR
    present = len(el_terms & ev_terms) / len(el_terms) >= THR
    return covered, present

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-input", required=True)
    ap.add_argument("--typed-elements", default="typed_elements.json")
    args = ap.parse_args()
    term_set = load_core()
    gt = load_gt(args.typed_elements)
    gt_terms = {req: [(e.get("element_type", "local"), e["text"], term_set(e["text"]))
                      for e in els if term_set(e["text"])]
                for req, els in gt.items()}
    out = {}

    # ---------- [A] SUITE-SZINTU H4 (full pipeline) ----------
    rows = load_rows(args.judge_input, {"full"})
    cells = collections.defaultdict(list)  # (model,mode,req) -> [rows]
    for r in rows:
        cells[(r["model"], r["mode"], r["reqId"])].append(r)
    suite = collections.defaultdict(lambda: {"rm": 0, "im": 0, "cov": 0, "n_el": 0})
    by_type = collections.defaultdict(lambda: [0, 0, 0])  # type -> [rm, im, covered]
    for (model, mode, req), rs in cells.items():
        gh_union = set()
        ev_union = set()
        for r in rs:
            gh_union |= term_set(r.get("gherkin", ""))
            ev_union |= term_set(r.get("evidenceText", ""))
        k = (mode, model)
        for etype, _txt, terms in gt_terms.get(req, []):
            suite[k]["n_el"] += 1
            covered = len(terms & gh_union) / len(terms) >= THR
            if covered:
                suite[k]["cov"] += 1; by_type[etype][2] += 1
                continue
            present = len(terms & ev_union) / len(terms) >= THR
            if present:
                suite[k]["im"] += 1; by_type[etype][1] += 1
            else:
                suite[k]["rm"] += 1; by_type[etype][0] += 1
    print("=== [A] SUITE-SZINTU H4 (elem fedett-e a cella BARMELY tesztjeben) ===")
    print(f"{'mode':<8}{'model':<28}{'n_elem':>7}{'covered%':>10}{'retr_miss%':>12}{'integ_miss%':>13}{'integ_share%':>13}")
    A = {}
    for (mode, model), a in sorted(suite.items()):
        n = a["n_el"]; miss = a["rm"] + a["im"]
        row = dict(n=n, covered=a["cov"]/n*100, rm=a["rm"]/n*100, im=a["im"]/n*100,
                   share=(a["im"]/miss*100 if miss else 0))
        A[f"{mode}|{model}"] = row
        print(f"{mode:<8}{model:<28}{n:>7}{row['covered']:>9.1f}%{row['rm']:>11.1f}%{row['im']:>12.1f}%{row['share']:>12.1f}%")
    print("\nTipusonkent (suite-szint, pooled, ABSZOLUT N-ekkel):")
    print(f"{'type':<14}{'n_osszes':>9}{'covered':>9}{'ret_miss':>9}{'int_miss':>9}{'int_share%':>11}")
    for t, (rm, im, cov) in sorted(by_type.items()):
        tot = rm + im + cov; miss = rm + im
        print(f"{t:<14}{tot:>9}{cov:>9}{rm:>9}{im:>9}{(im/miss*100 if miss else 0):>10.1f}%")
    out["suite_h4"] = A

    # ---------- [B] NO_RESOLUTION kar ----------
    rows_nr = load_rows(args.judge_input, {"full", "no_resolution"})
    hyb = [r for r in rows_nr if r["mode"] == "hybrid"]
    print("\n=== [B] NO_RESOLUTION vs FULL (hybrid) ===")
    DIMS = ("requirement_alignment", "target_specificity", "evidence_grounding",
            "executability", "gherkin_quality", "coverage")
    print(f"{'pipeline':<15}{'model':<28}{'n':>6}" + "".join(f"{d[:8]:>10}" for d in DIMS))
    for pipe in ("full", "no_resolution"):
        for model in sorted({r['model'] for r in hyb}):
            sub = [r for r in hyb if r["pipeline"] == pipe and r["model"] == model]
            if not sub: continue
            means = [st.mean(float(r[d]) for r in sub) for d in DIMS]
            print(f"{pipe:<15}{model:<28}{len(sub):>6}" + "".join(f"{m:>10.3f}" for m in means))
    # H4 dekompozicio karonkent (teszt-szint)
    print(f"\nH4 dekompozicio (teszt-szint, hybrid):")
    print(f"{'pipeline':<15}{'model':<28}{'retr_miss%':>12}{'integ_miss%':>13}{'total%':>9}")
    B = {}
    for pipe in ("full", "no_resolution"):
        for model in sorted({r['model'] for r in hyb}):
            sub = [r for r in hyb if r["pipeline"] == pipe and r["model"] == model]
            rm = im = tot = 0
            for r in sub:
                gh = term_set(r.get("gherkin", "")); ev = term_set(r.get("evidenceText", ""))
                for _t, _x, terms in gt_terms.get(r["reqId"], []):
                    tot += 1
                    c, p = elem_status(terms, gh, ev)
                    if c: continue
                    if p: im += 1
                    else: rm += 1
            if tot:
                B[f"{pipe}|{model}"] = dict(rm=rm/tot*100, im=im/tot*100)
                print(f"{pipe:<15}{model:<28}{rm/tot*100:>11.1f}%{im/tot*100:>12.1f}%{(rm+im)/tot*100:>8.1f}%")
    out["no_resolution"] = B

    # ---------- [C] TELITETTSEG + POZICIO ----------
    print("\n=== [C] RETRIEVAL-TELITETTSEG ===")
    print(f"{'mode':<8}{'evid. karakter (med)':>21}{'elem-recall%':>13}")
    C = {}
    pos_hit, pos_miss = [], []
    for mode in ("vector", "graph", "hybrid"):
        sub = [r for r in rows if r["mode"] == mode]
        # cella-szinten 1 evidencia eleg (cellan belul azonos)
        seen = {}
        for r in sub:
            seen.setdefault((r["model"], r["reqId"]), r)
        lens, rec_num, rec_den = [], 0, 0
        for (model, req), r in seen.items():
            ev_txt = r.get("evidenceText", "")
            ev = term_set(ev_txt)
            lens.append(len(ev_txt))
            for _t, txt, terms in gt_terms.get(req, []):
                rec_den += 1
                present = len(terms & ev) / len(terms) >= THR
                if present:
                    rec_num += 1
                    # pozicio: az elem legjellegzetesebb tokenjenek elso elofordulasa
                    anchor = max(terms, key=len)
                    idx = ev_txt.lower().find(anchor.lower())
                    if idx >= 0 and len(ev_txt) > 0:
                        # hit vs integration-miss kesobb: itt csak present elemek
                        gh = term_set(r.get("gherkin", ""))
                        rel = idx / len(ev_txt)
                        if len(terms & gh) / len(terms) >= THR: pos_hit.append(rel)
                        else: pos_miss.append(rel)
        med = sorted(lens)[len(lens)//2] if lens else 0
        C[mode] = dict(median_evidence_chars=med, element_recall=rec_num/rec_den*100 if rec_den else 0)
        print(f"{mode:<8}{med:>21}{C[mode]['element_recall']:>12.1f}%")
    if pos_hit and pos_miss:
        print(f"\nPozicio-analizis (elem relativ helye az evidenceText-ben, 0=eleje):")
        print(f"  fedett (hit) elemek:      n={len(pos_hit):>5}  median={st.median(pos_hit):.3f}  atlag={st.mean(pos_hit):.3f}")
        print(f"  integration-miss elemek:  n={len(pos_miss):>5}  median={st.median(pos_miss):.3f}  atlag={st.mean(pos_miss):.3f}")
        out["position"] = dict(hit_median=st.median(pos_hit), miss_median=st.median(pos_miss),
                               hit_n=len(pos_hit), miss_n=len(pos_miss))
    out["saturation"] = C
    Path("analysis").mkdir(exist_ok=True)
    with open("analysis/review_response.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nMentve: analysis/review_response.json")

if __name__ == "__main__":
    main()
