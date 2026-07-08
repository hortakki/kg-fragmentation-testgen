"""
exp_core.py — Shared core for the fragmented-requirements test-generation study.

Single source of truth for:
  * retrieval (graph / vector / hybrid) against Neo4j
  * evidence filtering heuristics (identical across providers)
  * context resolution (LLM + documented heuristic post-processing with provenance flags)
  * Gherkin generation (pipeline variants: full / no_resolution / no_retrieval)
  * LLM client layer (OpenAI + Anthropic) with response-level disk cache
    and Anthropic prompt caching
  * subjective (LLM-judge) evaluation over PERSISTED evidence
  * objective, document-grounded evaluation with a freezable reference set
  * run metadata logging for reproducibility

All provider-specific entry points (03/03c/05/05C/06/06C) are thin wrappers
around this module, which guarantees that both models are generated and
evaluated with byte-identical logic.

PROMPT_VERSION must be bumped whenever any prompt text changes, so that
runs are attributable to an exact prompt revision.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import platform
import re
import time
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("exp_core")

# ---------------------------------------------------------------------------
# Versioning & environment
# ---------------------------------------------------------------------------

PROMPT_VERSION = "2026-07-05.v4"        # bump on ANY prompt change
PIPELINE_VERSION = "2026-07-05.v4"      # bump on ANY logic change affecting outputs

NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
VECTOR_INDEX_NAME = os.environ.get("VECTOR_INDEX_NAME", "srcChunkEmb")

MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "8"))
# Exponential backoff: sleep = min(RETRY_BASE * 2**attempt, RETRY_MAX) + jitter.
# Defaults tuned to ride out sustained "high demand" 503/429/overloaded periods
# (esp. gemini-2.5-flash-lite) instead of failing the row after a few seconds.
RETRY_BASE_SECONDS = float(os.environ.get("LLM_RETRY_BASE_SECONDS", "2"))
RETRY_MAX_SECONDS = float(os.environ.get("LLM_RETRY_MAX_SECONDS", "60"))
DEFAULT_OUT_DIR = "runs"
DEFAULT_EVAL_DIR = "evaluations"
DEFAULT_LLM_CACHE_DIR = "cache/llm"
DEFAULT_DATA_CACHE_DIR = "cache/data"

# ---------------------------------------------------------------------------
# Heuristic vocabularies (verbatim from the original pipeline, now documented:
# these are researcher-authored, domain-specific cue lists and MUST be
# disclosed in the paper's Methodology / Threats to Validity).
# ---------------------------------------------------------------------------

GEN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "if", "in", "into", "is", "it",
    "of", "on", "or", "that", "the", "their", "then", "there", "these", "this", "to", "when", "with",
    "user", "users", "system", "must", "should", "can", "may", "after", "before", "during", "within",
    "shall", "will", "not", "become", "becomes", "requirement", "target", "field", "fields", "screen",
    "page",
}

CURRENT_CUES = {
    "current", "latest", "newest", "final", "effective", "active", "official", "current version",
    "new version", "updated version", "current lifecycle", "current specification",
}
STALE_CUES = {
    "old", "older", "older version", "previous", "prior", "legacy", "deprecated", "obsolete",
    "archived", "superseded", "archival", "earlier version", "historical", "outdated",
}

PRIMARY_RELATIONS = {
    "CONFLICTS_WITH", "SUPERSEDES", "OVERRIDES_FOR_CATEGORY", "USES_OBSOLETE_DATA_FROM",
    "VIOLATES_REQUIREMENT", "IMPLEMENTS", "DEFINED_IN", "PARTIALLY_IMPLEMENTS",
}
CONTEXT_RELATIONS = {"AFFECTS", "REFINES", "VECTOR_SIMILARITY"}

EXCEPTION_CUES = {
    "exception", "exceptions", "override", "overrides", "category-specific", "specific category",
    "only for", "only when", "special case", "special cases", "for category", "per category",
}
GAP_CUES = {
    "matrix", "depends on", "dependent on", "based on category", "category-dependent",
    "per category", "configuration-dependent", "conditional", "condition-dependent",
    "tbd", "to be defined", "not defined", "missing", "unknown", "unclear", "pending",
    "external table", "lookup table", "config table",
}
ABSTRACT_OPERATIVE_CUES = {
    "consistency", "alignment", "across all", "appropriate", "properly", "correctly",
    "expected behavior", "handling", "process correctly", "remain aligned",
}
SPECIFIC_RULE_CUES = {
    "round", "rounded", "rounding", "decimal", "precision", "status", "checkbox",
    "submit", "maintenance", "available", "non-rentable", "rentable", "blocked", "disabled",
}
CONFLICT_CUES = {
    "conflict", "conflicts", "violates", "violation", "obsolete", "deprecated", "superseded",
    "legacy", "older version", "old behavior",
}
META_PROVENANCE_PATTERNS = [
    r"\bis defined in\b", r"\bis described in\b", r"\bis specified in\b", r"\bis implemented by\b",
    r"\bdescribed in\b", r"\bspecified in\b", r"\bimplemented by\b",
]
BEHAVIOR_VERBS = {
    "allow", "approve", "block", "calculate", "capture", "complete", "create", "generate", "handle",
    "maintain", "notify", "prevent", "reject", "require", "return", "set", "synchronize", "track",
    "transition", "update", "validate", "wait", "mark", "round", "disable", "enable", "apply",
}

# Objective-eval vocabularies (kept separate from generation vocabularies on purpose)
OBJ_STOPWORDS = {
    'a', 'az', 'egy', 'és', 'vagy', 'hogy', 'nem', 'van', 'volt', 'lesz', 'kell', 'kelljen', 'ha', 'akkor', 'mint', 'is',
    'to', 'the', 'and', 'or', 'of', 'for', 'with', 'without', 'must', 'should', 'shall', 'can', 'cannot', 'be', 'are',
    'given', 'when', 'then', 'but', 'user', 'system', 'page', 'screen', 'field', 'button', 'test', 'case',
    'this', 'that', 'these', 'those', 'upon', 'after', 'before', 'from', 'into', 'onto', 'under', 'over',
    'verify', 'validates', 'validation', 'expected', 'result',
}
SYNONYM_MAP = {
    'transition': ['state', 'status', 'change', 'flow', 'lifecycle'],
    'end': ['complete', 'completion', 'completed', 'finish', 'finished'],
    'post': ['after', 'following'],
    'rent': ['rental'],
    'create': ['creation', 'request', 'register', 'registration'],
    'cancel': ['cancellation', 'cancelled'],
    'maintain': ['maintenance'],
    'cleaning': ['maintenance'],
    'manual': ['operator'],
    'approve': ['approval', 'approved'],
    'reject': ['rejection', 'rejected'],
    'mandatory': ['required', 'obligatory'],
    'required': ['mandatory'],
    'registration': ['register', 'signup', 'sign', 'onboarding'],
    'field': ['fields', 'attribute', 'input'],
    'email': ['e-mail', 'mail'],
}
FRAGMENTATION_RELS = {
    "AFFECTS", "CONFLICTS_WITH", "IDENTIFIES_GAP_IN", "REFINES",
    "VIOLATES_REQUIREMENT", "HAS_COMMENT", "SUPERSEDES",
}

# ---------------------------------------------------------------------------
# JSON schemas
# ---------------------------------------------------------------------------

RESOLUTION_SCHEMA = {
    "name": "resolved_context",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "operative_context": {"type": "array", "items": {"type": "string"}},
            "exceptions": {"type": "array", "items": {"type": "string"}},
            "conflicts_or_obsolete": {"type": "array", "items": {"type": "string"}},
            "gaps_or_uncertainties": {"type": "array", "items": {"type": "string"}},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "string"},
        },
        "required": [
            "operative_context", "exceptions", "conflicts_or_obsolete",
            "gaps_or_uncertainties", "supporting_evidence_ids", "notes",
        ],
        "additionalProperties": False,
    },
}

GENERATION_FROM_CONTEXT_SCHEMA = {
    "name": "gherkin_generation_from_context",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "test_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "gherkin": {"type": "string"},
                        "rationale": {"type": "string"},
                        "used_context_items": {"type": "array", "items": {"type": "string"}},
                        "used_source_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "gherkin", "rationale", "used_context_items", "used_source_ids"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "test_cases"],
        "additionalProperties": False,
    },
}

# NOTE: overall_score removed from the judge schema on purpose (fix B2).
# The composite is computed deterministically in code from the sub-scores.
JUDGE_SCHEMA = {
    "name": "gherkin_evaluation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "requirement_alignment": {"type": "integer"},
            "target_specificity": {"type": "integer"},
            "evidence_grounding": {"type": "integer"},
            "executability": {"type": "integer"},
            "gherkin_quality": {"type": "integer"},
            "coverage": {"type": "integer"},
            "is_generic": {"type": "boolean"},
            "drift_detected": {"type": "boolean"},
            "strengths": {"type": "string"},
            "weaknesses": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": [
            "requirement_alignment", "target_specificity", "evidence_grounding",
            "executability", "gherkin_quality", "coverage",
            "is_generic", "drift_detected", "strengths", "weaknesses", "reasoning",
        ],
        "additionalProperties": False,
    },
}

JUDGE_SUBSCORE_FIELDS = [
    "requirement_alignment", "target_specificity", "evidence_grounding",
    "executability", "gherkin_quality", "coverage",
]


def valid_judgement(payload: Any) -> bool:
    """Fix A-1: a judge response is valid only if every sub-score is an integer
    in 1..5 and the two flags are booleans. Blocks (a) caching malformed judge
    payloads and (b) the silent-zero averaging that would otherwise mark a row
    ok while feeding a 0 into the composite for a missing sub-score."""
    if not isinstance(payload, dict):
        return False
    for f in JUDGE_SUBSCORE_FIELDS:
        v = payload.get(f)
        # bool is a subclass of int — reject it explicitly for score fields.
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 5):
            return False
    for f in ("is_generic", "drift_detected"):
        if not isinstance(payload.get(f), bool):
            return False
    return True

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TargetNode:
    node_id: str
    labels: list[str]
    title: str
    body: str
    props: dict[str, Any]


@dataclass
class EvidenceItem:
    source_id: str
    source_type: str
    relation_path: list[str]
    hops: int
    score: Optional[float]
    text: str
    chunk_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class ResolvedContext:
    req_id: str
    mode: str
    operative_context: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    conflicts_or_obsolete: list[str] = field(default_factory=list)
    gaps_or_uncertainties: list[str] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    notes: str = ""
    # Provenance tracking (fix G1): statements injected by deterministic
    # heuristics — NOT produced by the LLM — are recorded here per bucket
    # so that Table-3-style statistics can be reported honestly
    # (llm-produced vs. heuristic-injected).
    injected: dict[str, list[str]] = field(default_factory=lambda: {
        "operative_context": [], "exceptions": [], "conflicts_or_obsolete": [], "gaps_or_uncertainties": [],
    })


@dataclass
class ResolutionEvidenceEntry:
    evidence_id: str
    item: EvidenceItem
    bucket: str
    reason: str

# ---------------------------------------------------------------------------
# Generic disk cache
# ---------------------------------------------------------------------------

def _cache_key(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _cache_load(path: Path, max_age_hours: float) -> Any:
    try:
        if not path.exists():
            return None
        if max_age_hours > 0:
            age_h = (time.time() - path.stat().st_mtime) / 3600.0
            if age_h >= max_age_hours:
                return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_save(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:  # cache failures must never break a run
        log.warning("Cache save failed (%s): %s", path, exc)

# ---------------------------------------------------------------------------
# LLM client layer (fix A2/A4/G4): one interface, two providers, shared
# response-level disk cache. Retries raise on final failure — NO silent
# zero-score fallbacks anywhere (fix A4).
# ---------------------------------------------------------------------------

class LLMClient:
    """Provider-agnostic structured-JSON LLM caller with disk response cache.

    cache key = (provider, model, system, user, schema, repeat_index)
    repeat_index MUST differ across intentional repeats, otherwise a repeat
    would be a cache hit and variance estimates would be fake.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        cache_dir: Optional[str] = DEFAULT_LLM_CACHE_DIR,
        cache_max_age_hours: float = 0.0,  # 0 = never expires
        anthropic_prompt_cache: bool = True,
    ):
        provider = provider.lower().strip()
        if provider not in {"openai", "anthropic", "gemini"}:
            raise ValueError(f"Unknown provider: {provider}")
        self.provider = provider
        self.model = model
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.cache_max_age_hours = cache_max_age_hours
        self.anthropic_prompt_cache = anthropic_prompt_cache
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == "gemini":
            # google-genai SDK: `pip install google-genai`
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            import anthropic
            self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._client

    # -- public API ---------------------------------------------------------

    def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        tool_name: str,
        max_tokens: int = 4096,
        repeat_index: int = 0,
        cache_validator: Optional[Any] = None,
    ) -> dict[str, Any]:
        if self.cache_dir is not None:
            key = _cache_key(self.provider, self.model, system_prompt, user_prompt,
                             schema, PROMPT_VERSION, repeat_index)
            path = self.cache_dir / f"llm_{key}.json"
            cached = _cache_load(path, self.cache_max_age_hours)
            if cached and isinstance(cached.get("payload"), dict):
                # Even a cached payload must pass validation — this heals caches
                # that were poisoned before validation existed (a bad response
                # saved by an older run is ignored and regenerated).
                if cache_validator is None or cache_validator(cached["payload"]):
                    return cached["payload"]
        else:
            path = None

        payload = self._call_uncached(system_prompt, user_prompt, schema, tool_name, max_tokens)

        # Only cache VALID responses. A malformed response (e.g. test_cases as a
        # bare string or empty) must never be cached, or the cell would fail
        # forever on every re-run. Invalid -> skip caching, let the caller retry.
        should_cache = path is not None and (cache_validator is None or cache_validator(payload))
        if should_cache:
            _cache_save(path, {
                "payload": payload,
                "meta": {
                    "provider": self.provider,
                    "model": self.model,
                    "prompt_version": PROMPT_VERSION,
                    "repeat_index": repeat_index,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                },
            })
        return payload

    # -- provider implementations -------------------------------------------

    # Substrings that mark a TRANSIENT, worth-retrying error (server overload,
    # rate limit, timeouts). Anything not matching is treated as likely
    # permanent (bad key, bad schema) and retried far less patiently.
    # B-3: the bare 5xx codes are matched with surrounding context ("http 500",
    # "error 500", "status 500", "code 500") to avoid false positives like
    # "5000ms". Word-level markers stay plain substrings.
    _TRANSIENT_MARKERS = (
        "429", "unavailable", "overloaded", "high demand",
        "rate limit", "timeout", "timed out", "temporarily", "try again",
        "connection", "reset by peer",
    )
    _TRANSIENT_5XX = ("500", "502", "503")

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        msg = str(exc).lower()
        if any(m in msg for m in LLMClient._TRANSIENT_MARKERS):
            return True
        import re as _re
        for code in LLMClient._TRANSIENT_5XX:
            if _re.search(rf"(?:http|error|status|code)\s*{code}\b", msg) or f"{code} " in msg and msg.strip().startswith(code):
                return True
        return False

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> float | None:
        """Best-effort parse of a server-provided Retry-After / retryDelay."""
        import re as _re
        m = _re.search(r"retry[-_ ]?(?:after|delay)\D{0,4}(\d+(?:\.\d+)?)", str(exc).lower())
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    def _call_uncached(self, system_prompt, user_prompt, schema, tool_name, max_tokens) -> dict[str, Any]:
        last_error: Exception | None = None
        cur_max_tokens = max_tokens
        for attempt in range(MAX_RETRIES):
            try:
                if self.provider == "openai":
                    return self._call_openai(system_prompt, user_prompt, schema)
                if self.provider == "gemini":
                    return self._call_gemini(system_prompt, user_prompt, schema, cur_max_tokens)
                return self._call_anthropic(system_prompt, user_prompt, schema, tool_name, cur_max_tokens)
            except Exception as exc:
                last_error = exc
                # Fix A-7: on a Gemini max_tokens truncation, double the budget
                # once (capped) so the next attempt has room for thinking+output.
                if "max_tokens" in str(exc).lower() and cur_max_tokens < 16384:
                    cur_max_tokens = min(cur_max_tokens * 2, 16384)
                    log.warning("Escalating max_tokens to %d after truncation", cur_max_tokens)
                    if attempt < MAX_RETRIES - 1:
                        continue
                transient = self._is_transient(exc)
                # Permanent-looking errors: don't burn all retries on them.
                if not transient and attempt >= 1:
                    log.warning("%s call failed (attempt %d/%d, non-transient): %s",
                                self.provider, attempt + 1, MAX_RETRIES, exc)
                    break
                if attempt == MAX_RETRIES - 1:
                    break
                # Honor server Retry-After if present, else jittered capped backoff.
                server_wait = self._retry_after_seconds(exc)
                if server_wait is not None:
                    delay = min(server_wait, RETRY_MAX_SECONDS)
                else:
                    delay = min(RETRY_BASE_SECONDS * (2 ** attempt), RETRY_MAX_SECONDS)
                delay += random.uniform(0, min(delay * 0.25, 5.0))  # jitter, capped
                log.warning("%s call failed (attempt %d/%d, %s): %s -- retrying in %.1fs",
                            self.provider, attempt + 1, MAX_RETRIES,
                            "transient" if transient else "non-transient", exc, delay)
                time.sleep(delay)
        # Fix A4: fail loudly. Callers must record the failure and EXCLUDE the
        # row from aggregates — never average silent zeros.
        raise RuntimeError(f"{self.provider}/{self.model} structured JSON call failed") from last_error

    def _call_openai(self, system_prompt, user_prompt, schema) -> dict[str, Any]:
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_schema", "json_schema": schema},
        )
        return json.loads(resp.choices[0].message.content)

    def _call_anthropic(self, system_prompt, user_prompt, schema, tool_name, max_tokens) -> dict[str, Any]:
        client = self._ensure_client()
        tool = {
            "name": tool_name,
            "description": "Return the result as structured JSON matching the required schema.",
            "input_schema": schema["schema"],
        }
        # Anthropic prompt caching: mark the (stable) system prompt as a cache
        # breakpoint. Saves cost when the same system prompt is reused across
        # many calls; harmless when below the minimum cacheable size.
        if self.anthropic_prompt_cache:
            system_blocks = [{"type": "text", "text": system_prompt,
                              "cache_control": {"type": "ephemeral"}}]
        else:
            system_blocks = system_prompt
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.0,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                data = getattr(block, "input", None)
                if not isinstance(data, dict):
                    raise ValueError("Claude tool_use input is not a dictionary")
                return data
        text_parts = [getattr(b, "text", "") for b in resp.content if getattr(b, "text", None)]
        if text_parts:
            joined = "\n".join(text_parts)
            start, end = joined.find("{"), joined.rfind("}") + 1
            if 0 <= start < end:
                parsed = json.loads(joined[start:end])
                if isinstance(parsed, dict) and parsed:
                    return parsed
        raise ValueError("Claude did not return a tool_use block or parseable JSON")

    @staticmethod
    def _gemini_sanitize_schema(node: Any) -> Any:
        """Convert an OpenAI-style JSON Schema into a Gemini-compatible one.

        Gemini's response_schema accepts a subset of JSON Schema. In particular
        it rejects `additionalProperties` and the OpenAI-only `strict` flag, and
        it wants plain nested objects. We recursively drop the unsupported keys
        and keep type/properties/items/required/enum, which is all our judge and
        generation schemas use.
        """
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                if k in {"additionalProperties", "strict"}:
                    continue
                out[k] = LLMClient._gemini_sanitize_schema(v)
            return out
        if isinstance(node, list):
            return [LLMClient._gemini_sanitize_schema(v) for v in node]
        return node

    def _call_gemini(self, system_prompt, user_prompt, schema, max_tokens) -> dict[str, Any]:
        from google.genai import types
        client = self._ensure_client()
        # Our schemas are wrapped as {"name","strict","schema":{...}}; Gemini
        # wants the inner object schema, sanitized.
        inner = schema.get("schema", schema)
        response_schema = self._gemini_sanitize_schema(inner)
        resp = client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        text = getattr(resp, "text", None)
        if text:
            start, end = text.find("{"), text.rfind("}") + 1
            if 0 <= start < end:
                parsed = json.loads(text[start:end])
                if isinstance(parsed, dict) and parsed:
                    return parsed
        # Fix A-7: empty/unparseable response. gemini-2.5-flash runs with thinking
        # by default; thinking tokens are drawn from max_output_tokens, so a long
        # evidence prompt can exhaust the budget and yield empty text. Surface the
        # diagnostics and, if truncated, raise a MAX_TOKENS-tagged error so the
        # retry loop can escalate max_tokens once.
        finish_reason = None
        thoughts = None
        try:
            cand = (resp.candidates or [None])[0]
            finish_reason = getattr(cand, "finish_reason", None)
            um = getattr(resp, "usage_metadata", None)
            thoughts = getattr(um, "thoughts_token_count", None) if um else None
        except Exception:
            pass
        log.warning("Gemini empty/unparseable response: finish_reason=%s thoughts_tokens=%s max_tokens=%s",
                    finish_reason, thoughts, max_tokens)
        if str(finish_reason).upper().endswith("MAX_TOKENS") or "MAX_TOKENS" in str(finish_reason).upper():
            raise ValueError(f"Gemini hit max_tokens (finish_reason={finish_reason}); response truncated")
        raise ValueError("Gemini did not return parseable JSON")

# ---------------------------------------------------------------------------
# Run metadata (fix B5/G5)
# ---------------------------------------------------------------------------

def build_run_metadata(**extra: Any) -> dict[str, Any]:
    meta = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "python": platform.python_version(),
        "embed_model": OPENAI_EMBED_MODEL,
        "vector_index": VECTOR_INDEX_NAME,
    }
    meta.update(extra)
    return meta


def write_run_metadata(out_dir: str | Path, name: str, meta: dict[str, Any]) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}_metadata.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

# ---------------------------------------------------------------------------
# Neo4j repository (read-only) + data-level cache
# ---------------------------------------------------------------------------

class Neo4jReadOnlyRepository:
    def __init__(self, uri: str, username: str, password: str, database: str,
                 vector_index_name: str, data_cache_dir: Optional[str] = None,
                 data_cache_max_age_hours: float = 720.0):
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self.vector_index_name = vector_index_name
        self.data_cache_dir = Path(data_cache_dir) if data_cache_dir else None
        self.data_cache_max_age_hours = data_cache_max_age_hours
        self._embed_client = None

    def close(self) -> None:
        self._driver.close()

    def _session(self):
        from neo4j import READ_ACCESS
        return self._driver.session(database=self.database, default_access_mode=READ_ACCESS)

    def _data_cache(self, kind: str, *key_parts: Any) -> tuple[Optional[Path], Any]:
        if self.data_cache_dir is None:
            return None, None
        path = self.data_cache_dir / f"{kind}_{_cache_key(kind, *key_parts)}.json"
        return path, _cache_load(path, self.data_cache_max_age_hours)

    @staticmethod
    def _best_text(props: dict[str, Any]) -> str:
        candidates = [
            props.get("title"), props.get("name"), props.get("desc"), props.get("description"),
            props.get("summary"), props.get("text"), props.get("body"), props.get("content"),
            props.get("role"),
        ]
        cleaned = [str(v).strip() for v in candidates if v not in (None, "")]
        return "\n".join(cleaned).strip()

    def get_target_node(self, target_id: str) -> TargetNode:
        path, cached = self._data_cache("target", target_id)
        if cached:
            return TargetNode(**cached)
        query = """
        MATCH (n {id:$target_id})
        RETURN labels(n) AS labels, properties(n) AS props
        LIMIT 1
        """
        with self._session() as session:
            rec = session.run(query, target_id=target_id).single()
        if not rec:
            raise ValueError(f"No such id in graph: {target_id}")
        labels = rec["labels"] or []
        props = rec["props"] or {}
        title = str(props.get("title") or props.get("name") or props.get("id") or target_id)
        body = self._best_text(props)
        target = TargetNode(node_id=target_id, labels=labels, title=title, body=body, props=props)
        if path is not None:
            _cache_save(path, asdict(target))
        return target

    def get_graph_evidence(self, target_id: str, max_hops: int = 2, limit: int = 40,
                           chunks_per_node: int = 3) -> list[EvidenceItem]:
        path, cached = self._data_cache("graph", target_id, max_hops, limit, chunks_per_node)
        if cached:
            return [EvidenceItem(**item) for item in cached]

        safe_max_hops = max(1, min(int(max_hops), 4))
        safe_chunk_cap = max(1, min(int(chunks_per_node), 8))
        query = f"""
        MATCH (target {{id:$target_id}})
        CALL (target) {{
            RETURN target AS node, 0 AS hops, [] AS rel_types
            UNION
            MATCH p=(target)-[:IN_DOC|DEFINED_IN|REFINES|CONFLICTS_WITH|AFFECTS|IMPLEMENTS|PARTIALLY_IMPLEMENTS|SUPERSEDES|VIOLATES_REQUIREMENT|HAS_COMMENT*1..{safe_max_hops}]-(node)
            WHERE NOT node:SrcChunk
            RETURN DISTINCT node AS node, length(p) AS hops, [rel IN relationships(p) | type(rel)] AS rel_types
        }}
        OPTIONAL MATCH (node)-[rel:IN_DOC]->(chunk:SrcChunk)
        OPTIONAL MATCH (chunk)-[:IN_DOC]->(doc:SrcDoc)
        WITH node, hops, rel_types,
             collect(DISTINCT {{
                chunk_id: chunk.id,
                text: chunk.text,
                doc_id: doc.id,
                doc_title: doc.title,
                doc_path: doc.path,
                link_props: properties(rel)
             }})[0..{safe_chunk_cap}] AS chunk_hits
        RETURN
            coalesce(node.id, '') AS source_id,
            labels(node) AS labels,
            properties(node) AS props,
            hops,
            rel_types,
            chunk_hits
        ORDER BY hops ASC, source_id ASC
        LIMIT $limit
        """
        evidence: list[EvidenceItem] = []
        seen_keys: set[tuple[str, str | None, str]] = set()
        with self._session() as session:
            rows = session.run(query, target_id=target_id, limit=max(limit * 3, 40)).data()

        for row in rows:
            props = row.get("props") or {}
            labels = row.get("labels") or []
            rel_types = row.get("rel_types") or []
            source_id = row.get("source_id") or ""
            source_type = labels[0] if labels else "Unknown"
            hops = int(row.get("hops") or 0)
            chunk_hits = row.get("chunk_hits") or []

            node_text = self._best_text(props)
            if node_text:
                key = (source_id, None, node_text)
                if key not in seen_keys:
                    seen_keys.add(key)
                    evidence.append(EvidenceItem(
                        source_id=source_id, source_type=source_type, relation_path=rel_types,
                        hops=hops, score=None, text=node_text, chunk_id=None,
                        metadata={"node_props": {k: v for k, v in props.items() if k != "embedding"}},
                    ))
            for chunk in chunk_hits:
                chunk_text = (chunk or {}).get("text") or ""
                chunk_id = (chunk or {}).get("chunk_id")
                if not chunk_text or not chunk_id:
                    continue
                key = (source_id, chunk_id, chunk_text)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                evidence.append(EvidenceItem(
                    source_id=source_id, source_type=f"{source_type}/SrcChunk",
                    relation_path=rel_types, hops=hops, score=None, text=chunk_text,
                    chunk_id=chunk_id,
                    metadata={
                        "doc_id": (chunk or {}).get("doc_id"),
                        "doc_title": (chunk or {}).get("doc_title"),
                        "doc_path": (chunk or {}).get("doc_path"),
                        "link_props": (chunk or {}).get("link_props") or {},
                    },
                ))

        evidence = evidence[: max(limit * 2, 40)]
        if path is not None:
            _cache_save(path, [asdict(item) for item in evidence])
        return evidence

    def get_vector_evidence(self, target: TargetNode, top_k: int = 40) -> list[EvidenceItem]:
        path, cached = self._data_cache("vector", target.node_id, top_k, OPENAI_EMBED_MODEL)
        if cached:
            return [EvidenceItem(**item) for item in cached]

        query_text = target.body or target.title or target.node_id
        if self._embed_client is None:
            from openai import OpenAI
            self._embed_client = OpenAI(api_key=OPENAI_API_KEY)
        embedding = self._embed_client.embeddings.create(
            model=OPENAI_EMBED_MODEL, input=query_text,
        ).data[0].embedding

        cypher = f"""
        CALL db.index.vector.queryNodes('{self.vector_index_name}', $top_k, $embedding)
        YIELD node, score
        OPTIONAL MATCH (node)-[:IN_DOC]->(doc:SrcDoc)
        RETURN
            coalesce(node.id, '') AS chunk_id,
            coalesce(node.text, '') AS text,
            score,
            doc.id AS doc_id,
            doc.title AS doc_title,
            doc.path AS doc_path
        """
        with self._session() as session:
            rows = session.run(cypher, top_k=top_k, embedding=embedding).data()

        evidence: list[EvidenceItem] = []
        seen: set[str] = set()
        for row in rows:
            chunk_id = row.get("chunk_id") or ""
            text = row.get("text") or ""
            score = float(row.get("score") or 0.0)
            if not chunk_id or not text:
                continue
            key = json.dumps({"chunk_id": chunk_id, "text": text}, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(EvidenceItem(
                source_id=chunk_id, source_type="SrcChunk",
                relation_path=["VECTOR_SIMILARITY"], hops=0, score=score, text=text,
                chunk_id=chunk_id,
                metadata={"doc_id": row.get("doc_id"), "doc_title": row.get("doc_title"),
                          "doc_path": row.get("doc_path")},
            ))
        if path is not None:
            _cache_save(path, [asdict(item) for item in evidence])
        return evidence

# ---------------------------------------------------------------------------
# Generation-side text heuristics (ported verbatim from 03_run_experiment.py)
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_keywords(target: TargetNode, max_keywords: int = 12) -> list[str]:
    raw = " ".join([
        target.node_id, target.title or "", target.body or "",
        " ".join(str(v) for v in target.props.values() if isinstance(v, (str, int, float))),
    ])
    words = normalize_text(raw).split()
    ordered: list[str] = []
    seen: set[str] = set()
    for word in words:
        if len(word) < 3 or word in GEN_STOPWORDS:
            continue
        if word not in seen:
            seen.add(word)
            ordered.append(word)
    if target.node_id.lower() not in seen:
        ordered.insert(0, target.node_id.lower())
    return ordered[:max_keywords]


def _doc_title(item: EvidenceItem) -> str:
    return str((item.metadata or {}).get("doc_title") or "")


def _doc_path(item: EvidenceItem) -> str:
    return str((item.metadata or {}).get("doc_path") or "")


def _extract_version_from_text(text: str) -> tuple[int, ...]:
    if not text:
        return ()
    candidates = []
    for m in re.finditer(r"\bv(?:ersion)?\s*([0-9]+(?:\.[0-9]+)*)\b", text, flags=re.IGNORECASE):
        candidates.append(tuple(int(p) for p in m.group(1).split(".")))
    return max(candidates, default=())


def _doc_family(item: EvidenceItem) -> str:
    source = _doc_title(item) or _doc_path(item)
    if not source:
        return ""
    base = Path(source).name.lower()
    base = re.sub(r"\.[a-z0-9]+$", "", base)
    base = re.sub(r"[-_ ]v[0-9]+(?:\.[0-9]+)*$", "", base)
    base = re.sub(r"[-_ ]version[ -]?[0-9]+(?:\.[0-9]+)*$", "", base)
    return base.strip()


def _cue_score(item: EvidenceItem) -> float:
    hay = " ".join([item.text or "", _doc_title(item), _doc_path(item)]).lower()
    score = 0.0
    for cue in CURRENT_CUES:
        if cue in hay:
            score += 8.0
    for cue in STALE_CUES:
        if cue in hay:
            score -= 12.0
    return score


def _family_version_adjustment(item: EvidenceItem, family_latest: dict[str, tuple[int, ...]]) -> float:
    family = _doc_family(item)
    if not family:
        return 0.0
    latest = family_latest.get(family, ())
    if not latest:
        return 0.0
    item_version = _extract_version_from_text(" ".join([_doc_title(item), _doc_path(item), item.text or ""]))
    if not item_version:
        return 0.0
    if item_version == latest:
        return 20.0
    if item_version < latest:
        return -25.0
    return 0.0


def build_family_latest_versions(items: list[EvidenceItem]) -> dict[str, tuple[int, ...]]:
    latest: dict[str, tuple[int, ...]] = {}
    for item in items:
        family = _doc_family(item)
        if not family:
            continue
        version = _extract_version_from_text(" ".join([_doc_title(item), _doc_path(item), item.text or ""]))
        if not version:
            continue
        if family not in latest or version > latest[family]:
            latest[family] = version
    return latest


def evidence_relevance_score(item: EvidenceItem, keywords: list[str], target_id: str,
                             family_latest: dict[str, tuple[int, ...]]) -> float:
    haystack = normalize_text(" ".join([
        item.source_id or "", item.source_type or "",
        " ".join(item.relation_path or []), item.text or "",
        _doc_title(item), _doc_path(item),
    ]))
    tokens = set(haystack.split())
    overlap = sum(1 for kw in keywords if kw in tokens)
    score = overlap * 10.0
    if item.source_id == target_id:
        score += 100.0
    if item.chunk_id and target_id.lower() in normalize_text(item.text):
        score += 20.0
    if item.hops == 0:
        score += 15.0
    elif item.hops == 1:
        score += 5.0
    else:
        score -= item.hops * 2.0
    if item.score is not None:
        score += min(max(item.score, 0.0), 1.0) * 10.0
    if "vector_similarity" in {r.lower() for r in item.relation_path}:
        score += 2.0
    score += _cue_score(item)
    score += _family_version_adjustment(item, family_latest)
    link_props = (item.metadata or {}).get("link_props") or {}
    composite = link_props.get("composite_score")
    if composite is not None:
        try:
            score += float(composite) * 5.0
        except Exception:
            pass
    return score


def deduplicate_evidence(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
    unique: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        key = json.dumps({
            "source_id": item.source_id, "chunk_id": item.chunk_id,
            "text": item.text, "relation_path": item.relation_path,
        }, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def focus_and_trim_evidence(evidence: list[EvidenceItem], target: TargetNode, limit: int,
                            min_items: int, require_direct_target_hit: bool = False,
                            drop_stale: bool = True) -> list[EvidenceItem]:
    """Graph-side filtering.

    Fix G2 (documentation + control): `drop_stale` makes the recency filter an
    explicit, logged experimental factor. When True (default, matching the
    original behavior), stale-cue CHUNKS are dropped; node-level texts are kept.
    """
    keywords = extract_keywords(target)
    token_keywords = set(keywords)
    family_latest = build_family_latest_versions(evidence)

    scored = sorted(
        evidence,
        key=lambda item: (
            evidence_relevance_score(item, keywords, target.node_id, family_latest),
            -(item.hops or 0),
            (item.score or 0.0),
        ),
        reverse=True,
    )
    filtered: list[EvidenceItem] = []
    seen_texts: set[str] = set()
    for item in scored:
        norm_text = normalize_text(item.text)
        if not norm_text or norm_text in seen_texts:
            continue
        token_set = set(norm_text.split())
        direct_match = item.source_id == target.node_id
        lexical_match = bool(token_set.intersection(token_keywords))
        vector_item = "VECTOR_SIMILARITY" in (item.relation_path or [])
        stale_penalty = _cue_score(item) <= -12.0 or _family_version_adjustment(item, family_latest) < 0.0
        if direct_match or lexical_match or vector_item:
            if drop_stale and stale_penalty and item.chunk_id:
                continue
            filtered.append(item)
            seen_texts.add(norm_text)
        if len(filtered) >= limit:
            break

    if require_direct_target_hit and not any(item.source_id == target.node_id for item in filtered):
        raise RuntimeError(f"No direct target hit left for {target.node_id} after focused filtering.")
    if len(filtered) < min_items:
        raise RuntimeError(f"Too few usable evidence items after filtering: {len(filtered)} < {min_items}.")
    return filtered[:limit]


def trim_vector_evidence(evidence: list[EvidenceItem], limit: int, min_items: int,
                         min_score: float = 0.0, drop_stale: bool = True) -> list[EvidenceItem]:
    family_latest = build_family_latest_versions(evidence)
    ranked = sorted(
        evidence,
        key=lambda item: (
            evidence_relevance_score(item, [], "", family_latest),
            (item.score or 0.0),
            len(item.text or ""),
        ),
        reverse=True,
    )
    filtered: list[EvidenceItem] = []
    seen_texts: set[str] = set()
    for item in ranked:
        if not item.text:
            continue
        if (item.score or 0.0) < min_score:
            continue
        if drop_stale and (_cue_score(item) <= -12.0 or _family_version_adjustment(item, family_latest) < 0.0):
            continue
        norm_text = " ".join((item.text or "").lower().split())
        if norm_text in seen_texts:
            continue
        seen_texts.add(norm_text)
        filtered.append(item)
        if len(filtered) >= limit:
            break
    if len(filtered) < min_items:
        raise RuntimeError(f"Too few usable vector evidence items: {len(filtered)} < {min_items}.")
    return filtered


def render_evidence(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "NO_EVIDENCE"
    lines: list[str] = []
    for idx, item in enumerate(evidence, start=1):
        rel_path = " > ".join(item.relation_path) if item.relation_path else "TARGET"
        score_part = f" score={item.score:.4f}" if item.score is not None else ""
        chunk_part = f" chunk={item.chunk_id}" if item.chunk_id else ""
        doc_title = _doc_title(item)
        doc_path = _doc_path(item)
        doc_part = f" doc={doc_title or doc_path}" if (doc_title or doc_path) else ""
        lines.append(
            f"[{idx}] source={item.source_id} type={item.source_type} hops={item.hops}"
            f"{score_part}{chunk_part}{doc_part} rel={rel_path}\n{item.text}"
        )
    return "\n\n".join(lines)

# ---------------------------------------------------------------------------
# Context resolution: bucketing, prompts, LLM call, heuristic post-processing
# (post-processing ported verbatim; heuristic INJECTIONS are now provenance-
# tracked — fix G1)
# ---------------------------------------------------------------------------

def classify_resolution_bucket(item: EvidenceItem, target: TargetNode) -> tuple[str, str]:
    rels = set(item.relation_path or [])
    if item.source_id == target.node_id and item.hops == 0:
        return "primary", "direct target evidence"
    if rels & PRIMARY_RELATIONS:
        return "primary", "explicit graph signal"
    if item.source_type.startswith("Implementation") or item.source_type.startswith("Specification"):
        return "primary", "implementation/specification context"
    if rels & CONTEXT_RELATIONS:
        return "context", "neighbor or similarity context"
    return "primary", "direct supporting evidence"


def partition_evidence_for_resolution(evidence: list[EvidenceItem], target: TargetNode,
                                      max_primary: int = 12, max_context: int = 8) -> list[ResolutionEvidenceEntry]:
    primary_items: list[tuple[EvidenceItem, str]] = []
    context_items: list[tuple[EvidenceItem, str]] = []
    for item in evidence:
        bucket, reason = classify_resolution_bucket(item, target)
        (primary_items if bucket == "primary" else context_items).append((item, reason))
    if not primary_items and context_items:
        primary_items.append(context_items.pop(0))
    selected: list[tuple[EvidenceItem, str, str]] = []
    for item, reason in primary_items[:max_primary]:
        selected.append((item, "primary", reason))
    for item, reason in context_items[:max_context]:
        selected.append((item, "context", reason))
    return [ResolutionEvidenceEntry(evidence_id=f"E{idx}", item=item, bucket=bucket, reason=reason)
            for idx, (item, bucket, reason) in enumerate(selected, start=1)]


def format_resolution_entries(entries: list[ResolutionEvidenceEntry], bucket: str, max_chars: int = 1200) -> str:
    blocks: list[str] = []
    filtered = [e for e in entries if e.bucket == bucket]
    if not filtered:
        return "- none"
    for entry in filtered:
        item = entry.item
        rel_path = " > ".join(item.relation_path) if item.relation_path else "TARGET"
        text = re.sub(r"\s+", " ", (item.text or "").strip())
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."
        parts = [
            f"[{entry.evidence_id}]", f"bucket: {entry.bucket}", f"bucket_reason: {entry.reason}",
            f"source_id: {item.source_id}", f"source_type: {item.source_type}",
            f"chunk_id: {item.chunk_id or ''}", f"hops: {item.hops}", f"relation_path: {rel_path}",
        ]
        if item.score is not None:
            parts.append(f"score: {item.score:.4f}")
        if _doc_title(item):
            parts.append(f"doc_title: {_doc_title(item)}")
        if _doc_path(item):
            parts.append(f"doc_path: {_doc_path(item)}")
        parts.append("text:")
        parts.append(text)
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def format_graph_hints(entries: list[ResolutionEvidenceEntry]) -> str:
    rel_counter: dict[str, int] = {}
    bucket_counter: dict[str, int] = {"primary": 0, "context": 0}
    for entry in entries:
        bucket_counter[entry.bucket] = bucket_counter.get(entry.bucket, 0) + 1
        for rel in entry.item.relation_path or []:
            rel_counter[rel] = rel_counter.get(rel, 0) + 1
    lines = [
        f"- primary_evidence_count: {bucket_counter.get('primary', 0)}",
        f"- context_evidence_count: {bucket_counter.get('context', 0)}",
    ]
    if rel_counter:
        priority = ["CONFLICTS_WITH", "SUPERSEDES", "OVERRIDES_FOR_CATEGORY", "USES_OBSOLETE_DATA_FROM",
                    "VIOLATES_REQUIREMENT", "PARTIALLY_IMPLEMENTS", "IMPLEMENTS", "DEFINED_IN",
                    "REFINES", "AFFECTS", "VECTOR_SIMILARITY"]
        ordered = sorted(rel_counter.items(),
                         key=lambda kv: (priority.index(kv[0]) if kv[0] in priority else 999, -kv[1], kv[0]))
        lines.extend(f"- {rel}: {count}" for rel, count in ordered)
    else:
        lines.append("- no_explicit_relation_hints")
    return "\n".join(lines)


RESOLVER_SYSTEM_PROMPT = (
    "You resolve requirement evidence into a compact operational context for downstream test generation. "
    "Do not generate tests. "
    "Use only the provided target, evidence, and graph hints. "
    "Prefer target-specific statements. "
    "Do not invent missing rules. "
    "PRIMARY evidence has much higher authority than CONTEXT evidence. "
    "CONTEXT evidence may provide neighboring scope, refinements, or semantically similar material, and it must not casually override the target's default truth. However, if multiple CONTEXT items consistently express the same target-relevant behavioral rule and no PRIMARY evidence contradicts it, you may promote that rule into operative_context. "
    "AFFECTS, REFINES, and VECTOR_SIMILARITY evidence should be treated as supporting context, not default truth, unless directly corroborated by target-specific PRIMARY evidence. "
    "If there is a likely default or current behavioral rule, put it into operative_context. Do not place provenance statements such as 'is defined in', 'is specified in', or 'is implemented by' into operative_context. "
    "If there is a scoped exception, category-specific behavior, or override, put it into exceptions. "
    "If there is conflicting, superseded, obsolete, violating, or invalid behavior that should not be treated as default truth, put it into conflicts_or_obsolete. "
    "If a rule depends on a matrix, category table, missing dependency, temporary workaround, unknown condition, or incomplete evidence, put that into gaps_or_uncertainties instead of promoting it to an operative rule. "
    "Each item must be short, atomic, and test-relevant. "
    "supporting_evidence_ids must contain only evidence ids in the form E<number>, such as E1 or E4. "
    "Return valid JSON only."
)


def build_resolver_user_prompt(target: TargetNode, entries: list[ResolutionEvidenceEntry], mode: str) -> str:
    return f"""
TARGET_ID: {target.node_id}
TARGET_LABELS: {", ".join(target.labels)}
TARGET_TITLE: {target.title}
TARGET_BODY:
{target.body}

MODE: {mode}

GRAPH_HINTS:
{format_graph_hints(entries)}

PRIMARY_EVIDENCE:
{format_resolution_entries(entries, bucket="primary")}

CONTEXT_EVIDENCE:
{format_resolution_entries(entries, bucket="context")}

Return JSON with this exact schema:
{{
  "operative_context": [],
  "exceptions": [],
  "conflicts_or_obsolete": [],
  "gaps_or_uncertainties": [],
  "supporting_evidence_ids": [],
  "notes": ""
}}
"""


def _is_meta_or_provenance_statement(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return True
    return any(re.search(pattern, s) for pattern in META_PROVENANCE_PATTERNS)


def _sentence_chunks(text: str) -> list[str]:
    raw = re.split(r"[\n\r]+|(?<=[\.!?;])\s+", text or "")
    out: list[str] = []
    for piece in raw:
        piece = re.sub(r"\s+", " ", piece).strip(" -•\t\r\n\"'")
        if len(piece) < 20:
            continue
        out.append(piece)
    return out


def _keyword_overlap_count(text: str, keywords: set[str]) -> int:
    toks = set(normalize_text(text).split())
    return sum(1 for kw in keywords if kw in toks)


def _looks_behavioral(text: str) -> bool:
    lowered = normalize_text(text)
    toks = set(lowered.split())
    if toks & BEHAVIOR_VERBS or toks & SPECIFIC_RULE_CUES:
        return True
    patterns = [
        r"\bstatus\b.*\bto\b", r"\btransitions?\b", r"\breturns?\b.*\bstate\b", r"\bshall\b",
        r"\bmust\b", r"\bshould\b", r"\bwhen\b.*\bupdate\b", r"\bround(?:ed|ing)?\b",
        r"\bdecimal\b", r"\bprecision\b", r"\bdisabled?\b", r"\benabled?\b", r"\bnon rent(?:able|al)\b",
    ]
    return any(re.search(p, lowered) for p in patterns)


def _is_too_abstract_operational_statement(text: str, target: TargetNode) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    norm = normalize_text(s)
    toks = set(norm.split())
    abstract_hits = sum(1 for cue in ABSTRACT_OPERATIVE_CUES if cue in norm)
    title_terms = {w for w in normalize_text(target.title).split() if len(w) >= 4 and w not in GEN_STOPWORDS}
    title_overlap = sum(1 for kw in title_terms if kw in toks)
    has_number = bool(re.search(r" \d+(?:\.\d+)? ", s))
    has_quoted_value = bool(re.search(r"[\"']([^\"']+)[\"']", s))
    has_condition = bool(re.search(r" (if|when|unless|until|before|after) ", norm))
    has_rule_cue = bool(toks & SPECIFIC_RULE_CUES)
    has_behavior_verb = bool(toks & BEHAVIOR_VERBS)
    specific = has_number or has_quoted_value or has_condition or has_rule_cue
    if re.search(r" (consistency|alignment) .* (across|between|throughout) ", norm):
        if not (has_number or has_quoted_value or has_condition):
            return True
    if re.search(r" (handle|manage|support|ensure) ", norm) and not specific and title_overlap <= 1:
        return True
    if abstract_hits >= 1 and not specific:
        return True
    if not has_behavior_verb and not specific and len(norm.split()) >= 7:
        return True
    if title_overlap == 0 and not specific and len(norm.split()) >= 7:
        return True
    return False


def _looks_like_json_fragment(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    if re.search(r'^[\{\}\[\],]+$', s):
        return True
    if re.search(r'^[A-Za-z_][A-Za-z0-9_ -]*"\s*:\s*"', s):
        return True
    if re.search(r'^"[A-Za-z_][A-Za-z0-9_ -]*"\s*:\s*"', s):
        return True
    if re.search(r'\b(summary|description|title|gherkin|rationale|test_cases|used_source_ids|used_context_items)"\s*:', s):
        return True
    return False


def _sanitize_item_text(text: str) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip()).strip(" ,;|\t\r\n")
    if not s or _looks_like_json_fragment(s):
        return ""
    s = re.sub(r'^"?[A-Za-z_][A-Za-z0-9_ -]*"?\s*:\s*', '', s).strip()
    if _looks_like_json_fragment(s):
        return ""
    return s


def _token_set(text: str) -> set[str]:
    return {t for t in normalize_text(text).split() if t}


def _is_redundant_statement(candidate: str, chosen: list[str]) -> bool:
    cand_toks = _token_set(candidate)
    if not cand_toks:
        return True
    for existing in chosen:
        ex_toks = _token_set(existing)
        if not ex_toks:
            continue
        inter = cand_toks & ex_toks
        union = cand_toks | ex_toks
        jacc = len(inter) / max(len(union), 1)
        containment = len(inter) / max(min(len(cand_toks), len(ex_toks)), 1)
        if jacc >= 0.72 or containment >= 0.90:
            return True
    return False


def _dedupe_statements(items: list[str]) -> list[str]:
    ordered = sorted(items, key=lambda s: (-len(_token_set(s)), -len(s), s))
    kept: list[str] = []
    for item in ordered:
        if not _is_redundant_statement(item, kept):
            kept.append(item)
    return kept


def _normalize_gap_statement(text: str) -> str:
    s = _sanitize_item_text(text)
    if not s:
        return ""
    norm = normalize_text(s)
    if norm.startswith('regardless of what the current srs') or 'emergency' in norm:
        return "A temporary or emergency override may affect the default behavior, but its exact scope is not fully specified in the retrieved evidence."
    if norm.startswith('2 5 2') or s.startswith('##'):
        return "Exact behavior depends on a category- or matrix-based rule that is not fully specified in the retrieved evidence."
    if any(cue in norm for cue in ('matrix', 'category', 'depends on', 'dependent on', 'configuration', 'lookup table', 'external table')):
        return "Exact behavior depends on a category- or matrix-based rule that is not fully specified in the retrieved evidence."
    if any(cue in norm for cue in ('temporary', 'workaround', 'override')):
        return "A temporary or exceptional condition may affect the default behavior, but its exact scope is not fully specified in the retrieved evidence."
    return ""


def _extract_target_focus_terms(target: TargetNode, entries: list[ResolutionEvidenceEntry]) -> set[str]:
    terms = set(extract_keywords(target, max_keywords=20))
    title_terms = [w for w in normalize_text(target.title).split() if len(w) >= 4 and w not in GEN_STOPWORDS]
    terms.update(title_terms)
    freq: dict[str, int] = {}
    for entry in entries:
        if entry.item.source_id != target.node_id:
            continue
        for tok in normalize_text(entry.item.text).split():
            if len(tok) < 4 or tok in GEN_STOPWORDS:
                continue
            freq[tok] = freq.get(tok, 0) + 1
    for tok, count in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:12]:
        if count >= 1:
            terms.add(tok)
    return terms


def _relevance_to_focus(text: str, focus_terms: set[str], title_terms: set[str]) -> tuple[int, int]:
    toks = set(normalize_text(text).split())
    return (sum(1 for kw in focus_terms if kw in toks), sum(1 for kw in title_terms if kw in toks))


def _passes_relevance_gate(text: str, focus_terms: set[str], title_terms: set[str], *,
                           bucket: str, require_behavior: bool = False, min_focus_overlap: int = 1) -> bool:
    if not text:
        return False
    focus_overlap, title_overlap = _relevance_to_focus(text, focus_terms, title_terms)
    norm = normalize_text(text)
    if require_behavior and not _looks_behavioral(text):
        return False
    if bucket == 'gap':
        return title_overlap >= 1 or focus_overlap >= max(2, min_focus_overlap + 1)
    if bucket in {'exception', 'conflict'}:
        return title_overlap >= 1 or focus_overlap >= max(1, min_focus_overlap)
    if bucket == 'context':
        return title_overlap >= 2 or focus_overlap >= max(2, min_focus_overlap + 1)
    if focus_overlap >= min_focus_overlap:
        return True
    return title_overlap >= 1 and any(tok in norm for tok in title_terms)


def _collect_evidence_grounded_candidates(entries: list[ResolutionEvidenceEntry], target: TargetNode,
                                          cue_set: set[str], require_behavior: bool = False,
                                          max_items: int = 2) -> list[dict[str, Any]]:
    focus_terms = _extract_target_focus_terms(target, entries)
    title_terms = {w for w in normalize_text(target.title).split() if len(w) >= 4 and w not in GEN_STOPWORDS}
    candidates: dict[str, dict[str, Any]] = {}
    for entry in entries:
        rels = set(entry.item.relation_path or [])
        for sent in _sentence_chunks(entry.item.text or ""):
            sent = _sanitize_item_text(sent)
            sent_norm = normalize_text(sent)
            if not sent_norm or _is_meta_or_provenance_statement(sent):
                continue
            if require_behavior and not _looks_behavioral(sent):
                continue
            cue_hits = [cue for cue in cue_set if cue in sent_norm]
            if not cue_hits:
                continue
            if not _passes_relevance_gate(sent, focus_terms, title_terms, bucket=entry.bucket,
                                          require_behavior=require_behavior, min_focus_overlap=1):
                continue
            score = _keyword_overlap_count(sent, focus_terms) + len(cue_hits)
            score += 3 if entry.bucket == "primary" else 1
            if rels & {"CONFLICTS_WITH", "SUPERSEDES", "USES_OBSOLETE_DATA_FROM", "VIOLATES_REQUIREMENT", "OVERRIDES_FOR_CATEGORY"}:
                score += 2
            item = candidates.setdefault(sent_norm, {"text": sent.strip(), "score": 0, "evidence_ids": [], "bucket": entry.bucket})
            item["score"] += score
            if entry.evidence_id not in item["evidence_ids"]:
                item["evidence_ids"].append(entry.evidence_id)
    ordered = sorted(candidates.values(), key=lambda d: (d["score"], len(d["evidence_ids"])), reverse=True)
    return ordered[:max_items]


def _extract_behavior_candidates(entries: list[ResolutionEvidenceEntry], target: TargetNode) -> list[dict[str, Any]]:
    focus_terms = _extract_target_focus_terms(target, entries)
    title_terms = {w for w in normalize_text(target.title).split() if len(w) >= 4 and w not in GEN_STOPWORDS}
    candidates: dict[str, dict[str, Any]] = {}
    for entry in entries:
        base_weight = 2 if entry.bucket == "primary" else 1
        rels = set(entry.item.relation_path or [])
        if rels & {"AFFECTS", "REFINES", "VECTOR_SIMILARITY"}:
            base_weight = min(base_weight, 1)
        for sent in _sentence_chunks(entry.item.text or ""):
            sent = _sanitize_item_text(sent)
            if not sent or _is_meta_or_provenance_statement(sent) or not _looks_behavioral(sent):
                continue
            if not _passes_relevance_gate(sent, focus_terms, title_terms, bucket=entry.bucket,
                                          require_behavior=True, min_focus_overlap=1):
                continue
            if entry.bucket == 'context':
                focus_overlap, title_overlap = _relevance_to_focus(sent, focus_terms, title_terms)
                if title_overlap < 2 and focus_overlap < 2:
                    continue
            key = normalize_text(sent)
            item = candidates.setdefault(key, {
                "text": sent.strip(), "score": 0, "primary_count": 0, "context_count": 0, "evidence_ids": [],
            })
            item["score"] += base_weight + _keyword_overlap_count(sent, focus_terms)
            if entry.bucket == "primary":
                item["primary_count"] += 1
            else:
                item["context_count"] += 1
            if entry.evidence_id not in item["evidence_ids"]:
                item["evidence_ids"].append(entry.evidence_id)
    return sorted(candidates.values(), key=lambda d: (d["score"], d["primary_count"], len(d["evidence_ids"])), reverse=True)


def _promote_behavior_candidates(ctx: ResolvedContext, entries: list[ResolutionEvidenceEntry], target: TargetNode) -> None:
    candidates = _extract_behavior_candidates(entries, target)
    if not candidates:
        return
    existing_norm = {normalize_text(x) for x in ctx.operative_context}
    for cand in candidates:
        text = _sanitize_item_text(cand["text"])
        if not text:
            continue
        norm = normalize_text(text)
        if norm in existing_norm or _is_too_abstract_operational_statement(text, target):
            continue
        if cand["primary_count"] >= 1 or cand["context_count"] >= 2 or len(cand["evidence_ids"]) >= 2:
            ctx.operative_context.append(text)
            ctx.injected["operative_context"].append(text)  # provenance (fix G1)
            existing_norm.add(norm)
            for eid in cand["evidence_ids"][:3]:
                if eid not in ctx.supporting_evidence_ids:
                    ctx.supporting_evidence_ids.append(eid)
            break


def _primary_fallback_operatives(entries: list[ResolutionEvidenceEntry], target: TargetNode,
                                 max_items: int = 2) -> list[dict[str, Any]]:
    primary_entries = [e for e in entries if e.bucket == 'primary']
    return _extract_behavior_candidates(primary_entries, target)[:max_items]

def postprocess_resolved_context(ctx: ResolvedContext, entries: list[ResolutionEvidenceEntry],
                                 target: TargetNode) -> ResolvedContext:
    """Deterministic post-processing of the LLM's resolved context.

    IMPORTANT (fix G1): every statement ADDED here (rather than filtered) is a
    heuristic injection, not an LLM output. All injections are recorded in
    ctx.injected[<bucket>] so that reconstructed-context statistics (paper
    Table 3) can be split into llm-produced vs. heuristic-injected counts.
    Vector-mode evidence carries no graph relations, therefore relation-based
    fallbacks can only fire in graph/hybrid mode — reporting the split is what
    makes the cross-mode comparison honest.
    """
    valid_ids = {entry.evidence_id for entry in entries}
    ctx.supporting_evidence_ids = [eid for eid in ctx.supporting_evidence_ids
                                   if re.fullmatch(r"E\d+", eid) and eid in valid_ids]

    def sanitize_bucket(items: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = _sanitize_item_text(item)
            if not text:
                continue
            norm = normalize_text(text)
            if norm in seen:
                continue
            seen.add(norm)
            cleaned.append(text)
        return cleaned

    ctx.operative_context = sanitize_bucket(ctx.operative_context)
    ctx.exceptions = sanitize_bucket(ctx.exceptions)
    ctx.conflicts_or_obsolete = sanitize_bucket(ctx.conflicts_or_obsolete)
    ctx.gaps_or_uncertainties = sanitize_bucket(ctx.gaps_or_uncertainties)

    focus_terms = _extract_target_focus_terms(target, entries)
    title_terms = {w for w in normalize_text(target.title).split() if len(w) >= 4 and w not in GEN_STOPWORDS}

    moved_meta: list[str] = []
    moved_abstract: list[str] = []
    filtered_operative: list[str] = []
    for item in ctx.operative_context:
        if _is_meta_or_provenance_statement(item):
            moved_meta.append(item)
            continue
        if not _passes_relevance_gate(item, focus_terms, title_terms, bucket='primary',
                                      require_behavior=True, min_focus_overlap=1):
            moved_abstract.append(item)
            continue
        if _is_too_abstract_operational_statement(item, target):
            moved_abstract.append(item)
            continue
        filtered_operative.append(item)
    ctx.operative_context = _dedupe_statements(filtered_operative)

    def filter_bucket(items: list[str], bucket: str, require_behavior: bool = False) -> list[str]:
        out: list[str] = []
        for item in items:
            text = item
            if bucket == 'gap':
                text = _normalize_gap_statement(item)
                if not text:
                    continue
            if not _passes_relevance_gate(text, focus_terms, title_terms, bucket=bucket,
                                          require_behavior=require_behavior, min_focus_overlap=1):
                continue
            if _is_redundant_statement(text, out):
                continue
            out.append(text)
        return out

    ctx.exceptions = filter_bucket(ctx.exceptions, 'exception')
    ctx.conflicts_or_obsolete = filter_bucket(ctx.conflicts_or_obsolete, 'conflict')
    ctx.gaps_or_uncertainties = filter_bucket(ctx.gaps_or_uncertainties, 'gap')

    rels = {rel for entry in entries for rel in (entry.item.relation_path or [])}

    def add_injected(bucket_list: list[str], bucket_name: str, value: str) -> None:
        value = _sanitize_item_text(value)
        if value and not _is_redundant_statement(value, bucket_list):
            bucket_list.append(value)
            ctx.injected[bucket_name].append(value)  # provenance (fix G1)

    exception_candidates = _collect_evidence_grounded_candidates(entries, target, EXCEPTION_CUES, max_items=2)
    gap_candidates = _collect_evidence_grounded_candidates(entries, target, GAP_CUES, max_items=2)
    conflict_candidates = _collect_evidence_grounded_candidates(entries, target, CONFLICT_CUES, max_items=2)

    has_exception_signal = bool(rels & {"OVERRIDES_FOR_CATEGORY"}) or bool(exception_candidates)
    has_gap_signal = bool(gap_candidates)
    has_conflict_signal = bool(rels & {"CONFLICTS_WITH", "SUPERSEDES", "USES_OBSOLETE_DATA_FROM",
                                       "VIOLATES_REQUIREMENT"}) or bool(conflict_candidates)

    if has_exception_signal and not ctx.exceptions:
        if exception_candidates:
            for cand in exception_candidates:
                add_injected(ctx.exceptions, "exceptions", cand["text"])
                for eid in cand["evidence_ids"]:
                    if eid not in ctx.supporting_evidence_ids:
                        ctx.supporting_evidence_ids.append(eid)
        elif rels & {"OVERRIDES_FOR_CATEGORY"}:
            add_injected(ctx.exceptions, "exceptions",
                         "A scoped or category-specific exception exists and should be tested separately from the default path.")

    if has_gap_signal and not ctx.gaps_or_uncertainties:
        for cand in gap_candidates:
            norm_gap = _normalize_gap_statement(cand["text"])
            if not norm_gap:
                continue
            add_injected(ctx.gaps_or_uncertainties, "gaps_or_uncertainties", norm_gap)
            for eid in cand["evidence_ids"]:
                if eid not in ctx.supporting_evidence_ids:
                    ctx.supporting_evidence_ids.append(eid)

    if has_conflict_signal and not ctx.conflicts_or_obsolete:
        if conflict_candidates:
            for cand in conflict_candidates:
                add_injected(ctx.conflicts_or_obsolete, "conflicts_or_obsolete", cand["text"])
                for eid in cand["evidence_ids"]:
                    if eid not in ctx.supporting_evidence_ids:
                        ctx.supporting_evidence_ids.append(eid)
        else:
            if rels & {"CONFLICTS_WITH", "VIOLATES_REQUIREMENT"}:
                add_injected(ctx.conflicts_or_obsolete, "conflicts_or_obsolete",
                             "Retrieved evidence includes conflicting or requirement-violating behavior that must not be treated as the default truth.")
            elif rels & {"SUPERSEDES", "USES_OBSOLETE_DATA_FROM"}:
                add_injected(ctx.conflicts_or_obsolete, "conflicts_or_obsolete",
                             "Retrieved evidence includes superseded or obsolete behavior that must not be treated as the current default truth.")

    if not ctx.operative_context or moved_abstract:
        _promote_behavior_candidates(ctx, entries, target)

    if not ctx.operative_context:
        for cand in _primary_fallback_operatives(entries, target, max_items=2):
            text = _sanitize_item_text(cand['text'])
            if not text or _is_too_abstract_operational_statement(text, target):
                continue
            if not _passes_relevance_gate(text, focus_terms, title_terms, bucket='primary',
                                          require_behavior=True, min_focus_overlap=1):
                continue
            if not _is_redundant_statement(text, ctx.operative_context):
                ctx.operative_context.append(text)
                ctx.injected["operative_context"].append(text)  # provenance (fix G1)
            for eid in cand['evidence_ids'][:3]:
                if eid not in ctx.supporting_evidence_ids:
                    ctx.supporting_evidence_ids.append(eid)
            if len(ctx.operative_context) >= 2:
                break

    if not ctx.operative_context and moved_meta:
        add_injected(ctx.gaps_or_uncertainties, "gaps_or_uncertainties",
                     "The available evidence is mostly provenance or implementation metadata and does not fully state the target's operative behavior.")

    ctx.operative_context = _dedupe_statements(
        [x for x in sanitize_bucket(ctx.operative_context) if not _is_too_abstract_operational_statement(x, target)])
    ctx.exceptions = filter_bucket(sanitize_bucket(ctx.exceptions), 'exception')
    ctx.conflicts_or_obsolete = filter_bucket(sanitize_bucket(ctx.conflicts_or_obsolete), 'conflict')
    ctx.gaps_or_uncertainties = filter_bucket(sanitize_bucket(ctx.gaps_or_uncertainties), 'gap')

    # keep provenance lists consistent with what survived the final filters
    for bucket_name, final_items in (
        ("operative_context", ctx.operative_context),
        ("exceptions", ctx.exceptions),
        ("conflicts_or_obsolete", ctx.conflicts_or_obsolete),
        ("gaps_or_uncertainties", ctx.gaps_or_uncertainties),
    ):
        final_norms = {normalize_text(x) for x in final_items}
        ctx.injected[bucket_name] = [x for x in ctx.injected[bucket_name] if normalize_text(x) in final_norms]

    if moved_meta:
        ctx.notes = (ctx.notes + " Filtered provenance/meta statements from operative_context: " +
                     " | ".join(moved_meta[:3])).strip()
    if moved_abstract:
        ctx.notes = (ctx.notes + " Filtered abstract or low-relevance operative statements: " +
                     " | ".join(moved_abstract[:3])).strip()

    if not ctx.supporting_evidence_ids and entries:
        ctx.supporting_evidence_ids = [entry.evidence_id for entry in entries[: min(3, len(entries))]]
    return ctx


def parse_resolved_context(payload: dict[str, Any], req_id: str, mode: str,
                           entries: list[ResolutionEvidenceEntry], target: TargetNode) -> ResolvedContext:
    def clean_list(name: str) -> list[str]:
        raw = payload.get(name, [])
        if not isinstance(raw, list):
            return []
        cleaned: list[str] = []
        for value in raw:
            text = str(value).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    ctx = ResolvedContext(
        req_id=req_id, mode=mode,
        operative_context=clean_list("operative_context"),
        exceptions=clean_list("exceptions"),
        conflicts_or_obsolete=clean_list("conflicts_or_obsolete"),
        gaps_or_uncertainties=clean_list("gaps_or_uncertainties"),
        supporting_evidence_ids=clean_list("supporting_evidence_ids"),
        notes=str(payload.get("notes", "") or "").strip(),
    )
    return postprocess_resolved_context(ctx, entries, target)


def format_resolved_context(ctx: ResolvedContext) -> str:
    def block(title: str, items: list[str]) -> str:
        if not items:
            return f"{title}:\n- none"
        return f"{title}:\n" + "\n".join(f"- {item}" for item in items)
    return "\n\n".join([
        block("Operative context", ctx.operative_context),
        block("Exceptions", ctx.exceptions),
        block("Conflicts or obsolete", ctx.conflicts_or_obsolete),
        block("Gaps or uncertainties", ctx.gaps_or_uncertainties),
        f"Supporting evidence ids:\n- {' | '.join(ctx.supporting_evidence_ids) if ctx.supporting_evidence_ids else 'none'}",
        f"Notes:\n- {ctx.notes or 'none'}",
    ])

# ---------------------------------------------------------------------------
# Generation (pipeline variants for the ablation study — RQ3)
#   full          : retrieval -> LLM resolution (+heuristics) -> generation
#   no_resolution : retrieval -> generation from RAW evidence (ablation A1)
#   no_retrieval  : generation from the target text only     (ablation A0)
# ---------------------------------------------------------------------------

GENERATOR_SYSTEM_PROMPT_FULL = (
    "You generate executable, target-specific Gherkin tests from a resolved operational context. "
    "Use the resolved context as the primary source of truth. "
    "Do not generate default tests from anything listed under conflicts_or_obsolete. "
    "If exceptions are listed, generate separate exception-focused tests when appropriate. "
    "If gaps or uncertainties are listed, avoid unsupported detail and overclaiming. "
    "The main subject of every test must remain the target requirement. "
    "Return valid JSON only."
)

GENERATOR_SYSTEM_PROMPT_RAW = (
    "You generate executable, target-specific Gherkin tests for a software requirement. "
    "Use the provided evidence as the source of truth. Prefer the most recent and authoritative "
    "information when evidence items conflict. "
    "The main subject of every test must remain the target requirement. "
    "Return valid JSON only."
)

GENERATOR_SYSTEM_PROMPT_TARGET_ONLY = (
    "You generate executable, target-specific Gherkin tests for a software requirement, "
    "based only on the requirement text itself. Do not invent domain rules that are not implied "
    "by the requirement. Return valid JSON only."
)


def build_generator_prompts(target: TargetNode, num_tests: int, mode: str, pipeline: str,
                            resolved: Optional[ResolvedContext] = None,
                            evidence: Optional[list[EvidenceItem]] = None) -> tuple[str, str]:
    if pipeline == "full":
        system_prompt = GENERATOR_SYSTEM_PROMPT_FULL
        context_block = f"RESOLVED_CONTEXT:\n{format_resolved_context(resolved)}"
    elif pipeline == "no_resolution":
        system_prompt = GENERATOR_SYSTEM_PROMPT_RAW
        # The no_resolution ablation feeds RAW evidence (no distillation). Cap
        # the character size so the prompt stays comparable to the full
        # pipeline's resolved-context size; an unbounded 50k+ char dump makes
        # the model return null/empty test_cases. This is a length cap only, not
        # a content filter — the ablation still sees raw, unresolved evidence.
        raw_ev = render_evidence(evidence or [])
        if len(raw_ev) > RAW_EVIDENCE_CHAR_CAP:
            raw_ev = raw_ev[:RAW_EVIDENCE_CHAR_CAP] + "\n[... raw evidence truncated ...]"
        context_block = f"RAW_EVIDENCE:\n{raw_ev}"
    elif pipeline == "no_retrieval":
        system_prompt = GENERATOR_SYSTEM_PROMPT_TARGET_ONLY
        context_block = "CONTEXT:\n- target requirement text only (no retrieval performed)"
    else:
        raise ValueError(f"Unknown pipeline variant: {pipeline}")

    user_prompt = f"""
TARGET_ID: {target.node_id}
TARGET_LABELS: {", ".join(target.labels)}
TARGET_TITLE: {target.title}
TARGET_BODY:
{target.body}

MODE: {mode}
PIPELINE: {pipeline}
REQUESTED_TEST_COUNT: {num_tests}

{context_block}

Return JSON with:
- summary
- test_cases

Each test case must contain:
- title
- gherkin
- rationale
- used_context_items
- used_source_ids
"""
    return system_prompt, user_prompt


def resolve_context(llm: LLMClient, target: TargetNode, evidence: list[EvidenceItem],
                    mode: str, repeat_index: int = 0) -> ResolvedContext:
    entries = partition_evidence_for_resolution(evidence=evidence, target=target)
    payload = llm.call_json(
        system_prompt=RESOLVER_SYSTEM_PROMPT,
        user_prompt=build_resolver_user_prompt(target, entries, mode),
        schema=RESOLUTION_SCHEMA,
        tool_name="return_resolved_context",
        repeat_index=repeat_index,
    )
    return parse_resolved_context(payload, req_id=target.node_id, mode=mode, entries=entries, target=target)


def generate_tests(llm: LLMClient, target: TargetNode, num_tests: int, mode: str, pipeline: str,
                   resolved: Optional[ResolvedContext] = None,
                   evidence: Optional[list[EvidenceItem]] = None,
                   repeat_index: int = 0) -> dict[str, Any]:
    system_prompt, user_prompt = build_generator_prompts(target, num_tests, mode, pipeline, resolved, evidence)

    def _valid_generation(p: dict[str, Any]) -> bool:
        # A generation is cacheable only if test_cases is a non-empty list with
        # at least one dict item. Blocks poisoning by string/None/empty results.
        tcs = p.get("test_cases")
        return isinstance(tcs, list) and any(isinstance(x, dict) for x in tcs)

    payload = llm.call_json(
        system_prompt=system_prompt, user_prompt=user_prompt,
        schema=GENERATION_FROM_CONTEXT_SCHEMA, tool_name="return_gherkin_generation",
        repeat_index=repeat_index, cache_validator=_valid_generation,
    )
    raw_cases = payload.get("test_cases", []) or []
    # Robustness: the model (or a stale cache entry from before these guards)
    # can return test_cases as something OTHER than a list of objects — e.g. a
    # bare string. Iterating a string would yield one "item" per character
    # (the 14306-malformed symptom), so normalize first: only a real list of
    # dicts is acceptable; anything else collapses to empty and is handled by
    # the empty-generation guard downstream (raise -> retryable, never saved).
    if not isinstance(raw_cases, list):
        log.warning("test_cases was %s, not a list, for %s/%s/%s r%d — treating as empty",
                    type(raw_cases).__name__, target.node_id, mode, pipeline, repeat_index)
        raw_cases = []
    good_cases = [tc for tc in raw_cases if isinstance(tc, dict)]
    dropped = len(raw_cases) - len(good_cases)
    if dropped:
        log.warning("Dropped %d malformed (non-object) test case(s) for %s/%s/%s r%d",
                    dropped, target.node_id, mode, pipeline, repeat_index)
    return {"summary": payload.get("summary", ""),
            "test_cases": good_cases[:num_tests]}

# ---------------------------------------------------------------------------
# Run persistence (fix G5/B5): every row carries model/provider/pipeline/
# repeatIndex/promptVersion; exact generation-time evidence is persisted and
# is the ONLY evidence evaluators are allowed to use (fix A7).
# ---------------------------------------------------------------------------

RUN_CSV_FIELDS = [
    "runId", "reqId", "mode", "pipeline", "provider", "model", "repeatIndex", "promptVersion",
    "testId", "title", "gherkin", "rationale", "usedSourceIds", "usedContextItems",
    "evidenceSources", "targetTitle", "targetBody", "evidenceText", "generationSummary",
    "resolvedOperativeContext", "resolvedExceptions", "resolvedConflictsOrObsolete",
    "resolvedGapsOrUncertainties", "resolvedEvidenceIds", "resolutionNotes",
    "injectedOperativeCount", "injectedExceptionsCount", "injectedConflictsCount", "injectedGapsCount",
]


def model_slug(provider: str, model: str) -> str:
    """Short, filename-safe identifier for a provider/model.

    Puts the model into the output filename so a file is self-identifying even
    if it is moved out of its run directory. Examples:
      openai   / gpt-4o-mini               -> "openai-gpt-4o-mini"
      anthropic/ claude-haiku-4-5-20251001 -> "anthropic-claude-haiku-4-5"
      gemini   / gemini-2.5-flash          -> "gemini-gemini-2.5-flash"
    A trailing all-digit date segment (e.g. -20251001) is dropped for brevity;
    the exact model string is still recorded in the `model` CSV column.
    """
    m = re.sub(r"-\d{6,}$", "", model)          # drop trailing date stamp
    raw = f"{provider}-{m}"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")
    return slug or "model"


def save_generated_run(out_dir: str, target: TargetNode, mode: str, pipeline: str,
                       provider: str, model: str, repeat_index: int,
                       generation: dict[str, Any], evidence: list[EvidenceItem],
                       resolved: Optional[ResolvedContext], run_params: dict[str, Any]) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]
    stem = f"{run_id}_{target.node_id}_{model_slug(provider, model)}_{mode}_{pipeline}_r{repeat_index}"
    path = Path(out_dir) / f"{stem}.csv"
    evidence_sources = "|".join(sorted({item.source_id for item in evidence if item.source_id}))
    evidence_text = render_evidence(evidence)

    res = resolved or ResolvedContext(req_id=target.node_id, mode=mode)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_CSV_FIELDS)
        writer.writeheader()
        for idx, tc in enumerate(generation.get("test_cases", []), start=1):
            writer.writerow({
                "runId": run_id,
                "reqId": target.node_id,
                "mode": mode,
                "pipeline": pipeline,
                "provider": provider,
                "model": model,
                "repeatIndex": repeat_index,
                "promptVersion": PROMPT_VERSION,
                "testId": f"{target.node_id}_{idx}",
                "title": tc.get("title", ""),
                "gherkin": tc.get("gherkin", ""),
                "rationale": tc.get("rationale", ""),
                "usedSourceIds": "|".join(tc.get("used_source_ids", [])),
                "usedContextItems": "|".join(tc.get("used_context_items", [])),
                "evidenceSources": evidence_sources,
                "targetTitle": target.title,
                "targetBody": target.body,
                "evidenceText": evidence_text,
                "generationSummary": generation.get("summary", ""),
                "resolvedOperativeContext": " || ".join(res.operative_context),
                "resolvedExceptions": " || ".join(res.exceptions),
                "resolvedConflictsOrObsolete": " || ".join(res.conflicts_or_obsolete),
                "resolvedGapsOrUncertainties": " || ".join(res.gaps_or_uncertainties),
                "resolvedEvidenceIds": "|".join(res.supporting_evidence_ids),
                "resolutionNotes": res.notes,
                "injectedOperativeCount": len(res.injected["operative_context"]),
                "injectedExceptionsCount": len(res.injected["exceptions"]),
                "injectedConflictsCount": len(res.injected["conflicts_or_obsolete"]),
                "injectedGapsCount": len(res.injected["gaps_or_uncertainties"]),
            })

    resolution_entries = partition_evidence_for_resolution(evidence=evidence, target=target) if evidence else []
    json_path = Path(out_dir) / f"{stem}_resolved.json"
    json_path.write_text(json.dumps({
        "req_id": res.req_id, "mode": mode, "pipeline": pipeline,
        "provider": provider, "model": model, "repeat_index": repeat_index,
        "prompt_version": PROMPT_VERSION, "pipeline_version": PIPELINE_VERSION,
        "run_params": run_params,
        "operative_context": res.operative_context,
        "exceptions": res.exceptions,
        "conflicts_or_obsolete": res.conflicts_or_obsolete,
        "gaps_or_uncertainties": res.gaps_or_uncertainties,
        "injected": res.injected,
        "supporting_evidence_ids": res.supporting_evidence_ids,
        "notes": res.notes,
        "evidence_preview": [
            {"evidence_id": e.evidence_id, "bucket": e.bucket, "bucket_reason": e.reason,
             "source_id": e.item.source_id, "chunk_id": e.item.chunk_id,
             "source_type": e.item.source_type, "relation_path": e.item.relation_path}
            for e in resolution_entries
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)

# ---------------------------------------------------------------------------
# Retrieval orchestration (symmetric parameters across modes — fix G2)
# ---------------------------------------------------------------------------

def retrieve_evidence(repo: Neo4jReadOnlyRepository, target: TargetNode, mode: str, *,
                      max_hops: int, limit: int, chunks_per_node: int, top_k: int,
                      min_evidence_items: int, min_vector_score: float,
                      hybrid_multiplier: float = 1.5, drop_stale: bool = True) -> list[EvidenceItem]:
    """Unified retrieval for all three modes.

    Fix G2: `min_vector_score` and `drop_stale` now apply IDENTICALLY to the
    standalone vector mode and to the vector branch of hybrid mode (previously
    hybrid hard-coded min_score=0.15 while vector used 0.0). All values are
    logged in run metadata.
    """
    if mode == "graph":
        raw = repo.get_graph_evidence(target_id=target.node_id, max_hops=max_hops,
                                      limit=limit, chunks_per_node=chunks_per_node)
        return focus_and_trim_evidence(raw, target=target, limit=limit,
                                       min_items=min_evidence_items,
                                       require_direct_target_hit=True, drop_stale=drop_stale)
    if mode == "vector":
        raw = repo.get_vector_evidence(target, top_k=max(top_k, limit))
        return trim_vector_evidence(raw, limit=limit, min_items=min_evidence_items,
                                    min_score=min_vector_score, drop_stale=drop_stale)
    if mode == "hybrid":
        graph_items = repo.get_graph_evidence(target_id=target.node_id, max_hops=max_hops,
                                              limit=limit, chunks_per_node=chunks_per_node)
        graph_evidence = focus_and_trim_evidence(graph_items, target=target, limit=limit,
                                                 min_items=max(1, min(min_evidence_items, 2)),
                                                 require_direct_target_hit=True, drop_stale=drop_stale)
        vector_items = repo.get_vector_evidence(target, top_k=max(top_k, limit))
        vector_evidence = trim_vector_evidence(vector_items, limit=limit, min_items=1,
                                               min_score=min_vector_score, drop_stale=drop_stale)
        evidence = deduplicate_evidence(graph_evidence + vector_evidence)[: int(limit * hybrid_multiplier)]
        if len(evidence) < min_evidence_items:
            raise RuntimeError(f"Too few combined evidence items: {len(evidence)} < {min_evidence_items}.")
        return evidence
    raise ValueError(f"Unknown mode: {mode}")


def run_generation_for_target(*, provider: str, model: str, target_id: str, mode: str,
                              pipeline: str, num_tests: int, top_k: int, max_hops: int,
                              limit: int, chunks_per_node: int, min_evidence_items: int,
                              min_vector_score: float, out_dir: str, repeat_index: int,
                              llm_cache_dir: Optional[str], data_cache_dir: Optional[str],
                              database: str, vector_index_name: str,
                              drop_stale: bool = True) -> dict[str, Any]:
    """Single entry point used by both the GPT and the Claude wrapper."""
    llm = LLMClient(provider=provider, model=model, cache_dir=llm_cache_dir)
    repo = Neo4jReadOnlyRepository(
        uri=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD,
        database=database, vector_index_name=vector_index_name,
        data_cache_dir=data_cache_dir,
    )
    run_params = {
        "mode": mode, "pipeline": pipeline, "num_tests": num_tests, "top_k": top_k,
        "max_hops": max_hops, "limit": limit, "chunks_per_node": chunks_per_node,
        "min_evidence_items": min_evidence_items, "min_vector_score": min_vector_score,
        "drop_stale": drop_stale, "repeat_index": repeat_index,
    }
    try:
        target = repo.get_target_node(target_id)

        evidence: list[EvidenceItem] = []
        resolved: Optional[ResolvedContext] = None

        if pipeline != "no_retrieval":
            evidence = retrieve_evidence(
                repo, target, mode,
                max_hops=max_hops, limit=limit, chunks_per_node=chunks_per_node,
                top_k=top_k, min_evidence_items=min_evidence_items,
                min_vector_score=min_vector_score, drop_stale=drop_stale,
            )
        if pipeline == "full":
            resolved = resolve_context(llm, target, evidence, mode, repeat_index=repeat_index)

        generation = generate_tests(llm, target, num_tests, mode, pipeline,
                                    resolved=resolved, evidence=evidence,
                                    repeat_index=repeat_index)

        # Guard (fix): never persist an empty run. If the model returned zero
        # test cases (valid-but-empty JSON, or a degenerate response), that is a
        # FAILURE, not a completed cell — otherwise a header-only CSV would look
        # done, inflate the cell count, and feed empty rows to the evaluators.
        # Raising here routes it through runall's fault handling (logged, retryable)
        # and, because the failed call is not cached, a re-run will retry it.
        n_tests = len(generation.get("test_cases", []))
        if n_tests == 0:
            raise RuntimeError(
                f"Empty generation for {target_id}/{mode}/{pipeline} r{repeat_index}: "
                f"model returned 0 test cases; not saving a header-only file."
            )

        saved_path = save_generated_run(
            out_dir=out_dir, target=target, mode=mode, pipeline=pipeline,
            provider=provider, model=model, repeat_index=repeat_index,
            generation=generation, evidence=evidence, resolved=resolved,
            run_params=run_params,
        )
        meta = build_run_metadata(provider=provider, model=model, target_id=target_id, **run_params)
        write_run_metadata(out_dir, Path(saved_path).stem, meta)

        res = resolved or ResolvedContext(req_id=target_id, mode=mode)
        return {
            "saved_run": saved_path,
            "tests_generated": len(generation.get("test_cases", [])),
            "evidence_items": len(evidence),
            "resolved_operatives": len(res.operative_context),
            "resolved_operatives_injected": len(res.injected["operative_context"]),
            "resolved_exceptions": len(res.exceptions),
            "resolved_exceptions_injected": len(res.injected["exceptions"]),
            "resolved_conflicts_or_obsolete": len(res.conflicts_or_obsolete),
            "resolved_conflicts_injected": len(res.injected["conflicts_or_obsolete"]),
            "resolved_gaps": len(res.gaps_or_uncertainties),
            "resolved_gaps_injected": len(res.injected["gaps_or_uncertainties"]),
        }
    finally:
        repo.close()


def add_generation_args(parser) -> None:
    parser.add_argument("--target-id", required=True, help="e.g. R1, R25, R70")
    parser.add_argument("--mode", choices=["graph", "vector", "hybrid"], default="hybrid")
    parser.add_argument("--pipeline", choices=["full", "no_resolution", "no_retrieval"], default="full",
                        help="full = retrieval+resolution+generation; no_resolution = raw-evidence ablation (A1); no_retrieval = target-only baseline (A0)")
    parser.add_argument("--num-tests", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--max-hops", type=int, default=2)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--chunks-per-node", type=int, default=3)
    parser.add_argument("--min-evidence-items", type=int, default=2)
    parser.add_argument("--min-vector-score", type=float, default=0.0,
                        help="Applied identically in vector mode and in the vector branch of hybrid mode (fix G2).")
    parser.add_argument("--keep-stale", action="store_true",
                        help="Disable the heuristic recency filter (makes stale-filtering an experimental factor).")
    parser.add_argument("--repeat-index", type=int, default=0,
                        help="Distinguishes intentional repeats in the LLM response cache. MUST differ across repeats.")
    parser.add_argument("--database", default=NEO4J_DATABASE)
    parser.add_argument("--vector-index-name", default=VECTOR_INDEX_NAME)
    parser.add_argument("--llm-cache-dir", default=DEFAULT_LLM_CACHE_DIR,
                        help="Response-level LLM cache. Empty string disables it.")
    parser.add_argument("--data-cache-dir", default=DEFAULT_DATA_CACHE_DIR,
                        help="Neo4j/embedding data cache. Empty string disables it.")


def generation_main(provider: str, default_model: str, default_out_dir: str) -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description=f"Gherkin generation ({provider}) — graph/vector/hybrid retrieval with pipeline ablations.")
    add_generation_args(parser)
    parser.add_argument("--model", default=default_model)
    parser.add_argument("--out-dir", default=default_out_dir)
    args = parser.parse_args()

    result = run_generation_for_target(
        provider=provider, model=args.model, target_id=args.target_id, mode=args.mode,
        pipeline=args.pipeline, num_tests=args.num_tests, top_k=args.top_k,
        max_hops=args.max_hops, limit=args.limit, chunks_per_node=args.chunks_per_node,
        min_evidence_items=args.min_evidence_items, min_vector_score=args.min_vector_score,
        out_dir=args.out_dir, repeat_index=args.repeat_index,
        llm_cache_dir=args.llm_cache_dir or None, data_cache_dir=args.data_cache_dir or None,
        database=args.database, vector_index_name=args.vector_index_name,
        drop_stale=not args.keep_stale,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# Subjective evaluation (LLM judge)
#   * ONE judge configuration for ALL generator outputs (fix A2). The wrapper
#     scripts only set defaults; cross-model comparisons are valid only when
#     the SAME judge (provider+model) scored every row — the script warns if
#     rows from multiple generator models are judged, and stamps the judge
#     identity on every output row.
#   * Evidence comes EXCLUSIVELY from the persisted evidenceText column of the
#     run CSVs (fix A7). No live rehydration.
#   * overall_score is computed deterministically in code as the mean of the
#     six sub-scores (fix B2).
#   * Failed judge calls are recorded with evalStatus=failed and EXCLUDED from
#     all aggregates (fix A4).
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = (
    "You are an expert QA Evaluator specializing in complex, FRAGMENTED software architectures. "
    "Your job is to evaluate whether a generated Gherkin test effectively tests the target requirement "
    "while intelligently integrating fragmented business rules (like conflicts, exceptions, gaps, or cross-module impacts) "
    "found in the supporting evidence.\n"
    "In a highly fragmented system, a naive \"happy path\" test is weak. A robust test incorporates valid constraints "
    "from neighboring components. Do NOT penalize a test for being complex or touching other modules IF that "
    "complexity is firmly grounded in the provided evidence. "
    "Return only the requested JSON."
)


# The judge sees the FULL persisted evidence (fix A7 + validity): it must ground
# its scores in the same complete, raw evidence the generator saw, NOT in the
# system's own distilled resolution — otherwise coverage/grounding would be
# circular (measuring fidelity to our pipeline's output rather than to the
# actual fragmented requirement). The resolved context is included only as a
# SUPPLEMENTARY signal of what the system extracted, never as a replacement.
# Set JUDGE_EVIDENCE_CHAR_BUDGET=0 to keep full evidence (default); a positive
# value truncates and is NOT recommended for the reported results.
JUDGE_EVIDENCE_CHAR_BUDGET = int(os.environ.get("JUDGE_EVIDENCE_CHAR_BUDGET", "0"))
# Length cap (characters) for RAW evidence in the no_resolution ablation. This
# is a size guard, not a content filter: it keeps the prompt comparable to the
# full pipeline so the model reliably returns structured test_cases. Generous
# by default (the ablation is meant to see more raw context than `full`).
RAW_EVIDENCE_CHAR_CAP = int(os.environ.get("RAW_EVIDENCE_CHAR_CAP", "12000"))


def _compose_resolved_block(row: dict[str, Any]) -> str:
    """Assemble the resolved-context block from the persisted CSV columns."""
    parts = []
    for label, col in (("OPERATIVE_RULES", "resolvedOperativeContext"),
                       ("EXCEPTIONS", "resolvedExceptions"),
                       ("CONFLICTS_OR_OBSOLETE", "resolvedConflictsOrObsolete"),
                       ("GAPS_OR_UNCERTAINTIES", "resolvedGapsOrUncertainties")):
        val = (row.get(col, "") or "").strip()
        if val:
            parts.append(f"{label}:\n{val}")
    return "\n\n".join(parts) if parts else "NONE_EXTRACTED"


def build_judge_user_prompt(row: dict[str, Any]) -> str:
    # FULL raw evidence is the ground truth the judge scores against (default).
    raw = row.get("evidenceText", "") or "NO_PERSISTED_EVIDENCE"
    if JUDGE_EVIDENCE_CHAR_BUDGET > 0 and len(raw) > JUDGE_EVIDENCE_CHAR_BUDGET:
        raw = raw[:JUDGE_EVIDENCE_CHAR_BUDGET] + "\n[... evidence truncated ...]"
    # Supplementary: what the system distilled (for transparency, NOT ground truth).
    resolved_block = _compose_resolved_block(row)
    return f"""
TARGET_REQUIREMENT_ID: {row.get('reqId', '')}
TARGET_TITLE: {row.get('targetTitle', '')}
TARGET_BODY:
{row.get('targetBody', '')}

TEST_TITLE: {row.get('title', '')}
GHERKIN:
{row.get('gherkin', '')}

EVIDENCE (full, persisted at generation time — THIS is the ground truth to score against):
{raw}

SYSTEM_EXTRACTED_CONTEXT (what the pipeline distilled; supplementary only, do NOT treat as ground truth — judge against the EVIDENCE above):
{resolved_block}

SCORING_RULES (each dimension is 1-5; anchors at 1/3/5):
- requirement_alignment: 5 = the test verifies the specific behavior of the target requirement (integrating valid cross-module impacts, e.g. AFFECTS/CONFLICTS_WITH, still counts as 5); 3 = related to the target but verifies only a peripheral aspect; 1 = mentions the target at most nominally while testing something else.
- target_specificity: 5 = uses exact constraints, parameters and edge-cases from the target or its evidence; 3 = some concrete details but key parameters generic; 1 = placeholder-level, interchangeable steps.
- evidence_grounding: 5 = every business rule in the test is supported by the EVIDENCE; 3 = core rule supported but details invented; 1 = logic not traceable to the evidence.
- executability: 5 = every step concrete and observable; 3 = mostly concrete with some vague steps; 1 = abstract, unmeasurable steps.
- gherkin_quality: 5 = valid, well-formed Given/When/Then; 3 = structural weaknesses (missing When, compound steps); 1 = not valid Gherkin.
- coverage: 5 ONLY if the test covers the target comprehensively, INCLUDING the hidden edge-cases and fragmented rules present anywhere in the evidence; reserve 5 for genuinely exhaustive tests; a solid but partial test is 3-4; 1 = covers a single trivial path.

GENERIC_TEST_RULE:
- If the test is a naive "happy path" that completely ignores specific constraints or conflicts clearly visible in the evidence, set is_generic=true and lower the relevant sub-scores.

FRAGMENTATION_INTEGRATION_VS_DRIFT_RULE (CRITICAL):
- The ontology is highly fragmented. If the test logic includes another feature (e.g., Billing, Maintenance, Notifications) BECAUSE the evidence shows an 'AFFECTS', 'CONFLICTS_WITH', 'IDENTIFIES_GAP_IN' or exception rule linking them to the target, this is EXCELLENT ("Fragmentation Integration"). DO NOT mark as drift_detected.
- Set drift_detected=true ONLY if the test completely abandons TARGET_REQUIREMENT_ID to test an unrelated feature with no justified link in the evidence.

OUTPUT_RULE:
- Return JSON with exactly these fields: requirement_alignment, target_specificity, evidence_grounding, executability, gherkin_quality, coverage, is_generic, drift_detected, strengths, weaknesses, reasoning.
- Each of the six score fields MUST be an integer from 1 to 5. is_generic and drift_detected MUST be booleans.
- Keep strengths and weaknesses to ONE short sentence each. Give reasoning as 1-2 short sentences (max ~40 words) — it is the qualitative audit trail for later human validation, so keep it informative, but do not repeat the numeric scores in prose.
"""


def load_run_rows(pattern: str) -> list[dict[str, Any]]:
    import glob
    clean = pattern.strip('"').strip("'")
    files = sorted(glob.glob(clean))
    if not files:
        raise SystemExit(f"No files match pattern: {clean}")
    rows: list[dict[str, Any]] = []
    for fp in files:
        base = os.path.basename(fp).lower()
        if not fp.endswith(".csv") or "summary" in base or "metadata" in base:
            continue
        with open(fp, "r", encoding="utf-8", newline="") as fin:
            rows.extend(list(csv.DictReader(fin)))
    if not rows:
        raise SystemExit("Input CSV files were empty or summary-only.")
    return rows


def judge_rows(rows: list[dict[str, Any]], judge: LLMClient, repeat_index: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        record = dict(row)
        record["judgeProvider"] = judge.provider
        record["judgeModel"] = judge.model
        record["judgePromptVersion"] = PROMPT_VERSION
        try:
            result = judge.call_json(
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_prompt=build_judge_user_prompt(row),
                schema=JUDGE_SCHEMA,
                tool_name="return_gherkin_evaluation",
                repeat_index=repeat_index,
                cache_validator=valid_judgement,
            )
            # Fix A-1: reject malformed judgements instead of silently averaging
            # zeros. An invalid payload routes into the except-branch -> failed.
            if not valid_judgement(result):
                raise ValueError("invalid judge payload (sub-scores not all int 1..5)")
            for fld in JUDGE_SUBSCORE_FIELDS + ["is_generic", "drift_detected", "strengths", "weaknesses", "reasoning"]:
                record[fld] = result.get(fld)
            # Validator guarantees each sub-score is an int in 1..5 — no `or 0`.
            subs = [int(result[f]) for f in JUDGE_SUBSCORE_FIELDS]
            record["overall_score"] = round(sum(subs) / len(subs), 4)  # deterministic composite (fix B2)
            record["evalStatus"] = "ok"
        except Exception as exc:
            log.error("Judge failed on row %d (%s/%s): %s", i, row.get("reqId"), row.get("testId"), exc)
            for fld in JUDGE_SUBSCORE_FIELDS + ["is_generic", "drift_detected", "strengths", "weaknesses"]:
                record[fld] = ""
            record["reasoning"] = f"evaluation_failed: {exc}"
            record["overall_score"] = ""
            record["evalStatus"] = "failed"  # excluded from aggregates (fix A4)
        out.append(record)
    return out


def summarize_judged(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import math
    from collections import defaultdict
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    n_failed = 0
    for row in results:
        if row.get("evalStatus") != "ok":
            n_failed += 1
            continue
        key = (row.get("model", "unknown"), row.get("mode", "unknown"), row.get("pipeline", "full"))
        groups[key].append(row)
    if n_failed:
        log.warning("%d rows had evalStatus=failed and are EXCLUDED from the summary.", n_failed)

    metric_fields = JUDGE_SUBSCORE_FIELDS + ["overall_score"]
    summary_rows: list[dict[str, Any]] = []
    for (model, mode, pipeline), rows in sorted(groups.items()):
        n = len(rows)
        summary: dict[str, Any] = {"model": model, "mode": mode, "pipeline": pipeline,
                                   "n": n, "n_failed_global": n_failed}
        for fld in metric_fields:
            vals = [float(r[fld]) for r in rows if r.get(fld) not in (None, "")]
            avg = sum(vals) / len(vals) if vals else 0.0
            if len(vals) > 1:
                std = math.sqrt(sum((x - avg) ** 2 for x in vals) / (len(vals) - 1))
                se = std / math.sqrt(len(vals))
            else:
                std, se = 0.0, 0.0
            summary[f"{fld}_avg"] = round(avg, 4)
            summary[f"{fld}_sd"] = round(std, 4)
            summary[f"{fld}_se"] = round(se, 4)
        generic = sum(1 for r in rows if str(r.get("is_generic", "")).lower() == "true")
        drift = sum(1 for r in rows if str(r.get("drift_detected", "")).lower() == "true")
        summary["generic_rate"] = round(generic / n, 4) if n else 0.0
        summary["drift_rate"] = round(drift / n, 4) if n else 0.0
        summary_rows.append(summary)
    return summary_rows


def judge_main(default_judge_provider: str, default_judge_model: str) -> None:
    """Subjective LLM-judge evaluation over persisted run CSVs.

    Crash recovery (B-1): the detail CSV is written at the end, but every judge
    call is disk-cached, so re-running with the SAME parameters after a crash is
    a near-free cache-hit for already-judged rows — only un-judged rows call the
    API. A full re-run only costs money when PROMPT_VERSION changes.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="LLM-judge evaluation over persisted run CSVs (no live rehydration).")
    parser.add_argument("--input", required=True, help="e.g. runs/*.csv")
    parser.add_argument("--out-dir", default=DEFAULT_EVAL_DIR)
    parser.add_argument("--judge-provider", choices=["openai", "anthropic", "gemini"], default=default_judge_provider)
    parser.add_argument("--judge-model", default=default_judge_model)
    # NOTE: two easily-confused flags with OPPOSITE meanings —
    #   --judge-repeat  shifts the JUDGE cache key (for intra-rater re-scoring);
    #   --filter-repeat filters GENERATOR rows by their repeatIndex column.
    # Naming them distinctly + explicit help prevents a costly mix-up at the
    # intra-rater step (using --filter-repeat there would freshly judge the
    # generator's r1 rows instead of re-scoring, wasting ~$9 and producing no
    # reliability data).
    parser.add_argument("--judge-repeat", "--repeat-index", type=int, default=0, dest="judge_repeat",
                        help="Judge-side cache-key offset for intra-rater RE-SCORING; NOT a row filter. "
                             "Use >0 to force a fresh second judgement of already-judged rows.")
    parser.add_argument("--llm-cache-dir", default=DEFAULT_LLM_CACHE_DIR)
    # Fix A-5: row-level filters + dry-run to prevent expensive misfires.
    parser.add_argument("--filter-repeat", type=int, default=None,
                        help="ROW FILTER: keep only generator rows whose repeatIndex equals this value "
                             "(this is NOT the judge re-score flag; see --judge-repeat).")
    parser.add_argument("--filter-req", default=None,
                        help="Comma-separated reqId list to keep.")
    parser.add_argument("--filter-mode", default=None,
                        help="Comma-separated modes to keep, e.g. 'vector,graph'.")
    parser.add_argument("--filter-pipeline", default=None,
                        help="Comma-separated pipelines to keep, e.g. 'full,no_resolution'.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print filtered row count, cell breakdown and cost estimate; no API calls.")
    parser.add_argument("--cost-per-test", type=float, default=0.0076,
                        help="USD per judged test, for the dry-run estimate.")
    args = parser.parse_args()

    rows = load_run_rows(args.input)

    # Fix A-5: apply row-level filters on the persisted CSV columns.
    def _keep(r: dict[str, Any]) -> bool:
        if args.filter_repeat is not None and str(r.get("repeatIndex", "")) != str(args.filter_repeat):
            return False
        if args.filter_req is not None and r.get("reqId", "") not in {x.strip() for x in args.filter_req.split(",")}:
            return False
        if args.filter_mode is not None and r.get("mode", "") not in {x.strip() for x in args.filter_mode.split(",")}:
            return False
        if args.filter_pipeline is not None and r.get("pipeline", "") not in {x.strip() for x in args.filter_pipeline.split(",")}:
            return False
        return True

    filters_active = any(x is not None for x in
                         (args.filter_repeat, args.filter_req, args.filter_mode, args.filter_pipeline))
    if filters_active:
        before = len(rows)
        rows = [r for r in rows if _keep(r)]
        log.info("Filters kept %d of %d rows.", len(rows), before)

    if not rows:
        raise SystemExit("No rows left after filtering; check --filter-* values.")

    # Fix A-5: dry-run — show the plan and cost, make NO API calls.
    if args.dry_run:
        from collections import Counter
        breakdown = Counter((r.get("model", "?"), r.get("mode", "?"),
                             r.get("pipeline", "?"), str(r.get("repeatIndex", "?"))) for r in rows)
        print("=" * 70)
        print(f"DRY RUN — {len(rows)} rows would be judged")
        print(f"Estimated cost: {len(rows)} x ${args.cost_per_test:.4f} = ${len(rows) * args.cost_per_test:.2f}")
        print("-" * 70)
        print(f"{'model':<26} {'mode':<8} {'pipeline':<16} {'rep':<4} {'n':>5}")
        for (model, mode, pipe, rep), n in sorted(breakdown.items()):
            print(f"{str(model)[:26]:<26} {mode:<8} {pipe:<16} {rep:<4} {n:>5}")
        print("=" * 70)
        raise SystemExit(0)

    generator_models = sorted({r.get("model", "unknown") for r in rows})
    if len(generator_models) > 1:
        log.warning(
            "Rows from MULTIPLE generator models detected (%s). For a valid cross-model comparison, "
            "the SAME judge (%s/%s) must score every row of every model — do not mix judge configurations.",
            generator_models, args.judge_provider, args.judge_model,
        )

    judge = LLMClient(provider=args.judge_provider, model=args.judge_model,
                      cache_dir=args.llm_cache_dir or None)
    results = judge_rows(rows, judge, repeat_index=args.judge_repeat)

    # Fix A-6: one automatic retry pass over failed rows (position-tracked so it
    # does not depend on testId uniqueness). ok rows are cache-hits anyway, but
    # here we only re-submit the failed subset.
    failed_idx = [i for i, r in enumerate(results) if r.get("evalStatus") != "ok"]
    if failed_idx:
        log.warning("Retrying %d failed row(s) once...", len(failed_idx))
        retry_rows = [rows[i] for i in failed_idx]
        retried = judge_rows(retry_rows, judge, repeat_index=args.judge_repeat)
        for pos, new in zip(failed_idx, retried):
            if new.get("evalStatus") == "ok":
                results[pos] = new
        still = sum(1 for r in results if r.get("evalStatus") != "ok")
        log.warning("After retry: %d row(s) still failed.", still)

    summary_rows = summarize_judged(results)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = re.sub(r"[^A-Za-z0-9_.-]+", "", args.input.replace("/", "_"))[:40] or "batch"
    detail_path = out / f"llm_eval_{tag}_{stamp}.csv"
    summary_path = out / f"llm_summary_{tag}_{stamp}.csv"

    with detail_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    if summary_rows:
        with summary_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    write_run_metadata(args.out_dir, detail_path.stem, build_run_metadata(
        judge_provider=args.judge_provider, judge_model=args.judge_model,
        input_pattern=args.input, rows_total=len(results),
        rows_failed=sum(1 for r in results if r.get("evalStatus") != "ok"),
        filter_repeat=args.filter_repeat, filter_req=args.filter_req,
        filter_mode=args.filter_mode, filter_pipeline=args.filter_pipeline,
    ))

    print("\n" + "=" * 100)
    print(f"{'LLM SUBJECTIVE EVALUATION SUMMARY (judge: ' + args.judge_provider + '/' + args.judge_model + ')':^100}")
    print("=" * 100)
    header = f"| {'Model':<22} | {'Mode':<7} | {'Pipe':<13} | {'N':<4} | {'Overall':<7} | {'Cov':<5} | {'Drift%':<6} |"
    print(header)
    print("-" * 100)
    for r in summary_rows:
        print(f"| {str(r['model'])[:22]:<22} | {r['mode']:<7} | {r['pipeline']:<13} | {r['n']:<4} "
              f"| {r['overall_score_avg']:>7.2f} | {r['coverage_avg']:>5.2f} | {r['drift_rate']*100:>5.1f}% |")
    print("=" * 100 + "\n")
    print(json.dumps({"detail_csv": str(detail_path), "summary_csv": str(summary_path),
                      "rows_evaluated": len(results)}, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# Objective (document-grounded) evaluation — model-agnostic, ONE implementation
# for all generator models (fix A3/G6).
#
# Changes vs. the original scripts, all disclosed:
#   * frag_bits uniformly include node 'name' (superset of both old variants).
#   * max_neighbor_hops default = 2, matching generation-time graph traversal
#     depth (fix A6 — evaluating 2-hop-generated content against a 1-hop
#     reference systematically penalized graph mode).
#   * support_score is the plain supported-term ratio. The previous
#     0.8/0.2 formula was mathematically identical to this ratio because no
#     neutral term class existed (fix A1); the paper text must be corrected
#     accordingly. unsupported_ratio is also reported explicitly.
#   * The canonical reference can be FROZEN: build once with
#     --export-reference, manually validate/correct the JSON, then evaluate
#     with --reference-json <file>. This turns the heuristic draft into the
#     paper's actual, human-validated Resolved Reference Set (fix A5).
#   * Coverage matching thresholds are CLI-configurable to enable the
#     sensitivity analysis (fix B1). Defaults reproduce the old behavior.
# ---------------------------------------------------------------------------

def obj_normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def obj_tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_\-']{3,}", (text or "").lower())
    out: list[str] = []
    for token in tokens:
        token = token.strip("'_- ")
        if not token or token in OBJ_STOPWORDS or token.isdigit():
            continue
        out.append(token)
    return out


def obj_line_is_heading(line: str) -> bool:
    s = line.strip()
    return s.startswith('#') or bool(re.match(r'^\d+(?:\.\d+)*\s+.+$', s)) or bool(re.match(r'^[A-Z0-9 _\-/]{6,}$', s))


def obj_line_is_bullet(line: str) -> bool:
    s = line.strip()
    return s.startswith(('-', '*', '+')) or bool(re.match(r'^\d+[\.)]\s+', s))


def obj_ngrams(tokens: list[str], n: int) -> list[str]:
    if len(tokens) < n:
        return []
    return [' '.join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def obj_unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        val = obj_normalize_ws(item)
        key = val.lower()
        if not val or key in seen:
            continue
        seen.add(key)
        out.append(val)
    return out


def obj_stemish(token: str) -> str:
    t = token.lower()
    for suffix in ('ing', 'tion', 'ions', 'ed', 'es', 's'):
        if t.endswith(suffix) and len(t) > len(suffix) + 3:
            t = t[:-len(suffix)]
            break
    return t[:6]


@dataclass
class ObjTargetContext:
    target_id: str
    target_label: str
    display_name: str
    description: str
    target_terms: list[str]
    context_terms: list[str]
    anchor_phrases: list[str]
    neighbor_texts: list[str]
    fragmentation_texts: list[str]


class GraphTargetResolver:
    def __init__(self, database: Optional[str] = None, max_neighbor_hops: int = 2):
        from neo4j import GraphDatabase
        uri, username, password = NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
        self.database = database or NEO4J_DATABASE
        # Fix A6: default 2 hops = generation-time traversal depth.
        self.max_neighbor_hops = max(1, min(int(max_neighbor_hops), 3))
        if not (uri and username and password):
            raise RuntimeError('Missing Neo4j env vars: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    def resolve(self, target_id: str) -> ObjTargetContext:
        from neo4j import READ_ACCESS
        with self.driver.session(database=self.database, default_access_mode=READ_ACCESS) as session:
            record = session.run(
                f"""
                MATCH (target {{id:$target_id}})
                OPTIONAL MATCH p=(target)-[*1..{self.max_neighbor_hops}]-(nbr)
                WHERE nbr <> target AND NOT nbr:SrcChunk
                WITH target, collect(DISTINCT {{
                    hops: length(p),
                    labels: labels(nbr),
                    props: properties(nbr),
                    rel_types: [rel IN relationships(p) | type(rel)]
                }})[0..60] AS neighbors
                RETURN labels(target) AS labels,
                       properties(target) AS props,
                       neighbors
                """,
                target_id=target_id,
            ).single()
        if not record:
            raise ValueError(f'Target not found in graph: {target_id}')

        props = record['props'] or {}
        labels = record['labels'] or []
        neighbors = record['neighbors'] or []

        display_name = obj_normalize_ws(
            props.get('name') or props.get('title') or props.get('desc') or props.get('description') or target_id)
        description = obj_normalize_ws(
            props.get('description') or props.get('desc') or props.get('summary') or display_name)

        target_terms: list[str] = []
        for phrase in [target_id, display_name, description]:
            target_terms.extend(obj_tokenize(phrase))

        expanded: list[str] = []
        for term in obj_unique_preserve(target_terms):
            expanded.append(term)
            if term in SYNONYM_MAP:
                expanded.extend(SYNONYM_MAP[term])
            for key, syns in SYNONYM_MAP.items():
                if term.startswith(key) or key.startswith(term):
                    expanded.extend(syns)
        target_terms = obj_unique_preserve(expanded)

        neighbor_texts: list[str] = []
        context_terms: list[str] = []
        fragmentation_texts: list[str] = []
        for neighbor in neighbors:
            nprops = neighbor.get('props') or {}
            hops = int(neighbor.get('hops') or 99)
            rel_types = set(neighbor.get('rel_types') or [])
            bits = [nprops.get('id'), nprops.get('name'), nprops.get('title'), nprops.get('role'),
                    nprops.get('desc'), nprops.get('description'), nprops.get('summary')]
            neighbor_phrase = obj_normalize_ws(' | '.join([str(b) for b in bits if obj_normalize_ws(str(b))]))
            if not neighbor_phrase:
                continue
            neighbor_texts.append(neighbor_phrase)
            if hops <= 1:
                context_terms.extend(obj_tokenize(neighbor_phrase))
            if rel_types.intersection(FRAGMENTATION_RELS):
                # Unified frag_bits (fix A3): 'name' is included for ALL models.
                frag_bits = [nprops.get('name'), nprops.get('title'), nprops.get('desc'),
                             nprops.get('description'), nprops.get('summary')]
                frag_text = obj_normalize_ws(' '.join([str(b) for b in frag_bits if b and obj_normalize_ws(str(b))]))
                if frag_text:
                    fragmentation_texts.append(frag_text)

        context_terms = obj_unique_preserve(context_terms)[:60]
        anchor_phrases = obj_unique_preserve(
            [display_name, description] +
            obj_ngrams(obj_tokenize(display_name), 2) +
            obj_ngrams(obj_tokenize(description), 2))[:30]

        return ObjTargetContext(
            target_id=target_id, target_label=(labels[0] if labels else 'Unknown'),
            display_name=display_name, description=description,
            target_terms=target_terms[:60], context_terms=context_terms,
            anchor_phrases=anchor_phrases, neighbor_texts=neighbor_texts[:30],
            fragmentation_texts=obj_unique_preserve(fragmentation_texts),
        )


class GraphAwareDocsExtractor:
    def __init__(self, docs_dir: str):
        self.docs_dir = Path(docs_dir)
        if not self.docs_dir.exists():
            raise FileNotFoundError(f'No such docs dir: {self.docs_dir}')

    def _iter_docs(self):
        for path in sorted(self.docs_dir.rglob('*')):
            if path.is_file() and path.suffix.lower() in {'.md', '.txt'}:
                yield path

    def _sections_from_file(self, path: Path) -> list[dict[str, Any]]:
        text = path.read_text(encoding='utf-8', errors='ignore')
        lines = text.splitlines()
        if not lines:
            return []
        sections: list[dict[str, Any]] = []
        current_heading = path.name
        buf: list[str] = []
        start_line = 1

        def flush(end_line: int):
            nonlocal buf, start_line, current_heading
            body = '\n'.join(buf).strip()
            if body:
                sections.append({'file': str(path), 'heading': current_heading,
                                 'start_line': start_line, 'end_line': end_line, 'text': body})

        for i, line in enumerate(lines, start=1):
            if obj_line_is_heading(line):
                flush(i - 1)
                current_heading = line.strip('# ').strip() or path.name
                buf = [line]
                start_line = i
            else:
                buf.append(line)
        flush(len(lines))

        if len(sections) <= 1:
            sections = []
            window, stride = 16, 8
            for start in range(0, len(lines), stride):
                chunk = lines[start:start + window]
                if not any(obj_normalize_ws(x) for x in chunk):
                    continue
                sections.append({'file': str(path), 'heading': path.name,
                                 'start_line': start + 1, 'end_line': min(len(lines), start + window),
                                 'text': '\n'.join(chunk).strip()})
        return sections

    def _score_section(self, section: dict[str, Any], ctx: ObjTargetContext) -> tuple[float, list[str]]:
        heading = obj_normalize_ws(section['heading'])
        text = obj_normalize_ws(section['text'])
        lowered = f'{heading}\n{text}'.lower()
        text_tokens = set(obj_tokenize(lowered))
        score, reasons = 0.0, []
        if re.search(rf'\b{re.escape(ctx.target_id)}\b', lowered, re.IGNORECASE):
            score += 50.0
            reasons.append('exact_target_id')
        if ctx.display_name and ctx.display_name.lower() in lowered:
            score += 35.0
            reasons.append('exact_display_name')
        exact_anchor_hits = 0
        for phrase in ctx.anchor_phrases:
            p = phrase.lower()
            if len(p) >= 6 and p in lowered:
                exact_anchor_hits += 1
        if exact_anchor_hits:
            score += min(20.0, exact_anchor_hits * 6.0)
            reasons.append(f'exact_anchor_hits:{exact_anchor_hits}')
        target_overlap = text_tokens.intersection({t.lower() for t in ctx.target_terms})
        if target_overlap:
            score += min(40.0, len(target_overlap) * 4.0)
            reasons.append(f'target_overlap:{len(target_overlap)}')
        context_overlap = text_tokens.intersection({t.lower() for t in ctx.context_terms})
        if context_overlap:
            score += min(10.0, len(context_overlap) * 1.0)
            reasons.append(f'context_overlap:{len(context_overlap)}')
        requirement_lines = 0
        targetish_lines = 0
        for line in section['text'].splitlines():
            s = line.strip()
            if re.search(r'\b(shall|must|required|prevent|allow|update|transition|status)\b', s, re.IGNORECASE):
                requirement_lines += 1
            if len(set(obj_tokenize(s)).intersection({t.lower() for t in ctx.target_terms})) >= 2:
                targetish_lines += 1
        if requirement_lines:
            score += min(10.0, requirement_lines * 1.2)
            reasons.append(f'requirement_lines:{requirement_lines}')
        if targetish_lines:
            score += min(10.0, targetish_lines * 2.0)
            reasons.append(f'targetish_lines:{targetish_lines}')
        return score, reasons

    def extract(self, ctx: ObjTargetContext) -> dict[str, Any]:
        scored_sections: list[dict[str, Any]] = []
        for path in self._iter_docs():
            for section in self._sections_from_file(path):
                score, reasons = self._score_section(section, ctx)
                if score < 8.0:
                    continue
                scored_sections.append({**section, 'score': round(score, 4), 'match_reasons': reasons})
        scored_sections.sort(key=lambda x: (-x['score'], x['file'], x['start_line']))
        top_hits = scored_sections[:12]

        evidence_text = '\n\n'.join(hit['text'] for hit in top_hits)
        bullet_lines: list[str] = []
        for hit in top_hits[:8]:
            for line in hit['text'].splitlines():
                s = line.strip()
                if not s:
                    continue
                line_tokens = set(obj_tokenize(s))
                target_overlap = len(line_tokens.intersection({t.lower() for t in ctx.target_terms}))
                if obj_line_is_bullet(s) or re.search(r'\b(shall|must|required|prevent|allow|update|transition|status)\b', s, re.IGNORECASE):
                    if target_overlap >= 1 or ctx.display_name.lower() in s.lower():
                        bullet_lines.append(s)

        from collections import Counter
        keyword_counter = Counter(obj_tokenize(evidence_text))
        top_keywords = [k for k, _ in keyword_counter.most_common(50)]
        canonical_points = obj_unique_preserve(bullet_lines + ctx.fragmentation_texts)[:30]
        frag_tokens: list[str] = []
        for ft in ctx.fragmentation_texts:
            frag_tokens.extend(obj_tokenize(ft))
        source_vocab = set(top_keywords + obj_tokenize(evidence_text) +
                           [t.lower() for t in ctx.target_terms] + frag_tokens)
        return {
            'target_id': ctx.target_id,
            'resolved_target': asdict(ctx),
            'hits': top_hits,
            'top_keywords': top_keywords,
            'canonical_points': canonical_points,
            'source_vocab': sorted(source_vocab),
            'source_text': evidence_text,
            'reference_status': 'heuristic_draft',  # becomes 'human_validated' after manual review
        }

class SourceGroundedEvaluator:
    """Objective, document-grounded scorer.

    coverage_score : matched canonical points / total canonical points
    support_score  : supported unique test terms / total unique test terms
                     (the old 0.8/0.2 composite reduced to exactly this value
                      because no neutral class existed — fix A1; the values are
                      numerically unchanged, only the description is honest now)
    objective_score: 0.55*coverage + 0.45*support (weights configurable;
                     report a weight sensitivity analysis in the paper)
    """

    def __init__(self, profile_by_req: dict[str, dict[str, Any]], *,
                 match_min_ratio: float = 0.25, match_min_tokens: int = 2,
                 pass_min_coverage: float = 0.15, pass_min_support: float = 0.50,
                 w_coverage: float = 0.55, w_support: float = 0.45):
        self.profile_by_req = profile_by_req
        self.match_min_ratio = match_min_ratio
        self.match_min_tokens = match_min_tokens
        self.pass_min_coverage = pass_min_coverage
        self.pass_min_support = pass_min_support
        self.w_coverage = w_coverage
        self.w_support = w_support

    @staticmethod
    def _clean_test_tokens(title: str, gherkin: str) -> list[str]:
        text = re.sub(r'\b(Given|When|Then|And|But|Scenario|Feature)\b', ' ',
                      f'{title}\n{gherkin}', flags=re.IGNORECASE)
        return [t for t in obj_tokenize(text) if len(t) >= 4]

    def _token_match_ratio(self, a_tokens: set[str], b_tokens: set[str]) -> float:
        if not a_tokens:
            return 0.0
        b_stems = {obj_stemish(t) for t in b_tokens}
        matched = sum(1 for token in a_tokens if token in b_tokens or obj_stemish(token) in b_stems)
        return matched / len(a_tokens)

    def _line_coverage(self, gherkin: str, canonical_points: list[str]) -> tuple[int, int]:
        if not canonical_points:
            return 0, 0
        test_tokens = set(self._clean_test_tokens('', gherkin))
        matched = 0
        for point in canonical_points:
            point_tokens = set(obj_tokenize(point))
            if not point_tokens:
                continue
            ratio = self._token_match_ratio(point_tokens, test_tokens)
            if ratio >= self.match_min_ratio or (len(point_tokens.intersection(test_tokens)) >= self.match_min_tokens):
                matched += 1
        return matched, len(canonical_points)

    def _support_breakdown(self, title: str, gherkin: str, source_vocab: set[str],
                           target_terms: set[str]) -> tuple[float, float, list[str]]:
        test_terms = self._clean_test_tokens(title, gherkin)
        if not test_terms:
            return 0.0, 0.0, []
        allowed = set(source_vocab) | set(target_terms)
        allowed_stems = {obj_stemish(t) for t in allowed}
        unsupported: list[str] = []
        supported = 0
        for term in sorted(set(test_terms)):
            if term in allowed or obj_stemish(term) in allowed_stems:
                supported += 1
            else:
                unsupported.append(term)
        total_unique = max(1, len(set(test_terms)))
        supported_ratio = supported / total_unique
        unsupported_ratio = len(unsupported) / total_unique
        return round(supported_ratio, 4), round(unsupported_ratio, 4), unsupported[:20]

    def evaluate_row(self, row: dict[str, str]) -> dict[str, Any]:
        req_id = (row.get('reqId') or row.get('target_id') or '').strip()
        profile = self.profile_by_req.get(req_id)
        if not profile:
            return {**row, 'source_hits': 0, 'resolved_target_name': '',
                    'coverage_score': None, 'support_score': None, 'unsupported_ratio': None,
                    'objective_score': None, 'objective_pass': 0, 'objective_notes': 'no_source_match',
                    'referenceStatus': 'missing'}
        canonical_points = profile['canonical_points']
        source_vocab = set(profile['source_vocab'])
        target_terms = set((profile.get('resolved_target') or {}).get('target_terms') or [])

        matched_points, total_points = self._line_coverage(row.get('gherkin', ''), canonical_points)
        coverage_score = round((matched_points / total_points), 4) if total_points else 0.0
        support_score, unsupported_ratio, unsupported = self._support_breakdown(
            row.get('title', ''), row.get('gherkin', ''), source_vocab, target_terms)
        objective_score = round(self.w_coverage * coverage_score + self.w_support * support_score, 4)
        objective_pass = 1 if (coverage_score >= self.pass_min_coverage and
                               support_score >= self.pass_min_support) else 0
        return {
            **row,
            'source_hits': len(profile.get('hits', [])),
            'resolved_target_name': ((profile.get('resolved_target') or {}).get('display_name')) or '',
            'matched_points': matched_points,
            'total_points': total_points,
            'coverage_score': coverage_score,
            'support_score': support_score,
            'unsupported_ratio': unsupported_ratio,
            'objective_score': objective_score,
            'objective_pass': objective_pass,
            'objective_notes': '|'.join(unsupported[:12]),
            'referenceStatus': profile.get('reference_status', 'heuristic_draft'),
        }


def load_reference_json(path: str) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError("Reference JSON must be a dict keyed by requirement id.")
    return data


def build_reference_profiles(target_ids: list[str], docs_dir: str, database: Optional[str],
                             max_neighbor_hops: int) -> dict[str, dict[str, Any]]:
    resolver = GraphTargetResolver(database=database, max_neighbor_hops=max_neighbor_hops)
    profiles: dict[str, dict[str, Any]] = {}
    try:
        extractor = GraphAwareDocsExtractor(docs_dir)
        for target_id in target_ids:
            try:
                ctx = resolver.resolve(target_id)
                profiles[target_id] = extractor.extract(ctx)
            except Exception as exc:
                log.error("Reference resolution failed for %s: %s", target_id, exc)
    finally:
        resolver.close()
    return profiles


def objective_summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict
    grouped: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in results:
        key = (row.get('model', 'unknown'), row.get('mode', 'unknown'), row.get('pipeline', 'full'))
        for metric in ('coverage_score', 'support_score', 'unsupported_ratio', 'objective_score', 'objective_pass'):
            value = row.get(metric)
            if value not in (None, ''):
                grouped[key][metric].append(float(value))
    summary_rows: list[dict[str, Any]] = []
    for (model, mode, pipeline), metrics in sorted(grouped.items()):
        def avg(name: str) -> float:
            vals = metrics.get(name, [])
            return round(sum(vals) / len(vals), 4) if vals else 0.0
        summary_rows.append({
            'model': model, 'mode': mode, 'pipeline': pipeline,
            'n': len(metrics.get('objective_score', [])),
            'coverage_score_avg': avg('coverage_score'),
            'support_score_avg': avg('support_score'),
            'unsupported_ratio_avg': avg('unsupported_ratio'),
            'objective_score_avg': avg('objective_score'),
            'objective_pass_rate': avg('objective_pass'),
        })
    return summary_rows


def objective_main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description='Objective, document-grounded evaluation (model-agnostic; one implementation for all models).')
    parser.add_argument('--input', required=True, help='e.g. runs/*.csv')
    parser.add_argument('--docs-dir', default='docs')
    parser.add_argument('--target-id', default=None)
    parser.add_argument('--out-dir', default=DEFAULT_EVAL_DIR)
    parser.add_argument('--neo4j-database', default=None)
    parser.add_argument('--max-neighbor-hops', type=int, default=2,
                        help='Default 2 = generation-time graph traversal depth (fix A6).')
    parser.add_argument('--reference-json', default=None,
                        help='Frozen (ideally human-validated) canonical reference. If given, docs/Neo4j are not queried.')
    parser.add_argument('--export-reference', action='store_true',
                        help='Export the heuristic reference draft for manual validation, then exit.')
    parser.add_argument('--match-min-ratio', type=float, default=0.25)
    parser.add_argument('--match-min-tokens', type=int, default=2)
    parser.add_argument('--pass-min-coverage', type=float, default=0.15)
    parser.add_argument('--pass-min-support', type=float, default=0.50)
    parser.add_argument('--w-coverage', type=float, default=0.55)
    parser.add_argument('--w-support', type=float, default=0.45)
    args = parser.parse_args()

    rows = load_run_rows(args.input)
    if args.target_id:
        rows = [r for r in rows if (r.get('reqId') or '').strip() == args.target_id]
    target_ids = ([args.target_id] if args.target_id
                  else sorted({(r.get('reqId') or '').strip() for r in rows if (r.get('reqId') or '').strip()}))
    if not target_ids:
        raise SystemExit('No reqId found in input CSVs and no --target-id given.')

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if args.reference_json:
        profiles = load_reference_json(args.reference_json)
        missing = [t for t in target_ids if t not in profiles]
        if missing:
            log.warning('Reference JSON is missing %d requirement(s): %s', len(missing), missing[:10])
        ref_status = 'frozen:' + args.reference_json
    else:
        log.warning('No --reference-json given: building a HEURISTIC reference draft on the fly. '
                    'For the paper, export it (--export-reference), validate it manually, freeze it, '
                    'and re-run with --reference-json (fix A5).')
        profiles = build_reference_profiles(target_ids, args.docs_dir, args.neo4j_database,
                                            args.max_neighbor_hops)
        ref_status = 'heuristic_draft'

    draft_path = out / f'reference_draft_{stamp}.json'
    if not args.reference_json:
        draft_path.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding='utf-8')
        log.info('Heuristic reference draft exported to %s — validate manually, then freeze.', draft_path)
    if args.export_reference:
        print(json.dumps({'reference_draft': str(draft_path), 'targets': len(profiles)},
                         ensure_ascii=False, indent=2))
        return

    evaluator = SourceGroundedEvaluator(
        profiles,
        match_min_ratio=args.match_min_ratio, match_min_tokens=args.match_min_tokens,
        pass_min_coverage=args.pass_min_coverage, pass_min_support=args.pass_min_support,
        w_coverage=args.w_coverage, w_support=args.w_support,
    )
    results = [evaluator.evaluate_row(row) for row in rows]
    summary_rows = objective_summarize(results)

    tag = re.sub(r'[^A-Za-z0-9_.-]+', '', args.input.replace('/', '_'))[:40] or 'batch'
    detail_path = out / f'objective_evaluation_details_{tag}_{stamp}.csv'
    summary_path = out / f'objective_evaluation_summary_{tag}_{stamp}.csv'

    with detail_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    if summary_rows:
        with summary_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    write_run_metadata(args.out_dir, detail_path.stem, build_run_metadata(
        input_pattern=args.input, reference=ref_status,
        match_min_ratio=args.match_min_ratio, match_min_tokens=args.match_min_tokens,
        pass_min_coverage=args.pass_min_coverage, pass_min_support=args.pass_min_support,
        w_coverage=args.w_coverage, w_support=args.w_support,
        max_neighbor_hops=args.max_neighbor_hops, rows=len(results),
    ))

    print('\n' + '=' * 100)
    print(f"{'OBJECTIVE (DOCS-BASED) EVALUATION SUMMARY':^100}")
    print('=' * 100)
    print(f"| {'Model':<22} | {'Mode':<7} | {'Pipe':<13} | {'N':<4} | {'Cov':<6} | {'Supp':<6} | {'Obj':<6} | {'Pass%':<6} |")
    print('-' * 100)
    for r in summary_rows:
        print(f"| {str(r['model'])[:22]:<22} | {r['mode']:<7} | {r['pipeline']:<13} | {r['n']:<4} "
              f"| {r['coverage_score_avg']:>6.3f} | {r['support_score_avg']:>6.3f} "
              f"| {r['objective_score_avg']:>6.3f} | {r['objective_pass_rate']*100:>5.1f}% |")
    print('=' * 100 + '\n')
    print(json.dumps({'detail_csv': str(detail_path), 'summary_csv': str(summary_path),
                      'reference': ref_status, 'rows': len(results)}, ensure_ascii=False, indent=2))
