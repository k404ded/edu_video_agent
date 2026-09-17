"""
Thin wrapper around the Google Gemini API used by every agent stage.

Centralizing this makes it trivial to swap models, add retries, or
insert logging later without touching individual agent modules.
"""
import json
import re
import time
from typing import Optional, List
from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import get_api_key, MODEL_NAME, MAX_TOKENS_PER_CALL

_client = None
_exhausted_models = set()

# High-speed fallback models with separate quota pools on Gemini API
# Fast-lite models are prioritized first for sub-second responses
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]


def _get_model_candidates(preferred_model: Optional[str] = None) -> List[str]:
    global _exhausted_models
    base_model = preferred_model or MODEL_NAME
    all_models = [base_model]
    for m in FALLBACK_MODELS:
        if m not in all_models:
            all_models.append(m)
    available = [m for m in all_models if m not in _exhausted_models]
    return available if available else all_models


def _extract_retry_delay(err):
    """Extracts recommended retry delay in seconds if provided by Google API error."""
    try:
        if hasattr(err, "response_json") and isinstance(err.response_json, dict):
            details = err.response_json.get("error", {}).get("details", [])
            for d in details:
                if "retryDelay" in d:
                    m = re.search(r"([\d.]+)", str(d["retryDelay"]))
                    if m:
                        return float(m.group(1))
    except Exception:
        pass
    m = re.search(r"retry in ([\d.]+)s", str(err), re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"retryDelay[\'\":\s]+(\d+)", str(err))
    if m:
        return float(m.group(1))
    return None


def _is_daily_quota_error(err):
    """Checks if the 429 error is a daily quota limit rather than a per-minute burst."""
    msg = str(err)
    return "GenerateRequestsPerDay" in msg or "per_day" in msg.lower() or "limit: 20" in msg


def get_client():
    global _client
    key = get_api_key()
    if _client is None:
        if key:
            _client = genai.Client(api_key=key)
            _client._configured_key = key
        else:
            _client = genai.Client()
    elif key and getattr(_client, "_configured_key", None) != key:
        _client = genai.Client(api_key=key)
        _client._configured_key = key
    return _client


def _call_with_model_fallback(
    make_call_fn,
    preferred_model: Optional[str] = None,
    max_retries_per_model: int = 2,
    initial_delay: float = 1.0,
):
    """
    Executes an API call across model candidates, automatically failing over to
    healthy models if a model hits rate limits (429), high-demand spikes (503),
    or deprecation (404).
    Remembers exhausted models to eliminate latency penalties on subsequent calls.
    """
    global _exhausted_models
    candidates = _get_model_candidates(preferred_model)
    last_error = None

    for model in candidates:
        delay = initial_delay
        for attempt in range(max_retries_per_model):
            try:
                return make_call_fn(model)
            except APIError as e:
                last_error = e
                status_code = getattr(e, "code", None) or getattr(e, "status_code", None)

                # 429: Rate limited or quota exhausted
                if status_code == 429:
                    if _is_daily_quota_error(e):
                        _exhausted_models.add(model)
                        break

                    retry_sec = _extract_retry_delay(e)
                    if retry_sec and retry_sec <= 5 and attempt < max_retries_per_model - 1:
                        time.sleep(retry_sec)
                        continue
                    elif attempt < max_retries_per_model - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    else:
                        _exhausted_models.add(model)
                        break

                # 503: High demand spike -> temporary burst limit; wait briefly and retry
                elif status_code == 503:
                    if attempt < max_retries_per_model - 1:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    else:
                        break

                # 404: Model not found or deprecated -> mark exhausted
                elif status_code == 404:
                    _exhausted_models.add(model)
                    break

                else:
                    # Non-transient error (e.g. 400 Bad Request)
                    raise
            except Exception as e:
                last_error = e
                raise

    if last_error:
        if getattr(last_error, "code", None) == 429 and _is_daily_quota_error(last_error):
            raise ValueError(
                "Gemini API free-tier quota (requests per day) exceeded across all candidate models. "
                "Please enable pay-as-you-go billing in Google AI Studio for higher limits, "
                "or wait for the daily quota reset."
            ) from last_error
        raise last_error
    raise RuntimeError("Failed to generate content from Gemini API.")


def call_llm(prompt: str, max_tokens: int = None, model_name: Optional[str] = None) -> str:
    """Send a single-turn prompt to the model and return raw text output."""
    client = get_client()
    tokens = max_tokens or MAX_TOKENS_PER_CALL
    config = types.GenerateContentConfig(
        max_output_tokens=tokens,
    )

    def _call(m: str):
        return client.models.generate_content(
            model=m,
            contents=prompt,
            config=config,
        )

    response = _call_with_model_fallback(_call, preferred_model=model_name)
    return (response.text or "").strip()


def call_llm_json(prompt: str, max_tokens: int = None, model_name: Optional[str] = None):
    """
    Call the model and parse its response as JSON. Requests JSON response
    from the Gemini API, and strips markdown code fences if present.
    Raises ValueError with the raw text included if parsing fails, so
    calling code can surface a useful error instead of a silent crash.
    """
    client = get_client()
    tokens = max_tokens or MAX_TOKENS_PER_CALL
    config = types.GenerateContentConfig(
        max_output_tokens=tokens,
        response_mime_type="application/json",
    )

    def _call(m: str):
        return client.models.generate_content(
            model=m,
            contents=prompt,
            config=config,
        )

    response = _call_with_model_fallback(_call, preferred_model=model_name)
    raw = (response.text or "").strip()
    if not raw:
        raise ValueError("Received empty response from Gemini model.")

    # Strip markdown code fences if the model wraps JSON in ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract the first {...} or [...] block if there's stray text around it
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from model output:\n{raw}")
