"""Per-model prices, read from the live Vultr Serverless Inference catalogue.

Cost figures on a sticker are computed from token counts the API returns and the
prices the API publishes, never from hand-typed constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelPrice:
    model: str
    input_per_token: float
    output_per_token: float

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return prompt_tokens * self.input_per_token + completion_tokens * self.output_per_token


INPUT_TYPES = {"prompt", "input", "input_tokens"}
OUTPUT_TYPES = {"completion", "output", "output_tokens"}


def parse_catalogue(payload: dict[str, Any]) -> dict[str, ModelPrice]:
    prices: dict[str, ModelPrice] = {}
    for model in payload.get("data", []):
        mid = model.get("id")
        if not mid:
            continue
        inp = out = 0.0
        modalities = [*model.get("input_modalities", []), *model.get("output_modalities", [])]
        for modality in modalities:
            for entry in modality.get("pricing", []) or []:
                if entry.get("unit") not in (None, "token"):
                    continue
                try:
                    value = float(entry.get("cost_usd", 0))
                except (TypeError, ValueError):
                    continue
                kind = str(entry.get("type", "")).lower()
                if kind in INPUT_TYPES:
                    inp = value
                elif kind in OUTPUT_TYPES:
                    out = value
        if not inp and out:
            # Decision, embedding and rerank models publish a single per-token price that
            # applies to the tokens they read (the docs bill decision input tokens against
            # the decision model), so use it for input as well.
            inp = out
        if inp or out:
            prices[mid] = ModelPrice(model=mid, input_per_token=inp, output_per_token=out)
    return prices
