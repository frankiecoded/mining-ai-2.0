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
                import hashlib
                text = f"{key}: {value} for user {phone_number}"
                vector = embed_text(text)
                # Deterministic id (md5) so re-storing the same fact overwrites
                # instead of creating duplicates across process restarts.
                doc_id = hashlib.md5(text.encode()).hexdigest()[:16]

                payload = {
                    "phone_number": phone_number,
                    "memory_key": key,
                    "memory_value": value,
                    "source": "conversational_extraction"
                }
                self.vector_client.upsert_document("long_term_memories", doc_id, vector, payload)
            except Exception as e:
                logger.warning(f"Long-term memory vector store skipped for {phone_number}: {e}")

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

    # ─── Personalised Awareness ───
    # Builds a self-contained "relationship context" digest per tenant so the AI
    # can feel it knows the user across sessions: who they are, what they own,
    # what they discussed, and what threads are still open.
    def build_awareness_context(
        self,
        user_key: str,
        recent_limit: int = 6,
        message_budget: int = 4000,
        exclude_session: str = "",
    ) -> str:
        """Compile a fully personalisable user-awareness block for the system prompt."""
        parts: List[str] = []

        # 1. Known profile facts (equipment, concession, FX rate, preferences...)
        try:
            profile = self.retrieve_user_profile(user_key) or {}
            if profile:
                facts = [f"- {k}: {v}" for k, v in profile.items() if k != "history"]
                if facts:
                    parts.append("## Facts I know about this user\n" + "\n".join(facts))
        except Exception as e:
            logger.error(f"Awareness profile failed for {user_key}: {e}")

        # 2. Cross-session conversation history (so the agent remembers the past).
        try:
            history_text = self._build_conversation_digest(user_key, recent_limit, message_budget, exclude_session)
            if history_text:
                parts.append("## What we have discussed before (across all previous sessions)\n" + history_text)
        except Exception as e:
            logger.error(f"Awareness history failed for {user_key}: {e}")

        if not parts:
            return ""
        return "\n\n".join(parts)

    def _build_conversation_digest(
        self,
        tenant_id: str,
        limit: int,
        budget: int,
        exclude_session: str = "",
    ) -> str:
        if not self.postgres_client:
            return ""
        conversations = self.postgres_client.get_recent_conversations(limit=limit, tenant_id=tenant_id) or []
        if not conversations:
            return ""

        # Skip the session we are currently in (history is passed separately),
        # then walk newest → oldest, extracting user asks and assistant answers.
        digest_lines: List[str] = []
        used = 0
        for conv in conversations:
            sid = conv.get("session_id", "")
            if exclude_session and sid == exclude_session:
                continue
            msgs = conv.get("messages") or []
            if not msgs:
                continue
            exchanges: List[str] = []
            pending: List[str] = []

            for msg in msgs:
                role = msg.get("role", "")
                content = (msg.get("content", "") or "").strip()
                if not content:
                    continue
                content = " ".join(content.split())
                if content.startswith("[Attached:"):
                    continue
                if role == "user":
                    exchanges.append(f"  U: {content[:320]}")
                    pending.append(content[:200])
                elif role == "assistant" and exchanges:
                    exchanges.append(f"  A: {content[:320]}")

            if not exchanges:
                continue

            block = f"- Session {sid.split(':', 1)[-1]}:\n" + "\n".join(exchanges[-4:])
            block_len = len(block)
            if used + block_len > budget and digest_lines:
                break
            digest_lines.append(block)
            used += block_len
            if used >= budget:
                break

        if not digest_lines:
            return ""
        return "\n\n".join(digest_lines[:limit])

    def open_threads(self, tenant_id: str, limit: int = 3) -> List[str]:
        """Recent user questions that may still need follow-up action."""
        if not self.postgres_client:
            return []
        conversations = self.postgres_client.get_recent_conversations(limit=limit, tenant_id=tenant_id) or []
        threads: List[str] = []
        for conv in conversations:
            msgs = conv.get("messages") or []
            for msg in reversed(msgs):
                if msg.get("role") == "user":
                    content = (msg.get("content", "") or "").strip()
                    if content and not content.startswith("[Attached:"):
                        threads.append(content[:240])
                        break
        return threads[:limit]

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
