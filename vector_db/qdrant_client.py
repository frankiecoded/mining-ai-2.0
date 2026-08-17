import os
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient as QClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger("ai_os.qdrant")

COLLECTIONS = {
    "company_knowledge": 384,
    "long_term_memories": 384,
    "production_data": 384,
    "financial_data": 384,
}


class VectorDBClient:
    """
    Manages vector embeddings storage and similarity search using Qdrant.
    Handles semantic retrieval for company documents, datasets, and long-term memory.
    """
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None,
                 url: Optional[str] = None, api_key: Optional[str] = None):
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = int(port or os.getenv("QDRANT_PORT", "6333"))
        self.url = url or os.getenv("QDRANT_URL", "")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY", "")
        self.client = None
        self.is_mocked = False

        self.mock_collections: Dict[str, List[Dict[str, Any]]] = {
            name: [] for name in COLLECTIONS
        }
        self.connect()

    def connect(self):
        try:
            if self.url:
                self.client = QClient(url=self.url, api_key=self.api_key or None, timeout=10.0)
            else:
                self.client = QClient(host=self.host, port=self.port, timeout=5.0)
            self.client.get_collections()
            logger.info("Connected to Qdrant Vector DB successfully.")
            self.is_mocked = False
            self.initialize_collections()
        except Exception as e:
            logger.warning(f"Failed to connect to Qdrant: {e}. Using in-memory mock vector storage.")
            self.is_mocked = True

    def initialize_collections(self):
        if self.is_mocked:
            return

        for name, dim in COLLECTIONS.items():
            try:
                exists = self.client.collection_exists(collection_name=name)
                if not exists:
                    self.client.create_collection(
                        collection_name=name,
                        vectors_config=qmodels.VectorParams(
                            size=dim,
                            distance=qmodels.Distance.COSINE
                        )
                    )
                    logger.info(f"Created Qdrant collection: {name} ({dim}d)")
            except Exception as e:
                logger.error(f"Error creating collection {name}: {e}")

    def upsert_document(self, collection_name: str, doc_id: int, vector: List[float], payload: Dict[str, Any]):
        if len(vector) != 384:
            vector = (vector + [0.0] * 384)[:384]

        if self.is_mocked:
            if collection_name not in self.mock_collections:
                self.mock_collections[collection_name] = []

            self.mock_collections[collection_name] = [
                item for item in self.mock_collections[collection_name] if item["id"] != doc_id
            ]
            self.mock_collections[collection_name].append({
                "id": doc_id,
                "vector": vector,
                "payload": payload
            })
            return

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    qmodels.PointStruct(id=doc_id, vector=vector, payload=payload)
                ]
            )
        except Exception as e:
            logger.error(f"Qdrant upsert error: {e}")

    def count_documents(self, collection_name: str) -> int:
        if self.is_mocked:
            return len(self.mock_collections.get(collection_name, []))
        try:
            info = self.client.get_collection(collection_name=collection_name)
            return info.points_count or 0
        except Exception as e:
            logger.error(f"Qdrant count error for {collection_name}: {e}")
            return 0

    def upsert_batch(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Upsert documents in batches of *batch_size*. Each doc dict must have
        keys ``id`` (int), ``vector`` (list[float]) and ``payload`` (dict).
        Returns the number of documents successfully upserted."""
        if self.is_mocked:
            for doc in documents:
                cid = collection_name
                if cid not in self.mock_collections:
                    self.mock_collections[cid] = []
                self.mock_collections[cid] = [
                    item for item in self.mock_collections[cid] if item["id"] != doc["id"]
                ]
                self.mock_collections[cid].append(doc)
            return len(documents)

        total = 0
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            points = []
            for doc in batch:
                vec = doc["vector"]
                if len(vec) != 384:
                    vec = (vec + [0.0] * 384)[:384]
                points.append(
                    qmodels.PointStruct(id=doc["id"], vector=vec, payload=doc["payload"])
                )
            try:
                self.client.upsert(collection_name=collection_name, points=points)
                total += len(points)
            except Exception as e:
                logger.error(
                    f"Qdrant batch upsert error at offset {start}: {e}"
                )
        return total

    def search_similarity(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        if len(query_vector) != 384:
            query_vector = (query_vector + [0.0] * 384)[:384]

        if self.is_mocked:
            docs = self.mock_collections.get(collection_name, [])
            results = []
            for doc in docs:
                v1 = doc["vector"]
                v2 = query_vector
                dot_prod = sum(a * b for a, b in zip(v1, v2))
                norm1 = sum(a * a for a in v1) ** 0.5
                norm2 = sum(b * b for b in v2) ** 0.5
                score = dot_prod / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

                if score >= score_threshold:
                    results.append({
                        "id": doc["id"],
                        "score": score,
                        "payload": doc["payload"]
                    })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]

        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )
            return [
                {"id": hit.id, "score": hit.score, "payload": hit.payload}
                for hit in search_result
            ]
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []
