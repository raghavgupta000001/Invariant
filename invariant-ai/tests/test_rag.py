from app.rag.retriever import HybridRetriever


def test_hybrid_retriever_finds_runbooks():
    retriever = HybridRetriever()
    results = retriever.retrieve("payment captured no erp order", top_k=3)
    assert len(results) > 0
    top = results[0]
    assert "payment" in top.content.lower() or "erp" in top.content.lower()
    assert top.score > 0
    assert top.source_path.endswith(".md")


def test_hybrid_retriever_amount_mismatch():
    retriever = HybridRetriever()
    results = retriever.retrieve("paise rupee unit conversion bug", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "paise" in top.content.lower() or "conversion" in top.content.lower()

