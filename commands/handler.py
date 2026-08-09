import os
import json
import logging
from typing import Dict, Any, Optional

from commands.service import CommandService, CommandState
from commands.datasets import (
    get_all_datasets, format_dataset_list, view_dataset,
    remove_dataset, search_datasets
)
from commands.ingestion import convert_file_to_dataset, ingest_text_directly
from commands.mining_commands import (
    calculate_grade, calculate_blast, calculate_cost,
    calculate_geology, calculate_fleet, calculate_carbon,
    calculate_water, calculate_geotech, calculate_reserves
)

logger = logging.getLogger("ai_os.commands.handler")

command_service = CommandService()


def handle_command(phone_number: str, text: str, attachments: list = None, **kwargs) -> Optional[Dict[str, Any]]:
    session = command_service.get_session(phone_number)

    if session.state == CommandState.AWAITING_DOCS:
        if text.strip().lower() in ("y", "yes", "done", "finish", "complete"):
            session.reset()
            return {"type": "command_response", "text": "All files processed! Your private datasets are ready. Use /list to see them."}
        if text.strip().lower() in ("n", "no", "cancel"):
            session.reset()
            return {"type": "command_response", "text": "File upload cancelled. Back to normal chat."}
        if text.strip().startswith("/"):
            parsed = command_service.parse_command(text)
            if parsed and parsed["command"] in ("/cancel", "/help", "/list", "/status", "/price", "/search"):
                if parsed["command"] == "/cancel":
                    session.reset()
                    return {"type": "command_response", "text": "File upload cancelled. Back to normal chat."}
                result = command_service.handle(phone_number, text)
                if result:
                    handler = result.get("handler")
                    if handler == "help":
                        return {"type": "command_response", "text": _format_help()}
                    elif handler == "list_datasets":
                        datasets = get_all_datasets()
                        return {"type": "command_response", "text": format_dataset_list(datasets)}
                    elif handler == "status":
                        return {"type": "command_response", "text": _format_status()}
                    elif handler == "price":
                        return {"type": "command_response", "text": _format_price()}
                    elif handler == "search_datasets":
                        query = result.get("args", "").strip()
                        if query:
                            return {"type": "command_response", "text": search_datasets(query)}
        if attachments:
            return _handle_file_upload(phone_number, attachments, session.docs_category)
        return {"type": "command_response", "text": "Send me files (PDF, DOCX, XLSX, CSV, TXT, JSON, images) or type *done* when finished."}

    if session.state == CommandState.AWAITING_REMOVE_CONFIRM:
        if text.strip().lower() in ("y", "yes", "confirm"):
            result = remove_dataset(session.pending_remove_index)
            session.reset()
            return {"type": "command_response", "text": result}
        if text.strip().lower() in ("n", "no", "cancel"):
            session.reset()
            return {"type": "command_response", "text": "Removal cancelled. Dataset kept."}
        return {"type": "command_response", "text": "Reply *yes* to confirm removal or *no* to cancel."}

    result = command_service.handle(phone_number, text, attachments=attachments)
    if result is None:
        return None

    handler = result.get("handler")
    cmd_type = result.get("type")

    if cmd_type == "response":
        return {"type": "command_response", "text": result["text"]}

    if handler == "help":
        return {"type": "command_response", "text": _format_help()}

    elif handler == "docs_start":
        category = result.get("category", "general")
        return {"type": "command_response", "text": _format_docs_start(category)}

    elif handler == "docs_receive":
        if attachments:
            return _handle_file_upload(phone_number, attachments, session.docs_category)
        return {"type": "command_response", "text": "Send me files (PDF, DOCX, XLSX, CSV, TXT, JSON, images) or type *done* when finished."}

    elif handler == "docs_finish":
        session.reset()
        return {"type": "command_response", "text": "All files processed! Use /list to see your datasets."}

    elif handler == "list_datasets":
        datasets = get_all_datasets()
        return {"type": "command_response", "text": format_dataset_list(datasets)}

    elif handler == "remove_start":
        args = result.get("args", "").strip()
        if args and args.isdigit():
            index = int(args)
            datasets = get_all_datasets()
            if 0 <= index < len(datasets):
                d = datasets[index]
                if d["type"] == "built-in":
                    return {"type": "command_response", "text": "Cannot remove built-in datasets. Only private datasets can be removed."}
                session.state = CommandState.AWAITING_REMOVE_CONFIRM
                session.pending_remove_index = index
                return {"type": "command_response", "text": f"Remove dataset `{d['name']}` ({d['size_kb']} KB)?\n\nReply *yes* to confirm or *no* to cancel."}
            return {"type": "command_response", "text": f"Invalid dataset number: {index}. Use /list to see available datasets."}

        datasets = get_all_datasets()
        private = [d for d in datasets if d["type"] == "private"]
        if not private:
            return {"type": "command_response", "text": "No private datasets to remove. Only private datasets can be removed."}
        lines = ["*Select a dataset to remove:*\n"]
        for d in private:
            lines.append(f"  `{d['id']}` {d['name']} ({d['size_kb']} KB)")
        lines.append("\nUse /remove <number> to select one.")
        return {"type": "command_response", "text": "\n".join(lines)}

    elif handler == "remove_confirm":
        result_text = remove_dataset(result["index"])
        return {"type": "command_response", "text": result_text}

    elif handler == "status":
        return {"type": "command_response", "text": _format_status()}

    elif handler == "price":
        return {"type": "command_response", "text": _format_price()}

    elif handler == "search_datasets":
        query = result.get("args", "").strip()
        if not query:
            return {"type": "command_response", "text": "Usage: /search <query>\nExample: /search gold extraction"}
        return {"type": "command_response", "text": search_datasets(query)}

    elif cmd_type == "mining_calc":
        args = result.get("args", "")
        handler_name = result.get("handler", "")
        calc_fn = {
            "grade": calculate_grade,
            "blast": calculate_blast,
            "cost": calculate_cost,
            "geology": calculate_geology,
            "fleet": calculate_fleet,
            "carbon": calculate_carbon,
            "water": calculate_water,
            "geotech": calculate_geotech,
            "reserves": calculate_reserves,
        }.get(handler_name)
        if calc_fn:
            return {"type": "command_response", "text": calc_fn(args)}
        return {"type": "command_response", "text": f"Unknown calculator: {handler_name}. Type /help to see available commands."}

    elif cmd_type == "unknown":
        return {"type": "command_response", "text": result["text"]}

    return {"type": "command_response", "text": "Unknown command. Type /help to see available commands."}


def _handle_file_upload(phone_number: str, attachments: list, category: str) -> Dict[str, Any]:
    results = []
    for att in attachments:
        mime = att.get("mime_type", "")
        name = att.get("name", "unknown_file")
        uri = att.get("storage_uri", "")

        file_bytes = b""
        try:
            storage = kwargs.get("storage_client") if "kwargs" in dir() else None
            if uri.startswith("s3://") or uri.startswith("local://"):
                from storage.minio_client import MinIOClient
                from backend.config import settings
                client = MinIOClient(
                    endpoint=settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY
                )
                file_bytes = client.download_file(uri) or b""
        except Exception as e:
            logger.warning(f"Failed to download {uri}: {e}")

        if not file_bytes:
            results.append(f"- {name}: Could not download file")
            continue

        result = convert_file_to_dataset(
            file_bytes=file_bytes,
            file_name=name,
            mime_type=mime,
            category=category,
            description=f"Uploaded by {phone_number}"
        )

        if result["success"]:
            results.append(f"- {name}: Created dataset with {result['chunks']} chunks ({result['text_length']} chars)")
        else:
            results.append(f"- {name}: {result['error']}")

    return {"type": "command_response", "text": "*File Processing Results:*\n" + "\n".join(results)}


def _format_help() -> str:
    return """*AI Mining OS - Available Commands*

*File Management:*
  /docs [category] - Enter file upload mode
  /list - View all your datasets
  /remove - Remove a private dataset
  /search <query> - Search datasets by name or content

*Quick Info:*
  /price - Current gold and precious metals prices
  /status - System status and dataset stats
  /cancel - Cancel current operation

*Grade Calculators:*
  /grade value <g/t> <tonnes> <recovery%> - Gold value
  /grade cog <mining> <processing> <ga> <price> <recovery%> - Cut-off grade
  /grade conversion <g/t> - g/t to oz/t
  /grade dilution <grade> <dilution%> - Dilution adjustment
  /grade reconciliation <planned> <actual> <planned_t> <actual_t> - Reconciliation

*Blast Design:*
  /blast hole <burden> <spacing> <depth> <dia> - Hole design
  /blast powder <burden> <spacing> <depth> <pf> - Explosive requirement
  /blast timing <holes> <delay_ms> - Blast timing
  /blast vibration <distance> <max_ppv> - Vibration limit

*Cost Analysis:*
  /cost aisc <direct> <indirect> <capex> <tonnes> <oz> - AISC
  /cost per_oz <total> <oz> - Cost per ounce
  /cost per_tonne <total> <tonnes> - Cost per tonne
  /cost comparison <a> <tonnes_a> <b> <tonnes_b> - Compare operations

*Geology:*
  /geology mineral <name> - Mineral properties
  /geology rock <type> - Rock type info
  /geology exploration <region> - Exploration guidance

*Fleet & Equipment:*
  /fleet productivity <bucket> <cycle> <avail%> - Loader productivity
  /fleet trucks <tonnes> <capacity> <distance> <speed> - Truck fleet
  /fleet diesel <hp> <hours> <rate> - Fuel consumption

*Environment & Water:*
  /carbon emission <diesel> <grid_kWh> <travel_km> - CO₂ emissions
  /carbon offset <tonnes> <trees|credits|renewable> - Offset options
  /carbon efficiency <fuel> <tonnes> - Efficiency per tonne
  /water balance <makeup> <recirculated> <evap> <seepage> - Water balance
  /water treatment <flow> <current> <target> - Treatment sizing

*Geotechnical:*
  /geotech rmr <ucs> <rqd> <spacing> <condition> <water> - RMR
  /geotech slope <height> <bench_angle> <overall_angle> - Slope stability
  /geotech pillar <w> <h> <d> <ucs> - Pillar design

*Reserves:*
  /reserves classification <tonnes> <grade> <recovery%> - Classification
  /reserves jorc <measured> <indicated> <inferred> - JORC breakdown

*Chat:*
  /help - Show this help"""


def _format_docs_start(category: str) -> str:
    return f"""*File Upload Mode Active*

Category: *{category}*

Send me files now:
- PDF, DOCX, XLSX documents
- CSV spreadsheets
- TXT, JSON files
- Images (PNG, JPG)

Each file will be:
  1. Downloaded securely
  2. Text extracted (OCR for images)
  3. Converted to a private dataset
  4. Added to your knowledge base

Type *done* when finished uploading.
Type *cancel* to exit without processing."""


def _format_status() -> str:
    datasets = get_all_datasets()
    built_in = [d for d in datasets if d["type"] == "built-in"]
    private = [d for d in datasets if d["type"] == "private"]
    total_kb = sum(d["size_kb"] for d in datasets)

    from backend.config import settings
    from database.postgres_client import PostgresClient
    from vector_db.qdrant_client import VectorDBClient

    pg_status = "Connected"
    qdrant_status = "Connected"

    try:
        pg = PostgresClient(dsn=settings.DATABASE_URL)
        pg_status = "SQLite Fallback" if pg.is_mocked else "Connected"
    except Exception:
        pg_status = "Unavailable"

    try:
        qd = VectorDBClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        qdrant_status = "In-Memory" if qd.is_mocked else "Connected"
    except Exception:
        qdrant_status = "Unavailable"

    return f"""*System Status*

*Datasets:*
  Built-in: {len(built_in)} ({sum(d['size_kb'] for d in built_in):.1f} KB)
  Private: {len(private)} ({sum(d['size_kb'] for d in private):.1f} KB)
  Total: {len(datasets)} ({total_kb:.1f} KB)

*Infrastructure:*
  Database: {pg_status}
  Vector DB: {qdrant_status}
  LLM: {settings.LOCAL_LLM_MODEL}

*Storage:*
  Private datasets: storage/private_datasets/
  Built-in datasets: datasets/"""


def _format_price() -> str:
    try:
        import asyncio
        from research.market_scraper import get_market_scraper
        scraper = get_market_scraper()
        if scraper:
            loop = asyncio.new_event_loop()
            prices = loop.run_until_complete(scraper.get_all_prices())
            loop.close()
            if prices:
                gold = prices.get("gold", {})
                silver = prices.get("silver", {})
                return f"""*Live Market Prices*

*Gold:* ${gold.get('price', 'N/A')}/oz ({gold.get('change', 'N/A')})
*Silver:* ${silver.get('price', 'N/A')}/oz ({silver.get('change', 'N/A')})
Source: {gold.get('source', 'Market data')}

Use /search for more market intelligence."""
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")

    return "*Market prices temporarily unavailable.*\nCheck back later or use /search gold price."
