#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""19_provenance_audit.py — typed_elements draft vs vegleges diff + tipus-szamok.
Futtatas: python 19_provenance_audit.py  (a projektmappabol)"""
import json, collections, glob, sys

final = json.load(open("typed_elements.json", encoding="utf-8"))
cand = glob.glob("typed_elements_draft*.json")
draft = json.load(open(cand[0], encoding="utf-8")) if cand else None
print("draft fajl:", cand[0] if cand else "NINCS MEG — csak a vegleges szamai")

def stats(d, label):
    els = [(r, e["text"], e.get("element_type", "?")) for r, v in d.items()
           for e in (v.get("elements") or [])]
    print(f"{label}: {len(els)} elem, {len(d)} reqId")
    print("  tipusok:", dict(collections.Counter(t for _, _, t in els)))
    return {(r, t.strip()): ty for r, t, ty in els}

F = stats(final, "VEGLEGES")
if draft:
    D = stats(draft, "DRAFT   ")
    removed = [k for k in D if k not in F]
    added = [k for k in F if k not in D]
    retyped = [(k, D[k], F[k]) for k in D if k in F and D[k] != F[k]]
    print(f"\ntorolt elem: {len(removed)} | uj elem: {len(added)} | atttipusozott: {len(retyped)}")
    for k, a, b in retyped[:10]:
        print(f"  attipus: {k[0]}  {a} -> {b}   ({k[1][:60]}...)")
    if removed[:5]:
        print("  torolt peldak:", [(r, t[:50]) for r, t in removed[:5]])
    if added[:5]:
        print("  uj peldak:", [(r, t[:50]) for r, t in added[:5]])
