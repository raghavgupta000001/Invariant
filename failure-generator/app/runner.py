import asyncio
import time
import structlog
from typing import Optional
from catalog.scenarios import SCENARIOS, get_scenario, get_by_category, FailureScenario
from app.injector import FailureInjector

logger = structlog.get_logger()


class ScenarioRunner:
    def __init__(self, injector: Optional[FailureInjector] = None):
        self.injector = injector or FailureInjector()

    async def run_scenario_by_id(self, scenario_id: str) -> dict:
        scenario = get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return await self.injector.execute_scenario(scenario)

    async def run_batch(self, category: Optional[str] = None, limit: Optional[int] = None) -> dict:
        target_scenarios = get_by_category(category) if category else SCENARIOS
        if limit:
            target_scenarios = target_scenarios[:limit]

        start_time = time.monotonic()
        results = []
        passed = 0
        failed = 0

        for sc in target_scenarios:
            try:
                res = await self.injector.execute_scenario(sc)
                results.append(res)
                if res["status"] in ("COMPLETED", "PARTIAL_FAILURE", "FAILED"):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error("scenario_execution_exception", scenario_id=sc.id, error=str(e))
                results.append({
                    "scenario_id": sc.id,
                    "status": "EXCEPTION",
                    "error": str(e),
                })
                failed += 1

        duration_ms = int((time.monotonic() - start_time) * 1000)

        return {
            "total_executed": len(target_scenarios),
            "reproducible_count": passed,
            "error_count": failed,
            "duration_ms": duration_ms,
            "results": results,
        }

