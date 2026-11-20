from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.agents.orchestrator import InvestigationOrchestrator
from app.telemetry.metrics import LLMMetricsCollector
from app.rag.retriever import HybridRetriever

router = APIRouter(prefix="/ai", tags=["ai"])

metrics_collector = LLMMetricsCollector()
retriever = HybridRetriever()
orchestrator = InvestigationOrchestrator(metrics=metrics_collector)


@router.post("/investigate")
async def investigate_incident_endpoint(incident: dict):
    """
    Triggers multi-agent investigation over an incident and returns structured root cause & recovery plan.
    """
    try:
        res = await orchestrator.investigate_incident(incident)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/query")
async def query_runbooks(q: str = Query(..., description="Query term")):
    """
    Performs hybrid dense/sparse retrieval over operational runbooks.
    """
    results = retriever.retrieve(q, top_k=5)
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "chunk_id": r.chunk_id,
                "document_title": r.document_title,
                "source_path": r.source_path,
                "score": r.score,
                "snippet": r.content[:200] + "...",
            }
            for r in results
        ]
    }


@router.get("/telemetry")
async def get_telemetry_summary():
    """
    Returns LLM native metrics: tokens/sec, cost-per-request, cache hit rates, average latency.
    """
    return metrics_collector.get_summary()

