"""Gemini 2.5 Pro client for the chatbot runtime.

Loads API key from /Users/rajat/Desktop/Ramco Rise Claude/ramco-journey-model/.env
Caches responses to disk under .gemini_cache/ for repeatability during eval.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

try:
    import google.generativeai as genai
    _SDK = True
except Exception:
    genai = None
    _SDK = False


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
CACHE_DIR = HERE / ".gemini_cache"


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = PROJECT / ".env"
    if not p.exists():
        return env
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
    return env


class LLMError(Exception): ...


class LLMClient:
    def __init__(self, model: str | None = None, use_cache: bool = True):
        env = _load_env()
        self.api_key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.model_name = model or env.get("GEMINI_MODEL") or "gemini-2.5-pro"
        self.use_cache = use_cache
        self._model = None
        if use_cache:
            CACHE_DIR.mkdir(exist_ok=True)

    @property
    def available(self) -> bool:
        return _SDK and bool(self.api_key)

    def _model_obj(self):
        if self._model is not None:
            return self._model
        if not self.available:
            raise LLMError("Gemini not available")
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def _key(self, prompt: str, temperature: float, json_mode: bool) -> str:
        return hashlib.sha1(
            f"{self.model_name}|t={temperature}|json={json_mode}|{prompt}".encode("utf-8")
        ).hexdigest()

    def call_json(self, prompt: str, *, temperature: float = 0.0,
                  max_output_tokens: int = 4096) -> dict:
        if not self.available:
            raise LLMError("Gemini SDK or API key missing")

        key = self._key(prompt, temperature, True)
        if self.use_cache:
            cached = CACHE_DIR / f"{key}.json"
            if cached.exists():
                return json.loads(cached.read_text(encoding="utf-8"))

        cfg = {"temperature": temperature,
               "max_output_tokens": max_output_tokens,
               "response_mime_type": "application/json"}
        for attempt in range(2):
            try:
                resp = self._model_obj().generate_content(prompt, generation_config=cfg)
                text = (resp.text or "").strip()
                if not text:
                    raise LLMError("Empty Gemini response")
                # strip code fences if present
                if text.startswith("```"):
                    text = text.split("```", 2)[1]
                    if text.lower().startswith("json"):
                        text = text[4:]
                    text = text.strip().rstrip("`")
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError:
                    raise LLMError(f"Could not parse JSON: {text[:200]}")
                if self.use_cache:
                    (CACHE_DIR / f"{key}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")
                return obj
            except LLMError:
                raise
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.8)
                    continue
                raise LLMError(f"Gemini call failed: {e}") from e
        raise LLMError("unreachable")
