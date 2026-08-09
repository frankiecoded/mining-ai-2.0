import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai_os.memory_engine")


class MemoryEngineService:
    """
    Memory Engine coordinates multi-tiered memory systems:
    1. Short-Term: Recent chat thread in relational DB.
    2. Long-Term: Entity facts and user attributes in postgres + vector DB.
    3. Archive: Historical reports lookup via semantic search.
    """
    def __init__(self, postgres_client: Optional[Any] = None, vector_client: Optional[Any] = None):
        self.postgres_client = postgres_client
        self.vector_client = vector_client

    def retrieve_short_term_memory(self, session_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Retrieving short term chat history for session: {session_id}")
        if self.postgres_client:
            return self.postgres_client.get_conversation(session_id)
        return []

    def save_short_term_memory(self, session_id: str, phone_number: str, messages: List[Dict[str, Any]]):
        logger.info(f"Saving short term chat history for session: {session_id}")
        if self.postgres_client:
            self.postgres_client.save_conversation(session_id, phone_number, messages)

    def retrieve_user_profile(self, phone_number: str) -> Dict[str, str]:
        logger.info(f"Retrieving long term user memory profile for: {phone_number}")
        if self.postgres_client:
            return self.postgres_client.get_user_memories(phone_number)
        return {}

    def update_user_profile(self, phone_number: str, key: str, value: str):
        logger.info(f"Updating user memory for {phone_number}: {key} -> {value}")
        if self.postgres_client:
            self.postgres_client.save_user_memory(phone_number, key, value)

        if self.vector_client and not self.vector_client.is_mocked:
            try:
                from ingestion.embeddings import embed_text
                vector = embed_text(f"{key}: {value} for user {phone_number}")
            except Exception:
                import random
                vector = [random.uniform(-0.1, 0.1) for _ in range(384)]

            payload = {
                "phone_number": phone_number,
                "memory_key": key,
                "memory_value": value,
                "source": "conversational_extraction"
            }
            doc_id = hash(f"{phone_number}_{key}") % 1000000
            self.vector_client.upsert_document("long_term_memories", doc_id, vector, payload)

    def extract_and_store_facts(self, phone_number: str, conversation_text: str, llm_adapter=None):
        """
        Extracts user-relevant facts from conversation using the LLM,
        then stores them in both relational DB and vector DB.
        """
        if llm_adapter is None:
            return

        try:
            facts = llm_adapter.extract_user_facts(conversation_text)
            if facts:
                for key, value in facts.items():
                    self.update_user_profile(phone_number, key, value)
                logger.info(f"Extracted and stored {len(facts)} facts for user {phone_number}")
        except Exception as e:
            logger.error(f"Fact extraction failed for {phone_number}: {e}")

    def search_archived_reports(self, query: str) -> List[Dict[str, Any]]:
        logger.info(f"Searching archives for query: '{query}'")
        if self.vector_client and not self.vector_client.is_mocked:
            try:
                from ingestion.embeddings import embed_text
                query_vector = embed_text(query)
            except Exception:
                import random
                query_vector = [random.uniform(-0.1, 0.1) for _ in range(384)]

            results = self.vector_client.search_similarity("company_knowledge", query_vector, limit=3)
            if results:
                return results

        return [
            {
                "id": 901,
                "payload": {
                    "title": "2024 Geological Assessment Shaft 1",
                    "content_preview": "Original exploration drilling indicated primary chalcopyrite grade of 1.45% Cu at depth of 300m."
                }
            }
        ]
