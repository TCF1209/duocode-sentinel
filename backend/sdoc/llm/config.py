"""Model selection, the pinned rate card, and the run budget.

Two rules govern this file.

**Prices are a pinned snapshot, not a memory.** Every figure below was read
from OpenAI's published pricing page on the date in `PRICING_SNAPSHOT`, and the
source is recorded so anyone can re-check it. A cost figure quoted in a pitch
has to be defensible.

**Unknown models fail closed.** Asking for a model with no audited price raises
rather than silently billing at a rate nobody verified. A system that cannot
say what a call costs has no business making it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

# Read from https://developers.openai.com/api/docs/pricing on this date.
PRICING_SNAPSHOT = "openai-published-pricing-2026-09-19"

# USD per 1,000,000 tokens: (input, cached_input, output)
PRICES_USD_PER_MILLION: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "gpt-5":        (Decimal("1.25"), Decimal("0.125"), Decimal("10.00")),
    "gpt-5-mini":   (Decimal("0.25"), Decimal("0.025"), Decimal("2.00")),
    "gpt-5-nano":   (Decimal("0.05"), Decimal("0.005"), Decimal("0.40")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("0.10"),  Decimal("1.60")),
    "gpt-4.1-nano": (Decimal("0.10"), Decimal("0.025"), Decimal("0.40")),
    "gpt-4o-mini":  (Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
}

# gpt-5-mini is the default for both text and vision: capable enough for the
# cases the rules could not settle, and cheap enough that using it on the tail
# of an inbox is not a decision anyone has to defend. The rules handle the bulk,
# so a more expensive model would buy accuracy we are not short of.
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_VISION_MODEL = "gpt-5-mini"

# A single run may not spend more than this without being asked. When the
# ceiling is reached the pipeline stops calling the model and escalates the
# remaining cases to a human — which is a correct outcome, not a failure.
DEFAULT_RUN_BUDGET_USD = Decimal("2.00")

_MILLION = Decimal("1000000")


class UnpricedModel(RuntimeError):
    """A model was requested that has no audited price in the snapshot."""


@dataclass(frozen=True)
class LLMSettings:
    api_key: str | None
    model: str
    vision_model: str
    run_budget_usd: Decimal
    cache_enabled: bool

    @property
    def available(self) -> bool:
        """Whether model calls can be made at all.

        False is a normal operating mode, not an error: the deterministic path
        handles every document it recognises and escalates the rest.
        """
        return bool(self.api_key)


def load_settings(env: dict[str, str] | None = None) -> LLMSettings:
    env = dict(os.environ if env is None else env)
    model = env.get("SENTINEL_LLM_MODEL") or DEFAULT_MODEL
    vision = env.get("SENTINEL_VISION_MODEL") or DEFAULT_VISION_MODEL
    for name in (model, vision):
        if name not in PRICES_USD_PER_MILLION:
            raise UnpricedModel(
                f"{name!r} has no audited price in {PRICING_SNAPSHOT}. "
                f"Add it to PRICES_USD_PER_MILLION with a source, or pick one of: "
                f"{', '.join(sorted(PRICES_USD_PER_MILLION))}."
            )
    budget_raw = env.get("SENTINEL_RUN_BUDGET_USD")
    budget = Decimal(budget_raw) if budget_raw else DEFAULT_RUN_BUDGET_USD
    return LLMSettings(
        api_key=(env.get("OPENAI_API_KEY") or "").strip() or None,
        model=model,
        vision_model=vision,
        run_budget_usd=budget,
        cache_enabled=env.get("SENTINEL_LLM_CACHE", "1") != "0",
    )


def cost_usd(model: str, *, input_tokens: int, output_tokens: int,
             cached_tokens: int = 0) -> Decimal:
    """What a call actually cost, at the pinned rates.

    `cached_tokens` are input tokens the provider served from its own prompt
    cache and bills at the lower rate; they are a subset of `input_tokens`.
    """
    try:
        price_in, price_cached, price_out = PRICES_USD_PER_MILLION[model]
    except KeyError as exc:
        raise UnpricedModel(f"{model!r} has no audited price") from exc

    fresh = max(0, input_tokens - cached_tokens)
    return (
        Decimal(fresh) * price_in
        + Decimal(cached_tokens) * price_cached
        + Decimal(output_tokens) * price_out
    ) / _MILLION


def load_dotenv_if_present(path: Optional[str] = None) -> None:
    """Load a local .env so the CLI works without exporting variables.

    Searched from this file upwards, not from the working directory. That
    distinction was a real bug rather than tidiness: `api/main.py` documents
    `cd backend && uvicorn api.main:app` as a way to run the server, and under
    a bare `".env"` the repository-root file is then invisible, so the model
    tier switches itself off — silently, because an absent key is a normal
    state that degrades to the deterministic path rather than raising. The
    symptom is a `/compare?use_llm=true` that quietly behaves exactly like
    `use_llm=false`.

    Deliberately silent when the file really is absent: on a deployed server
    the variables come from the platform, and there is no .env to find.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:                                   # pragma: no cover
        return

    if path is not None:
        load_dotenv(path, override=False)
        return

    # backend/sdoc/llm/config.py -> backend/sdoc/llm, backend/sdoc, backend,
    # <repo root>. The repository root is where .env lives and .env.example
    # tells people to put it.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return
