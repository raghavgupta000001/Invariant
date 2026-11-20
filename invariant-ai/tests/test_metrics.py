from app.telemetry.metrics import LLMMetricsCollector


def test_cost_calculation():
    collector = LLMMetricsCollector()
    # 1,000 prompt tokens + 500 completion tokens on gemini-1.5-pro
    cost = collector.calculate_cost("gemini-1.5-pro", prompt_tokens=1000, completion_tokens=500)
    # (1000 * 3.50 / 1e6) + (500 * 10.50 / 1e6) = 0.0035 + 0.00525 = 0.00875
    assert cost == 0.00875


def test_metrics_recording_and_summary():
    collector = LLMMetricsCollector()
    m1 = collector.record_call(
        model="gemini-1.5-flash",
        operation="investigation",
        prompt_tokens=500,
        completion_tokens=200,
        latency_ms=120,
    )
    assert m1.total_tokens == 700
    assert m1.cost_usd > 0

    # Cached call
    m2 = collector.record_call(
        model="gemini-1.5-flash",
        operation="investigation",
        prompt_tokens=500,
        completion_tokens=200,
        latency_ms=5,
        cached=True,
    )
    assert m2.cost_usd == 0.0
    assert m2.cached is True

    summary = collector.get_summary()
    assert summary["total_calls"] == 2
    assert summary["cache_hits"] == 1
    assert summary["cache_hit_rate"] == 0.5
    assert summary["total_tokens"] == 1400


def test_semantic_cache():
    collector = LLMMetricsCollector()
    collector.cache_store("investigate INC-100", '{"result": "ok"}')
    cached = collector.cache_lookup("investigate INC-100")
    assert cached == '{"result": "ok"}'
    assert collector.cache_lookup("unknown prompt") is None

