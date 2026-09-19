"""The model client: structured output, caching, cost accounting, a budget.

Design constraints that shaped this file:

* **Unavailable is a normal state.** No key, no network, or a spent budget all
  raise `LLMUnavailable`, and every caller treats that as "escalate this case"
  rather than as a crash. The pipeline must finish its inbox either way.
* **Every call is metered.** Tokens and cost are recorded per purpose at the
  pinned rates, so the cost figure we quote is measured, not estimated.
* **Every call is cached by content.** A re-run costs nothing and returns the
  same answers, which is what makes a live demo safe.
* **Output is schema-validated.** The model is asked for a Pydantic shape and
  the SDK enforces it, so a caller never parses free text.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

from . import config
from .cache import ResponseCache, cache_key

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """A model answer could not be obtained. Callers escalate instead."""


@dataclass
class Usage:
    """What the run actually spent, broken down by what it was spent on."""

    calls: int = 0
    cached_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    by_purpose: dict[str, dict[str, Any]] = field(default_factory=dict)
    refusals: int = 0
    errors: int = 0

    def record(self, purpose: str, *, input_tokens: int, output_tokens: int,
               cost: Decimal, cached: bool) -> None:
        self.calls += 1
        if cached:
            self.cached_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost
        slot = self.by_purpose.setdefault(
            purpose, {"calls": 0, "cached": 0, "input_tokens": 0,
                      "output_tokens": 0, "cost_usd": Decimal("0")})
        slot["calls"] += 1
        slot["cached"] += int(cached)
        slot["input_tokens"] += input_tokens
        slot["output_tokens"] += output_tokens
        slot["cost_usd"] += cost

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "live_calls": self.calls - self.cached_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": float(round(self.cost_usd, 6)),
            "refusals": self.refusals,
            "errors": self.errors,
            "by_purpose": {
                k: {**v, "cost_usd": float(round(v["cost_usd"], 6))}
                for k, v in sorted(self.by_purpose.items())
            },
        }


class LLMClient:
    """A thin, metered wrapper. Callers never touch the SDK directly."""

    def __init__(self, settings: Optional[config.LLMSettings] = None,
                 cache_root: str = ".cache/llm") -> None:
        self.settings = settings or config.load_settings()
        self.cache = ResponseCache(cache_root, enabled=self.settings.cache_enabled)
        self.usage = Usage()
        self._client = None
        self._budget_exhausted = False

    # -- availability ----------------------------------------------------
    @property
    def available(self) -> bool:
        return self.settings.available and not self._budget_exhausted

    def _require(self) -> Any:
        if not self.settings.available:
            raise LLMUnavailable("no OPENAI_API_KEY configured")
        if self._budget_exhausted:
            raise LLMUnavailable(
                f"run budget of ${self.settings.run_budget_usd} reached; "
                f"remaining cases are escalated rather than charged"
            )
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:                    # pragma: no cover
                raise LLMUnavailable("openai SDK is not installed") from exc
            self._client = OpenAI(api_key=self.settings.api_key)
        return self._client

    def _check_budget(self) -> None:
        if self.usage.cost_usd >= self.settings.run_budget_usd:
            self._budget_exhausted = True

    # -- the one call everything goes through ----------------------------
    def structured(
        self,
        *,
        purpose: str,
        instructions: str,
        prompt: str,
        schema: Type[T],
        images: Optional[list[bytes]] = None,
        model: Optional[str] = None,
        max_output_tokens: int = 2048,
        reasoning_effort: Optional[str] = "low",
    ) -> T:
        """Ask the model for `schema` and return a validated instance.

        `purpose` is a short slug ("classify", "extract", "read_scan") used for
        the cost breakdown and the cache key, so the metrics page can say where
        the money went.

        `reasoning_effort` is a real cost lever on reasoning models, which bill
        their internal reasoning as output tokens: a one-line classification was
        spending four hundred output tokens on a three-field answer. "low" is
        the default because these are extraction and triage tasks, where the
        work is reading carefully rather than thinking hard. Pass None to let
        the model decide.
        """
        chosen = model or (self.settings.vision_model if images else self.settings.model)

        payload: dict[str, Any] = {
            "instructions": instructions,
            "prompt": prompt,
            "schema": schema.model_json_schema(),
            "max_output_tokens": max_output_tokens,
            "reasoning_effort": reasoning_effort,
        }
        if images:
            # Hash the bytes, not the base64: same image, same key, and the
            # cache file stays small.
            import hashlib
            payload["images"] = [hashlib.sha256(b).hexdigest() for b in images]

        key = cache_key(model=chosen, purpose=purpose, payload=payload)
        hit = self.cache.get(key)
        if hit is not None:
            self.usage.record(
                purpose,
                input_tokens=hit.get("input_tokens", 0),
                output_tokens=hit.get("output_tokens", 0),
                cost=Decimal("0"),           # a cache hit costs nothing
                cached=True,
            )
            return schema.model_validate(hit["value"])

        self.cache.record_miss()
        client = self._require()

        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for blob in images or []:
            b64 = base64.b64encode(blob).decode("ascii")
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{b64}",
            })

        kwargs: dict[str, Any] = {
            "model": chosen,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "text_format": schema,
            "max_output_tokens": max_output_tokens,
        }
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        try:
            response = client.responses.parse(**kwargs)
        except TypeError:
            # An SDK or model that does not take a reasoning setting: the call
            # is still valid without it, so drop it rather than failing.
            kwargs.pop("reasoning", None)
            try:
                response = client.responses.parse(**kwargs)
            except Exception as exc:
                self.usage.errors += 1
                raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:
            self.usage.errors += 1
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            # A refusal or a truncated response. Not an answer, so not used.
            self.usage.refusals += 1
            raise LLMUnavailable("model returned no parsed output")

        usage = getattr(response, "usage", None)
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        cached_tok = 0
        details = getattr(usage, "input_tokens_details", None)
        if details is not None:
            cached_tok = int(getattr(details, "cached_tokens", 0) or 0)

        cost = config.cost_usd(chosen, input_tokens=in_tok,
                               output_tokens=out_tok, cached_tokens=cached_tok)
        self.usage.record(purpose, input_tokens=in_tok, output_tokens=out_tok,
                          cost=cost, cached=False)
        self._check_budget()

        self.cache.put(key, {
            "value": parsed.model_dump(),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "model": chosen,
        })
        return parsed

    # -- reporting -------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "model": self.settings.model,
            "vision_model": self.settings.vision_model,
            "pricing_snapshot": config.PRICING_SNAPSHOT,
            "budget_usd": float(self.settings.run_budget_usd),
            "budget_exhausted": self._budget_exhausted,
            "usage": self.usage.to_dict(),
            "cache": self.cache.stats(),
        }
