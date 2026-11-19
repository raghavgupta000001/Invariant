from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from catalog.scenarios import (
    SCENARIOS,
    get_scenario,
    get_by_category,
    get_by_severity,
    CATEGORY_SUMMARY,
    SEVERITY_SUMMARY,
)
from app.injector import FailureInjector
from app.runner import ScenarioRunner

router = APIRouter(prefix="/failures", tags=["failures"])
injector = FailureInjector()
runner = ScenarioRunner(injector=injector)


@router.get("/scenarios")
async def list_scenarios(
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
):
    """List scenarios in catalog with optional filtering."""
    scenarios = SCENARIOS
    if category:
        scenarios = [s for s in scenarios if s.category == category]
    if severity:
        scenarios = [s for s in scenarios if s.severity == severity]

    return {
        "count": len(scenarios),
        "categories": CATEGORY_SUMMARY,
        "severities": SEVERITY_SUMMARY,
        "scenarios": [s.to_dict() for s in scenarios],
    }


@router.get("/scenarios/{scenario_id}")
async def get_scenario_detail(scenario_id: str):
    """Get single scenario details and ground-truth expectation."""
    sc = get_scenario(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return sc.to_dict()


@router.post("/inject/{scenario_id}")
async def inject_scenario(scenario_id: str):
    """Executes a specific scenario through the simulator."""
    try:
        result = await runner.run_scenario_by_id(scenario_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-batch")
async def run_batch(
    category: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    """Runs a batch of scenarios and returns aggregate execution report."""
    return await runner.run_batch(category=category, limit=limit)


@router.post("/reset")
async def reset_failures():
    """Resets all injected failures across external services."""
    return await injector.reset_all_services()

