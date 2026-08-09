import os
import json
import logging
import time
import hashlib
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ai_os.commands.datasets")

DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datasets")
PRIVATE_DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "private_datasets")


def ensure_private_dir():
    os.makedirs(PRIVATE_DATASETS_DIR, exist_ok=True)


def get_all_datasets() -> List[Dict[str, Any]]:
    datasets = []

    for root, dirs, files in os.walk(DATASETS_DIR):
        for f in files:
            if f.endswith(".json") or f.endswith(".csv"):
                path = os.path.join(root, f)
                rel = os.path.relpath(path, DATASETS_DIR)
                size = os.path.getsize(path)
                parts = rel.split(os.sep)
                category = parts[0] if len(parts) > 1 else "root"
                datasets.append({
                    "id": len(datasets),
                    "name": f,
                    "path": rel,
                    "category": category,
                    "size_bytes": size,
                    "size_kb": round(size / 1024, 1),
                    "type": "built-in"
                })

    ensure_private_dir()
    for root, dirs, files in os.walk(PRIVATE_DATASETS_DIR):
        for f in files:
            if f.endswith(".json") or f.endswith(".csv"):
                path = os.path.join(root, f)
                rel = os.path.relpath(path, PRIVATE_DATASETS_DIR)
                size = os.path.getsize(path)
                parts = rel.split(os.sep)
                category = parts[0] if len(parts) > 1 else "private"
                datasets.append({
                    "id": len(datasets),
                    "name": f,
                    "path": rel,
                    "category": category,
                    "size_bytes": size,
                    "size_kb": round(size / 1024, 1),
                    "type": "private"
                })

    return datasets


def format_dataset_list(datasets: List[Dict[str, Any]]) -> str:
    if not datasets:
        return "No datasets found."

    lines = ["*Your Datasets:*\n"]

    built_in = [d for d in datasets if d["type"] == "built-in"]
    private = [d for d in datasets if d["type"] == "private"]

    if built_in:
        lines.append("*Built-in Datasets:*")
        for d in built_in:
            lines.append(f"  `{d['id']}` {d['name']} ({d['size_kb']} KB) - {d['category']}")
        lines.append("")

    if private:
        lines.append("*Your Private Datasets:*")
        for d in private:
            lines.append(f"  `{d['id']}` {d['name']} ({d['size_kb']} KB) - {d['category']}")
        lines.append("")

    lines.append(f"Total: {len(datasets)} datasets ({sum(d['size_kb'] for d in datasets):.1f} KB)")
    lines.append("\nSelect a number to view details, or use /remove <number> to delete.")
    return "\n".join(lines)


def view_dataset(dataset_id: int) -> Optional[str]:
    datasets = get_all_datasets()
    if dataset_id < 0 or dataset_id >= len(datasets):
        return None

    d = datasets[dataset_id]
    if d["type"] == "built-in":
        path = os.path.join(DATASETS_DIR, d["path"])
    else:
        path = os.path.join(PRIVATE_DATASETS_DIR, d["path"])

    if not os.path.exists(path):
        return "Dataset file not found."

    try:
        with open(path) as f:
            data = json.load(f)

        lines = [f"*Dataset: {d['name']}*", f"Category: {d['category']}", f"Type: {d['type']}", f"Size: {d['size_kb']} KB", ""]

        if isinstance(data, dict):
            top_keys = list(data.keys())[:15]
            lines.append(f"Top-level keys ({len(data.keys())} total):")
            for k in top_keys:
                v = data[k]
                if isinstance(v, dict):
                    lines.append(f"  `{k}`: {len(v)} sub-keys")
                elif isinstance(v, list):
                    lines.append(f"  `{k}`: {len(v)} items")
                elif isinstance(v, str):
                    lines.append(f"  `{k}`: {v[:80]}...")
                else:
                    lines.append(f"  `{k}`: {v}")
        elif isinstance(data, list):
            lines.append(f"Array with {len(data)} items")
            if data:
                first = data[0]
                if isinstance(first, dict):
                    lines.append(f"First item keys: {list(first.keys())[:10]}")
                    preview = json.dumps(first, indent=2)[:500]
                    lines.append(f"\nPreview:\n{preview}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error reading dataset: {str(e)[:100]}"


def remove_dataset(dataset_id: int) -> Optional[str]:
    datasets = get_all_datasets()
    if dataset_id < 0 or dataset_id >= len(datasets):
        return "Invalid dataset number."

    d = datasets[dataset_id]

    if d["type"] == "built-in":
        return "Cannot remove built-in datasets. Only private datasets can be removed."

    path = os.path.join(PRIVATE_DATASETS_DIR, d["path"])

    if not os.path.exists(path):
        return "Dataset file not found."

    try:
        os.remove(path)
        parent = os.path.dirname(path)
        if parent != PRIVATE_DATASETS_DIR and not os.listdir(parent):
            os.rmdir(parent)
        return f"Dataset `{d['name']}` has been removed."
    except Exception as e:
        return f"Error removing dataset: {str(e)[:100]}"


def search_datasets(query: str) -> str:
    datasets = get_all_datasets()
    query_lower = query.lower()
    matches = []

    for d in datasets:
        if query_lower in d["name"].lower() or query_lower in d["category"].lower():
            matches.append(d)

    if not matches:
        for d in datasets:
            path = os.path.join(DATASETS_DIR if d["type"] == "built-in" else PRIVATE_DATASETS_DIR, d["path"])
            try:
                with open(path) as f:
                    content = f.read(5000)
                if query_lower in content.lower():
                    matches.append(d)
            except Exception:
                pass

    if not matches:
        return f"No datasets found matching '{query}'."

    lines = [f"*Search results for '{query}':*\n"]
    for m in matches[:10]:
        lines.append(f"  `{m['id']}` {m['name']} ({m['size_kb']} KB) - {m['category']} [{m['type']}]")
    lines.append(f"\nFound {len(matches)} matching datasets.")
    return "\n".join(lines)
