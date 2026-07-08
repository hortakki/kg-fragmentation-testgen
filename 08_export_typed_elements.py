#!/usr/bin/env python3
"""
08_export_typed_elements.py — Standalone exporter of TYPED, per-requirement
ground-truth elements for the H4 decomposition (Opció 1). Does NOT touch
exp_core.py (frozen). Queries Neo4j directly for each requirement's fragmentation
neighbours + their relation types, assigns one element_type per element by a
documented priority, and writes typed_elements_draft.json for HUMAN VALIDATION.

Workflow:
  1) python 08_export_typed_elements.py --export
         -> typed_elements_draft.json  (element_type from graph relations)
  2) MANUAL: review text + element_type, fix any label, then set
         "reference_status": "human_validated" per requirement (or globally).
     Save as typed_elements.json.
  3) 07_hypothesis_analysis.py --h4 --typed-elements typed_elements.json

element_type priority (most specific wins; documented convention):
  conflict (CONFLICTS_WITH) > gap (IDENTIFIES_GAP_IN) > cross_module (AFFECTS)
  > supersede (SUPERSEDES/VIOLATES_REQUIREMENT) > refine (REFINES).
Target-document bullet rules are 'local'. HAS_COMMENT excluded (absent in graph).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

FRAG_TYPE_PRIORITY = [
    ("CONFLICTS_WITH", "conflict"),
    ("IDENTIFIES_GAP_IN", "gap"),
    ("AFFECTS", "cross_module"),
    ("SUPERSEDES", "supersede"),
    ("VIOLATES_REQUIREMENT", "supersede"),
    ("REFINES", "refine"),
]
FRAG_RELS = [r for r, _ in FRAG_TYPE_PRIORITY]


def frag_type_for(rel_types: set) -> str:
    for rel, etype in FRAG_TYPE_PRIORITY:
        if rel in rel_types:
            return etype
    return "refine"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _neighbor_text(props: dict) -> str:
    bits = [props.get("name"), props.get("title"), props.get("desc"),
            props.get("description"), props.get("summary")]
    return _norm(" ".join(str(b) for b in bits if b and _norm(str(b))))


_SPLIT_RE = re.compile(r"(?:\r?\n|(?<=[.;!?])\s+|^\s*[-*•]\s+)", re.MULTILINE)

def _local_rules(props: dict) -> list[str]:
    """Target's own body split into bullet/sentence-level rules (NOT one blob):
    a single concatenated element would never reach the coverage threshold in
    a test but would almost always be 'present' in the evidence, forcing every
    local element into integration_miss and biasing H4."""
    bits = [props.get("body"), props.get("text"), props.get("description"),
            props.get("desc")]
    raw = "\n".join(str(b) for b in bits if b)
    rules = []
    for part in _SPLIT_RE.split(raw):
        part = _norm(part)
        # min length filter: drop headers/fragments with too little content
        if part and len(part.split()) >= 4:
            rules.append(part)
    # name/title as a single short identifying rule if nothing else survived
    if not rules:
        t = _norm(" ".join(str(props.get(k, "")) for k in ("name", "title")))
        if t:
            rules.append(t)
    return rules


def export(out_path: Path) -> None:
    load_dotenv()
    from neo4j import GraphDatabase
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    pwd = os.environ["NEO4J_PASSWORD"]
    db = os.environ.get("NEO4J_DATABASE", "neo4j")

    q = """
    MATCH (r:Requirement)
    OPTIONAL MATCH (r)-[rel]-(n)
    WHERE type(rel) IN $frag_rels AND NOT n:SrcChunk
    WITH r, n, collect(DISTINCT type(rel)) AS rel_types
    RETURN r.id AS reqId, properties(r) AS r_props,
           collect({props: properties(n), rel_types: rel_types}) AS neighbors
    ORDER BY reqId
    """
    result: dict[str, Any] = {}
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session(database=db) as session:
        for rec in session.run(q, frag_rels=FRAG_RELS):
            req = rec["reqId"]
            elements = []
            seen = set()
            # local element from the requirement itself
            # local elements: bullet/sentence-level rules from the target itself
            for rule in _local_rules(rec["r_props"] or {}):
                if rule in seen:
                    continue
                seen.add(rule)
                elements.append({"text": rule, "element_type": "local"})
            for nb in rec["neighbors"]:
                props = nb.get("props") or {}
                rel_types = set(nb.get("rel_types") or [])
                if not rel_types.intersection(FRAG_RELS):
                    continue
                text = _neighbor_text(props)
                if not text or text in seen:
                    continue
                seen.add(text)
                elements.append({"text": text, "element_type": frag_type_for(rel_types)})
            result[req] = {
                "reqId": req,
                "elements": elements,
                "reference_status": "heuristic_draft",  # -> human_validated after review
            }
    driver.close()
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    n_el = sum(len(v["elements"]) for v in result.values())
    print(f"Wrote {out_path}: {len(result)} requirements, {n_el} typed elements.")
    print("MANUAL STEP: review element_type labels, then set reference_status="
          "'human_validated' and save as typed_elements.json.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--export", action="store_true")
    p.add_argument("--out", default="typed_elements_draft.json")
    args = p.parse_args()
    if args.export:
        export(Path(args.out))
    else:
        p.print_help()


if __name__ == "__main__":
    main()
