import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMCallMetrics:
    model: str
    operation: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_usd: float
    cached: bool = False


class LLMMetricsCollector:
    # Model pricing per 1,000,000 tokens
    PRICING = {
        "gemini-1.5-pro": {"input": 3.50 / 1e6, "output": 10.50 / 1e6},
        "gemini-1.5-flash": {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
        "gemini-pro": {"input": 3.50 / 1e6, "output": 10.50 / 1e6},
    }

    def __init__(self):
        self.metrics_history: list[LLMCallMetrics] = []
        self._cache: dict[str, str] = {}

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self.PRICING.get(model, self.PRICING["gemini-1.5-flash"])
        cost = (prompt_tokens * rates["input"]) + (completion_tokens * rates["output"])
        return round(cost, 6)

    def record_call(
        self,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        cached: bool = False,
    ) -> LLMCallMetrics:
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = 0.0 if cached else self.calculate_cost(model, prompt_tokens, completion_tokens)

        metric = LLMCallMetrics(
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            cached=cached,
        )
        self.metrics_history.append(metric)
        return metric

    def get_summary(self) -> dict:
        total_tokens = sum(m.total_tokens for m in self.metrics_history)
        total_cost = sum(m.cost_usd for m in self.metrics_history)
        total_calls = len(self.metrics_history)
        cache_hits = sum(1 for m in self.metrics_history if m.cached)

        avg_latency = (
            sum(m.latency_ms for m in self.metrics_history) / total_calls
            if total_calls > 0 else 0
        )

        return {
            "total_calls": total_calls,
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hits / total_calls, 3) if total_calls > 0 else 0.0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency, 1),
        }

    def cache_lookup(self, prompt: str) -> Optional[str]:
        h = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        return self._cache.get(h)

    def cache_store(self, prompt: str, response: str):
        h = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        self._cache[h] = response

