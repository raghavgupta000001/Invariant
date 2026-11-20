import httpx
import structlog
from typing import Any, Optional
from app.rag.retriever import HybridRetriever

logger = structlog.get_logger()


class EvidenceCollectorTools:
    def __init__(
        self,
        core_api_url: str = "http://localhost:8080",
        simulator_url: str = "http://localhost:8000",
        retriever: Optional[HybridRetriever] = None,
    ):
        self.core_api_url = core_api_url
        self.simulator_url = simulator_url
        self.retriever = retriever or HybridRetriever()

    async def get_transaction_full_record(self, transaction_ref: str) -> dict[str, Any]:
        """Retrieves full transaction record from invariant-core."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(f"{self.core_api_url}/transactions/{transaction_ref}")
                if res.status_code == 200:
                    return res.json()
            except Exception as e:
                logger.warning("failed_to_fetch_transaction", error=str(e))
        return {"transaction_ref": transaction_ref, "status": "UNKNOWN", "steps": {}}

    async def get_all_events_for_transaction(self, transaction_ref: str) -> list[dict[str, Any]]:
        """Retrieves timeline of all events observed for transaction."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(f"{self.core_api_url}/transactions/{transaction_ref}/timeline")
                if res.status_code == 200:
                    return res.json().get("events", [])
            except Exception as e:
                logger.warning("failed_to_fetch_timeline", error=str(e))
        return []

    async def query_source_system_current_state(self, transaction_ref: str) -> dict[str, Any]:
        """Makes read-only query to simulator cross-system status endpoint."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(f"{self.simulator_url}/simulate/status/{transaction_ref}")
                if res.status_code == 200:
                    return res.json()
            except Exception as e:
                logger.warning("failed_to_query_source_state", error=str(e))
        return {"transaction_ref": transaction_ref, "services": {}}

    async def search_similar_incidents(self, incident_type: str, limit: int = 3) -> list[dict[str, Any]]:
        """Retrieves historical resolved incidents of similar type."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                res = await client.get(f"{self.core_api_url}/incidents?state=RESOLVED")
                if res.status_code == 200:
                    incidents = res.json().get("incidents", [])
                    matched = [i for i in incidents if i.get("incident_type") == incident_type]
                    return matched[:limit]
            except Exception:
                pass
        return []

    def retrieve_runbook(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Performs hybrid RAG over operational runbooks."""
        chunks = self.retriever.retrieve(query, top_k=top_k)
        return [
            {
                "chunk_id": c.chunk_id,
                "document_title": c.document_title,
                "content": c.content,
                "source_path": c.source_path,
                "score": c.score,
            }
            for c in chunks
        ]

