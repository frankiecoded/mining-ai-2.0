import os
import csv
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("ai_os.ingestion")

DATASETS_ROOT = Path(__file__).parent.parent / "datasets"


def _csv_row_to_text(row: Dict[str, str], prefix: str = "") -> str:
    """
    Converts a CSV row dict into a human-readable text chunk suitable for embedding.
    Example: "Production Log for 2026-04-01 at Shaft 2 North: 4200 tons milled, grade 1.72% Cu, recovery 93.8%, concentrate 68.2 tons."
    """
    parts = []
    if prefix:
        parts.append(prefix)
    for key, value in row.items():
        if value and value.strip():
            clean_key = key.replace("_", " ").title()
            parts.append(f"{clean_key}: {value}")
    return ". ".join(parts)


def load_json_dataset(filepath: Path) -> List[Dict[str, Any]]:
    """
    Loads a JSON knowledge base file.
    Expected format: a JSON array of objects, each with at minimum:
      - id: unique identifier
      - title: document title
      - content: full text content
      - tags: list of string tags for categorization
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]
        logger.info(f"Loaded {len(data)} records from {filepath.name}")
        return data
    except Exception as e:
        logger.error(f"Failed to load JSON dataset {filepath}: {e}")
        return []


def load_csv_dataset(filepath: Path) -> List[Dict[str, str]]:
    """
    Loads a CSV file into a list of row dicts.
    Each row becomes a separate document for embedding.
    """
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        logger.info(f"Loaded {len(rows)} rows from {filepath.name}")
        return rows
    except Exception as e:
        logger.error(f"Failed to load CSV dataset {filepath}: {e}")
        return []


def prepare_documents_for_indexing() -> List[Dict[str, Any]]:
    """
    Scans the datasets/ directory tree and prepares all documents for vector indexing.
    Returns a list of documents with:
      - id: unique string ID
      - text: text to embed
      - payload: metadata to store in Qdrant
    """
    from ingestion.embeddings import chunk_text

    documents = []

    # Process all JSON files in datasets/
    for json_file in DATASETS_ROOT.rglob("*.json"):
        category = json_file.parent.name
        records = load_json_dataset(json_file)

        for record in records:
            doc_id = record.get("id", f"{category}_{json_file.stem}_{len(documents)}")
            title = record.get("title", "")
            content = record.get("content", "")
            tags = record.get("tags", [])

            # Chunk long content (1000 chars, 150 overlap — paragraph-aware)
            chunks = chunk_text(content, max_chunk_size=1000, overlap=150)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}" if len(chunks) > 1 else doc_id
                text_to_embed = f"{title}: {chunk}" if title else chunk

                documents.append({
                    "id": chunk_id,
                    "text": text_to_embed,
                    "payload": {
                        "source": "knowledge_base",
                        "category": category,
                        "file": json_file.name,
                        "title": title,
                        "tags": tags,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "content_preview": chunk[:200],
                    }
                })

    # Process all CSV files in datasets/
    for csv_file in DATASETS_ROOT.rglob("*.csv"):
        category = csv_file.parent.name
        stem = csv_file.stem
        rows = load_csv_dataset(csv_file)

        for idx, row in enumerate(rows):
            text = _csv_row_to_text(row, prefix=f"{stem.replace('_', ' ').title()} record")
            doc_id = f"{category}_{stem}_{idx}"

            # Extract date if present
            date_val = row.get("date", "")

            documents.append({
                "id": doc_id,
                "text": text,
                "payload": {
                    "source": "dataset",
                    "category": category,
                    "file": csv_file.name,
                    "record_index": idx,
                    "date": date_val,
                    "row_data": row,
                    "content_preview": text[:200],
                }
            })

    logger.info(f"Prepared {len(documents)} documents for indexing from {DATASETS_ROOT}")
    return documents


def index_documents_to_vector_db(
    vector_client,
    documents: Optional[List[Dict[str, Any]]] = None,
    collection_name: str = "company_knowledge",
    batch_size: int = 64
) -> int:
    """
    Embeds and upserts all prepared documents into the Qdrant vector collection.
    Returns the number of documents successfully indexed.
    """
    from ingestion.embeddings import embed_batch

    if documents is None:
        documents = prepare_documents_for_indexing()

    if not documents:
        logger.warning("No documents to index.")
        return 0

    total_indexed = 0

    for batch_start in range(0, len(documents), batch_size):
        batch = documents[batch_start:batch_start + batch_size]
        texts = [doc["text"] for doc in batch]

        try:
            vectors = embed_batch(texts, batch_size=batch_size)
        except Exception as e:
            logger.error(f"Embedding batch failed at offset {batch_start}: {e}")
            continue

        docs_to_upsert = []
        for doc, vector in zip(batch, vectors):
            doc_id_hash = int(hashlib.md5(str(doc["id"]).encode()).hexdigest()[:8], 16)
            docs_to_upsert.append({
                "id": doc_id_hash,
                "vector": vector,
                "payload": doc["payload"],
            })

        try:
            upserted = vector_client.upsert_batch(
                collection_name=collection_name,
                documents=docs_to_upsert,
                batch_size=100,
            )
            total_indexed += upserted
        except Exception as e:
            logger.error(f"Batch upsert failed at offset {batch_start}: {e}")

        logger.info(
            f"Indexed batch {batch_start // batch_size + 1}/"
            f"{(len(documents) - 1) // batch_size + 1} "
            f"({total_indexed}/{len(documents)} documents)"
        )

    logger.info(f"Indexing complete. {total_indexed} documents indexed into '{collection_name}'.")
    return total_indexed


def run_full_ingestion(vector_client) -> int:
    """
    End-to-end ingestion pipeline:
    1. Prepare documents from all dataset files
    2. Embed and index into Qdrant
    Returns total documents indexed.
    """
    logger.info("=" * 60)
    logger.info("Starting full dataset ingestion pipeline...")
    logger.info("=" * 60)

    documents = prepare_documents_for_indexing()
    logger.info(f"Prepared {len(documents)} documents from datasets/")

    # Index knowledge base documents into company_knowledge collection
    kb_docs = [d for d in documents if d["payload"]["source"] == "knowledge_base"]
    dataset_docs = [d for d in documents if d["payload"]["source"] == "dataset"]

    count_kb = 0
    count_ds = 0

    if kb_docs:
        count_kb = index_documents_to_vector_db(
            vector_client, kb_docs, collection_name="company_knowledge"
        )

    if dataset_docs:
        # Production data goes to production_data collection
        production_docs = [d for d in dataset_docs if d["payload"]["category"] == "production"]
        finance_docs = [d for d in dataset_docs if d["payload"]["category"] == "finance"]
        equipment_docs = [d for d in dataset_docs if d["payload"]["category"] == "equipment"]
        safety_docs = [d for d in dataset_docs if d["payload"]["category"] == "safety"]
        other_docs = [d for d in dataset_docs if d["payload"]["category"] not in
                      ("production", "finance", "equipment", "safety")]

        if production_docs:
            count_ds += index_documents_to_vector_db(
                vector_client, production_docs, collection_name="production_data"
            )
        if finance_docs:
            count_ds += index_documents_to_vector_db(
                vector_client, finance_docs, collection_name="financial_data"
            )
        if equipment_docs:
            count_ds += index_documents_to_vector_db(
                vector_client, equipment_docs, collection_name="company_knowledge"
            )
        if safety_docs:
            count_ds += index_documents_to_vector_db(
                vector_client, safety_docs, collection_name="company_knowledge"
            )
        if other_docs:
            count_ds += index_documents_to_vector_db(
                vector_client, other_docs, collection_name="company_knowledge"
            )

    total = count_kb + count_ds
    logger.info("=" * 60)
    logger.info(f"Ingestion complete. Total indexed: {total} documents")
    logger.info(f"  Knowledge base: {count_kb} documents")
    logger.info(f"  Datasets: {count_ds} documents")
    logger.info("=" * 60)

    return total
