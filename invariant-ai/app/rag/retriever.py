import os
import math
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_title: str
    content: str
    source_path: str
    score: float


class HybridRetriever:
    def __init__(self, kb_dir: Optional[str] = None):
        self.kb_dir = kb_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge_base"
        )
        self.chunks: list[dict] = []
        self._load_documents()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def _load_documents(self):
        self.chunks.clear()
        if not os.path.exists(self.kb_dir):
            return

        for root, _, files in os.walk(self.kb_dir):
            for file in files:
                if file.endswith((".md", ".txt")):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Chunk by markdown sections (split by '## ')
                    sections = content.split("## ")
                    title = sections[0].replace("# ", "").strip().split("\n")[0]
                    for idx, sec in enumerate(sections):
                        chunk_text = sec if idx == 0 else f"## {sec}"
                        self.chunks.append({
                            "chunk_id": f"{file}#section-{idx}",
                            "document_title": title,
                            "content": chunk_text.strip(),
                            "source_path": path,
                            "tokens": self._tokenize(chunk_text),
                        })

    def _sparse_bm25_score(self, query_tokens: list[str], chunk_tokens: list[str]) -> float:
        """BM25 keyword relevance score."""
        score = 0.0
        chunk_len = len(chunk_tokens)
        if chunk_len == 0:
            return 0.0

        for q in query_tokens:
            tf = chunk_tokens.count(q)
            if tf > 0:
                # Standard BM25 term weighting: k1=1.5, b=0.75
                score += (tf * 2.5) / (tf + 1.5 * (0.25 + 0.75 * (chunk_len / 50.0)))
        return score

    def _dense_sim_score(self, query_tokens: list[str], chunk_tokens: list[str]) -> float:
        """Cosine token similarity representation."""
        if not query_tokens or not chunk_tokens:
            return 0.0
        q_set = set(query_tokens)
        c_set = set(chunk_tokens)
        intersection = q_set.intersection(c_set)
        return len(intersection) / math.sqrt(len(q_set) * len(c_set))

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q_tokens = self._tokenize(query)
        if not q_tokens or not self.chunks:
            return []

        # Track 1: Sparse BM25
        sparse_scores = []
        for c in self.chunks:
            s = self._sparse_bm25_score(q_tokens, c["tokens"])
            sparse_scores.append((c, s))
        sparse_ranked = sorted(sparse_scores, key=lambda x: x[1], reverse=True)

        # Track 2: Dense similarity
        dense_scores = []
        for c in self.chunks:
            d = self._dense_sim_score(q_tokens, c["tokens"])
            dense_scores.append((c, d))
        dense_ranked = sorted(dense_scores, key=lambda x: x[1], reverse=True)

        # Reciprocal Rank Fusion (RRF) with k=60
        rrf_scores: dict[str, float] = {}
        chunk_map = {c["chunk_id"]: c for c in self.chunks}

        for rank, (c, score) in enumerate(dense_ranked[:20]):
            if score > 0:
                rrf_scores[c["chunk_id"]] = rrf_scores.get(c["chunk_id"], 0.0) + 1.0 / (60 + rank + 1)

        for rank, (c, score) in enumerate(sparse_ranked[:20]):
            if score > 0:
                rrf_scores[c["chunk_id"]] = rrf_scores.get(c["chunk_id"], 0.0) + 1.0 / (60 + rank + 1)

        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            RetrievedChunk(
                chunk_id=cid,
                document_title=chunk_map[cid]["document_title"],
                content=chunk_map[cid]["content"],
                source_path=chunk_map[cid]["source_path"],
                score=round(score, 4),
            )
            for cid, score in sorted_ids
        ]

