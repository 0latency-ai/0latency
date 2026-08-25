"""Cost Kill-Switch for LongMemEval Benchmark Harness.

Standalone side-channel module providing:
- Pre-flight cost estimation with hard gate
- Thread-safe runtime CostAccumulator with abort-on-breach

Introduced after cost incident (2026-05-16): .env EXTRACTION_MODEL override
to claude-sonnet-4-6 caused $603 unintended spend.

This module does NOT touch scoring, prompt content, fuzzy matching, recall logic,
or payload construction. It is a pure cost-tracking side-channel.
"""

import sys
import threading
from typing import Dict, List, Any

# Pricing table: model_id -> {input: $/1M tokens, output: $/1M tokens}
PRICE_TABLE = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-haiku-4-20250514":   {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    # Fallback for unknown models: use Sonnet pricing (conservative)
    "_default":                   {"input": 3.00, "output": 15.00},
}

ESTIMATED_OUTPUT_TOKENS_PER_EXTRACTION = 400
ESTIMATED_OUTPUT_TOKENS_PER_REASONING = 500
RECALL_BUDGET_TOKENS = 8000


def get_prices(model: str) -> Dict[str, float]:
    """Look up pricing for a model, falling back to Sonnet (most expensive)."""
    return PRICE_TABLE.get(model, PRICE_TABLE["_default"])


def estimate_tokens_from_content(content: str) -> int:
    """Rough token estimate: 4 chars = 1 token (matches recall.py heuristic)."""
    return max(1, len(content) // 4)


def preflight_estimate(
    turns: List[Dict[str, Any]],
    num_questions: int,
    model: str,
    enable_reasoning: bool = False,
    max_cost: float = 20.0,
) -> Dict[str, Any]:
    """
    Compute pre-flight cost estimate. Returns dict with breakdown.
    Calls sys.exit(5) if estimate exceeds max_cost.
    """
    prices = get_prices(model)

    # Extraction cost
    extraction_input = sum(
        estimate_tokens_from_content(t.get("content", "")) for t in turns
    )
    extraction_output = len(turns) * ESTIMATED_OUTPUT_TOKENS_PER_EXTRACTION

    # Recall cost (retrieval only -- no LLM generation in recall itself)
    recall_input = num_questions * RECALL_BUDGET_TOKENS
    recall_output = 0

    # Reasoning cost (optional)
    reasoning_input = num_questions * RECALL_BUDGET_TOKENS if enable_reasoning else 0
    reasoning_output = num_questions * ESTIMATED_OUTPUT_TOKENS_PER_REASONING if enable_reasoning else 0

    total_input = extraction_input + recall_input + reasoning_input
    total_output = extraction_output + recall_output + reasoning_output

    estimated_cost = (
        total_input * prices["input"] / 1_000_000 +
        total_output * prices["output"] / 1_000_000
    )

    report = {
        "model": model,
        "prices": prices,
        "num_turns": len(turns),
        "num_questions": num_questions,
        "enable_reasoning": enable_reasoning,
        "extraction_input_tokens": extraction_input,
        "extraction_output_tokens": extraction_output,
        "recall_input_tokens": recall_input,
        "recall_output_tokens": recall_output,
        "reasoning_input_tokens": reasoning_input,
        "reasoning_output_tokens": reasoning_output,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": estimated_cost,
        "max_cost_usd": max_cost,
        "passed": estimated_cost <= max_cost,
    }

    print(f"\n  COST PRE-FLIGHT ESTIMATE")
    print(f"  Model: {model}")
    print(f"  Pricing: ${prices['input']:.2f}/1M input, ${prices['output']:.2f}/1M output")
    print(f"  Turns: {len(turns):,}  Questions: {num_questions}")
    print(f"  Est. input tokens:  {total_input:>12,}")
    print(f"  Est. output tokens: {total_output:>12,}")
    print(f"  ---")
    print(f"  PROJECTED COST:      ${estimated_cost:>10.4f}")
    print(f"  BUDGET (--max-cost): ${max_cost:>10.2f}")

    if not report["passed"]:
        print(f"  HALT: Projected cost exceeds budget. Refusing to start.")
        print(f"  Increase --max-cost or reduce dataset size.")
        sys.exit(5)
    else:
        headroom = max_cost - estimated_cost
        print(f"  PASS: ${headroom:.2f} headroom remaining")

    return report


class CostAccumulator:
    """Thread-safe runtime cost tracker with hard abort on budget breach."""

    def __init__(self, max_cost: float, model: str):
        self._lock = threading.Lock()
        self._input_tokens = 0
        self._output_tokens = 0
        self._max_cost = max_cost
        self._prices = get_prices(model)
        self.aborted = False
        self.abort_reason = ""

    def add(self, input_tokens: int, output_tokens: int) -> bool:
        """Record token usage. Returns True if budget is now exceeded (abort)."""
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            cost = self._cost_unlocked()
            if cost > self._max_cost:
                self.aborted = True
                self.abort_reason = (
                    f"Cumulative cost ${cost:.4f} exceeded "
                    f"--max-cost ${self._max_cost:.2f} "
                    f"(in={self._input_tokens:,} out={self._output_tokens:,})"
                )
                return True
            return False

    def _cost_unlocked(self) -> float:
        return (
            self._input_tokens * self._prices["input"] / 1_000_000 +
            self._output_tokens * self._prices["output"] / 1_000_000
        )

    @property
    def current_cost(self) -> float:
        with self._lock:
            return self._cost_unlocked()

    @property
    def total_input_tokens(self) -> int:
        with self._lock:
            return self._input_tokens

    @property
    def total_output_tokens(self) -> int:
        with self._lock:
            return self._output_tokens

    def summary(self) -> str:
        with self._lock:
            return (
                f"Cost: ${self._cost_unlocked():.4f} / ${self._max_cost:.2f} "
                f"(input={self._input_tokens:,} output={self._output_tokens:,})"
            )
