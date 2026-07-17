#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
05b_evaluate_thirdjudge.py — wrapper a harmadik bírálóhoz (DeepSeek).
NEM módosítja az exp_core-t: futásidőben lefokozza a response_format
'json_schema' típust 'json_object'-re (a DeepSeek API csak ezt támogatja).
Minden más (prompt, séma-validálás, cache, CLI) változatlan.

Használat: mint a 05_evaluate.py, csak:
  python 05b_evaluate_thirdjudge.py --input "runs*/*.csv" --judge-provider openai
    --judge-model deepseek-chat ... 
Env: OPENAI_BASE_URL=https://api.deepseek.com, OPENAI_API_KEY=<deepseek kulcs>
"""
import os, sys

if "deepseek" not in os.environ.get("OPENAI_BASE_URL", ""):
    sys.exit("BIZTONSAGI OV: OPENAI_BASE_URL nem a DeepSeekre mutat — "
             "ezt a wrappert csak harmadik-biralo futasra hasznald.")

import openai.resources.chat.completions as _occ

_orig_create = _occ.Completions.create

def _create(self, *args, **kwargs):
    rf = kwargs.get("response_format")
    if isinstance(rf, dict) and rf.get("type") == "json_schema":
        kwargs["response_format"] = {"type": "json_object"}
    return _orig_create(self, *args, **kwargs)

_occ.Completions.create = _create
print("[wrapper] response_format json_schema -> json_object (DeepSeek-kompatibilitas)")

from exp_core import judge_main
judge_main(default_judge_provider="openai", default_judge_model="deepseek-chat")
