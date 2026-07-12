#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
09_reference_validate.py — önálló segéd, NEM nyúl az exp_core-hoz.

Kétlépéses kézi validálás:
  1) --export-review : a reference JSON canonical_pointjait átnézhető TXT-be írja
       python 09_reference_validate.py --export-review ^
         --input evaluations/reference_draft_20260707_183716.json ^
         --review-txt reference_review.txt
     A TXT-ben soronként: REQID<TAB>pont. Szerkesztés: TÖRÖLD a rossz sorokat
     (pl. önálló nevek: Dave, Viktor). Sort módosítani szabad, hozzáadni is
     (REQID<TAB>szöveg formában). A # kezdetű sorok kommentek.
  2) --apply-review : a szerkesztett TXT-ből új JSON-t épít, minden mező
     megőrzésével, a canonical_points cseréjével és
     reference_status = "human_validated" beállítással.
       python 09_reference_validate.py --apply-review ^
         --input evaluations/reference_draft_20260707_183716.json ^
         --review-txt reference_review.txt ^
         --output evaluations/reference.json
     Kiír egy diff-összegzést (törölt/módosított/új pontok reqId-nként).
"""
import argparse, json, sys, collections, unicodedata

# Gyanú-heurisztika csak JELÖLÉSRE (a TXT-ben [GYANUS] prefix-komment), nem töröl:
SUSPECT_MAX_LEN = 30
KNOWN_AUTHOR_TOKENS = {
    "dave", "viktor", "marta", "nora", "lesly", "tomas",
    "developer", "engineer", "writer", "master", "qa", "ux",
    "backend", "security", "tool",
}

def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip())

def is_suspect(point: str) -> bool:
    p = point.strip()
    words = [w.strip('.,:;"\'').lower() for w in p.split()]
    if not words:
        return True
    # Csupa név/beosztás tokenből álló rövid elem
    if len(p) <= SUSPECT_MAX_LEN and all(w in KNOWN_AUTHOR_TOKENS for w in words):
        return True
    # Egyszavas elem, nagybetűvel kezdődik, nincs benne tartalmi jel
    if len(words) == 1 and p[:1].isupper() and p.isalpha():
        return True
    return False

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def export_review(args):
    d = load(args.input)
    n_total, n_suspect = 0, 0
    with open(args.review_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write("# reference kezi validalas — torold a rossz sorokat, mentsd, majd --apply-review\n")
        f.write("# formatum: REQID<TAB>canonical_point  (a # sorok kommentek)\n")
        for rid in sorted(d, key=lambda x: (len(x), x)):
            pts = d[rid].get("canonical_points", [])
            f.write(f"\n# ===== {rid} ({len(pts)} pont) =====\n")
            for p in pts:
                one_line = " ".join(norm(p).split())  # sortoresek kiszedese
                if is_suspect(one_line):
                    f.write("# [GYANUS] az alabbi sor valoszinuleg zaj (nev/ures cimke):\n")
                    n_suspect += 1
                f.write(f"{rid}\t{one_line}\n")
                n_total += 1
    print(f"Exportalva: {args.review_txt} — {n_total} pont, ebbol {n_suspect} [GYANUS] jelolessel.")
    print("Szerkeszd (torles/javitas), majd futtasd az --apply-review lepest.")

def apply_review(args):
    d = load(args.input)
    kept = collections.defaultdict(list)
    with open(args.review_txt, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                sys.exit(f"HIBA: {i}. sor nem 'REQID<TAB>szoveg' formatumu: {line!r}")
            rid, pt = line.split("\t", 1)
            rid, pt = rid.strip(), norm(pt)
            if rid not in d:
                sys.exit(f"HIBA: {i}. sor ismeretlen reqId: {rid!r}")
            if pt:
                kept[rid].append(pt)
    out = {}
    tot_before = tot_after = 0
    print(f"{'reqId':<8}{'elotte':>8}{'utana':>8}{'valtozas':>10}")
    for rid, entry in d.items():
        before = entry.get("canonical_points", [])
        # egysorositott elotte-lista az osszehasonlitashoz
        before_norm = [" ".join(norm(p).split()) for p in before]
        after = kept.get(rid, [])
        e = dict(entry)
        e["canonical_points"] = after
        e["reference_status"] = "human_validated"
        out[rid] = e
        tot_before += len(before_norm)
        tot_after += len(after)
        if len(before_norm) != len(after) or set(before_norm) != set(after):
            print(f"{rid:<8}{len(before_norm):>8}{len(after):>8}{len(after)-len(before_norm):>+10}")
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nOsszesen: {tot_before} -> {tot_after} pont ({tot_after - tot_before:+d}).")
    print(f"Kiirva: {args.output} (minden reqId: reference_status=human_validated)")
    empty = [rid for rid, e in out.items() if not e["canonical_points"]]
    if empty:
        print(f"FIGYELEM: {len(empty)} reqId 0 ponttal maradt: {', '.join(empty)}")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export-review", action="store_true")
    g.add_argument("--apply-review", action="store_true")
    ap.add_argument("--input", required=True)
    ap.add_argument("--review-txt", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()
    if args.apply_review and not args.output:
        ap.error("--apply-review eseten --output kotelezo")
    (export_review if args.export_review else apply_review)(args)

if __name__ == "__main__":
    main()
    