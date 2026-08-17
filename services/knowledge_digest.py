"""
Knowledge Digest Service — Compulsory Dataset Loading System

This service ensures the AI ALWAYS has access to the full content of the most
relevant datasets for every query. Unlike RAG (which returns snippets), this
loads the actual full dataset files based on keyword matching.

Design:
  1. DATASET_REGISTRY maps every dataset file to its topics, keywords, and category
  2. load_relevant_datasets(query) matches a query to relevant datasets
  3. The full content of matched datasets is injected into the system prompt
  4. Compulsory datasets are ALWAYS loaded regardless of the query
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger("ai_os.knowledge_digest")

DATASETS_DIR = Path(__file__).parent.parent / "datasets"

# Compulsory datasets — ALWAYS loaded into context
COMPULSORY_DATASETS = [
    "company/org_structure.json",
    "operations/shift_protocols.json",
    "safety/safety_protocols.json",
    "regulations/mining_regulations.json",
    # Baguley Limited — Company-owned exploration reports (ALWAYS loaded)
    "baguley_limited/ophir_july_2026_report.json",
    "baguley_limited/ophir_june_2026_report.json",
    "baguley_limited/ophir_may_2026_report.json",
    "baguley_limited/ophir_part1_presentation.json",
    "baguley_limited/ophir_part2_presentation.json",
    # Kapoeta — Priority regional data
    "regions/kapoeta_gold.json",
    "regions/kapoeta_climate_exploration.json",
]

# Dataset registry: maps file path to (keywords, category, description)
# Keywords are lowercase. The loader matches query words against these.
DATASET_REGISTRY: Dict[str, Dict] = {
    # GEOLOGY
    "geology/geological_standards.json": {
        "keywords": ["geology", "rock", "mineral", "classification", "alteration", "ore", "deposit", "structural", "fault", "fold", "metamorphic", "igneous", "sedimentary"],
        "category": "geology",
        "description": "Rock classification, mineral identification, alteration minerals, structural geology, ore deposits",
        "priority": 1,
    },
    "geology/gold_geology_exploration.json": {
        "keywords": ["gold", "exploration", "drilling", "sampling", "assay", "resource", "reserve", "grade", "drill", "core", "rc", "diamond", "pathfinder", "arsenic", "antimony", "bismuth"],
        "category": "geology",
        "description": "Gold exploration methods, drilling, sampling, assaying, resource estimation, reserve classification",
        "priority": 1,
    },
    "geology/geotechnical.json": {
        "keywords": ["geotechnical", "slope", "stability", "pit", "wall", "rock mass", "soil", "bearing", "foundation", "tunnel", "underground", "rmi", "rqd", "fracture"],
        "category": "geology",
        "description": "Rock mass classification, slope stability, underground design, soil mechanics",
        "priority": 1,
    },

    # EQUIPMENT
    "equipment/mining_equipment.json": {
        "keywords": ["equipment", "fleet", "excavator", "truck", "haul", "drill", "loader", "conveyor", "pump", "compressor", "cat", "komatsu", "hitachi", "sensor", "maintenance", "oil", "pressure", "temperature", "vibration"],
        "category": "equipment",
        "description": "Mining equipment fleet, sensor readings, maintenance status, equipment specs",
        "priority": 1,
    },
    "equipment/equipment_operations_manual.json": {
        "keywords": ["equipment", "operation", "manual", "haul truck", "excavator", "drill", "loader", "conveyor", "pump", "compressor", "procedure", "startup", "shutdown", "inspection"],
        "category": "equipment",
        "description": "Equipment operations manual — haul trucks, excavators, drills, loaders, conveyors, pumps",
        "priority": 1,
    },
    "equipment/failure_modes.json": {
        "keywords": ["failure", "breakdown", "fault", "malfunction", "diagnostic", "troubleshoot", "repair", "wear", "damage", "overheating", "leak", "vibration", "abnormal"],
        "category": "equipment",
        "description": "Equipment failure modes, diagnostics, troubleshooting for all mining equipment",
        "priority": 2,
    },

    # FINANCE
    "finance/financial_data.json": {
        "keywords": ["finance", "budget", "cost", "revenue", "profit", "loss", "capex", "opex", "procurement", "payroll", "forecast", "kpi", "npv", "irr", "investment"],
        "category": "finance",
        "description": "Financial data — budgets, procurement, revenue, cost of production, capital projects, forecasts",
        "priority": 1,
    },
    "finance/cost_analysis.json": {
        "keywords": ["cost", "analysis", "benchmark", "scenario", "sensitivity", "capital", "operating", "processing", "mining", "labor", "environmental", "infrastructure", "contingency", "aisc", "per ounce"],
        "category": "finance",
        "description": "Cost analysis — capital expenditure, operating costs, benchmarks, scenarios, sensitivity analysis",
        "priority": 1,
    },

    # MARKETS
    "markets/commodity_prices.json": {
        "keywords": ["price", "gold", "silver", "platinum", "palladium", "copper", "nickel", "iron", "lithium", "cobalt", "diamond", "tanzanite", "ruby", "emerald", "tsavorite", "commodity", "market"],
        "category": "markets",
        "description": "Current commodity prices for all precious metals, gemstones, and industrial metals",
        "priority": 1,
    },
    "markets/gold_market_intelligence.json": {
        "keywords": ["gold", "silver", "platinum", "market", "analysis", "etf", "futures", "options", "central bank", "interest rate", "inflation", "geopolitics", "trading", "technical", "fundamental"],
        "category": "markets",
        "description": "Gold market intelligence — supply/demand, central bank buying, ETF flows, technical analysis",
        "priority": 1,
    },
    "markets/historical_prices.json": {
        "keywords": ["historical", "price", "trend", "correlation", "volatility", "monthly", "annual", "macro", "indicator"],
        "category": "markets",
        "description": "Historical price data for all commodities — monthly/quarterly trends and correlations",
        "priority": 2,
    },

    # MINING
    "mining/mine_planning.json": {
        "keywords": ["mine plan", "planning", "pit", "open pit", "underground", "production schedule", "waste", "stripping", "cutback", "phase", "pushback", "haul road", "dump"],
        "category": "mining",
        "description": "Mine planning — open pit methods, underground methods, production scheduling, financial modeling",
        "priority": 1,
    },
    "mining/gold_extraction_processes.json": {
        "keywords": ["extraction", "leach", "heap leach", "cil", "cip", "cyanide", "gravity", "flotation", "recovery", "process", "carbon", "elution", "electrowinning", "smelt", "refractory"],
        "category": "mining",
        "description": "Gold extraction — CIL, gravity, heap leach, flotation, cyanidation, environmental considerations",
        "priority": 1,
    },
    "mining/sops.json": {
        "keywords": ["sop", "procedure", "protocol", "standard", "artisanal", "placer", "diamond", "safety", "processing", "environmental", "equipment"],
        "category": "mining",
        "description": "Standard Operating Procedures — 26 SOPs covering artisanal mining, placer, diamond, safety, processing",
        "priority": 1,
    },
    "mining/gold_safety_environmental.json": {
        "keywords": ["safety", "environmental", "cyanide", "tailings", "water", "air quality", "noise", "waste", "emergency", "incident", "compliance", "training", "monitoring"],
        "category": "mining",
        "description": "Gold mining safety and environmental management — underground/surface safety, cyanide, tailings",
        "priority": 1,
    },

    # OPERATIONS
    "operations/emergency_response.json": {
        "keywords": ["emergency", "evacuation", "fire", "rescue", "medical", "incident", "alarm", "shelter", "first aid", "burns", "crush", "fall", "flood", "collapse"],
        "category": "operations",
        "description": "Emergency response protocols — classification, medical, fire, environmental, evacuation",
        "priority": 1,
    },
    "operations/drilling_blasting.json": {
        "keywords": ["drill", "blast", "explosive", "detonator", "fragmentation", "vibration", "hole", "bench", "pattern", "stemming", "initiation"],
        "category": "operations",
        "description": "Drilling and blasting — blast designs, explosive types, vibration monitoring, fragmentation standards",
        "priority": 1,
    },
    "operations/tailings_management.json": {
        "keywords": ["tailings", "dam", "storage", "waste", "impoundment", "water", "monitoring", "seepage", "stability", "decommission"],
        "category": "operations",
        "description": "Tailings management — storage facility, dam safety, environmental monitoring",
        "priority": 2,
    },
    "operations/water_management.json": {
        "keywords": ["water", "dewatering", "treatment", "balance", "quality", "monitoring", "borehole", "river", "aquifer", "discharge"],
        "category": "operations",
        "description": "Water management — sources, treatment, dewatering, water balance, quality monitoring",
        "priority": 2,
    },
    "operations/supply_chain.json": {
        "keywords": ["supply", "procurement", "logistics", "transport", "customs", "warehouse", "inventory", "import", "export", "freight"],
        "category": "operations",
        "description": "Supply chain — transport routes, customs, procurement, warehousing, logistics",
        "priority": 2,
    },

    # PRODUCTION
    "production/gold_production_data.json": {
        "keywords": ["production", "output", "tonnage", "grade", "recovery", "ounces", "monthly", "quarterly", "annual", "target", "actual", "benchmark"],
        "category": "production",
        "description": "Gold production data — operations, monthly/quarterly data, annual targets, cost benchmarks",
        "priority": 1,
    },
    "production/production_logs.json": {
        "keywords": ["production log", "daily", "shift", "lake victoria", "bulawayo", "merelani", "winza", "voi", "mwadui", "gemstone log"],
        "category": "production",
        "description": "Production logs — gold (Lake Victoria, Bulawayo) and gemstone (Merelani, Winza, Voi, Mwadui)",
        "priority": 1,
    },
    "production/grade_control.json": {
        "keywords": ["grade", "grade control", "blast hole", "sampling", "reconciliation", "resource model", "estimation", "kriging", "idw", "statistics", "qaqc"],
        "category": "production",
        "description": "Grade control — blast hole sampling, resource modeling, grade estimation, reconciliation",
        "priority": 1,
    },
    "production/precious_stones_production.json": {
        "keywords": ["tanzanite", "ruby", "emerald", "diamond", "tsavorite", "gemstone", "gem", "quality", "carat", "clarity", "color"],
        "category": "production",
        "description": "Precious stones production — tanzanite, ruby, emerald, diamond, tsavorite operations",
        "priority": 1,
    },

    # PROCESSING
    "processing/gold_processing_metallurgy.json": {
        "keywords": ["processing", "mill", "grind", "crush", "classification", "flotation", "cyanidation", "cil", "cip", "elution", "electrowinning", "smelt", "refine", "metallurgy", "recovery"],
        "category": "processing",
        "description": "Gold processing metallurgy — grinding, crushing, gravity, flotation, cyanidation, CIL/CIP, smelting",
        "priority": 1,
    },
    "processing/metallurgical_testing.json": {
        "keywords": ["metallurgical", "test", "comminution", "flotation test", "leach", "gravity test", "laboratory", "assay", "bench", "pilot"],
        "category": "processing",
        "description": "Metallurgical testing — comminution, flotation, leaching, gravity, environmental testing",
        "priority": 2,
    },

    # COMMUNITY / ESG
    "community/esg_carbon.json": {
        "keywords": ["esg", "carbon", "emission", "ghg", "renewable", "energy", "biodiversity", "waste", "recycle", "water", "climate", "sustainability"],
        "category": "community",
        "description": "ESG and carbon metrics — emissions, water, waste, biodiversity, targets",
        "priority": 2,
    },
    "community/social_impact.json": {
        "keywords": ["community", "social", "impact", "benefit", "grievance", "stakeholder", "resettlement", "artisanal", "local", "employment", "education", "health"],
        "category": "community",
        "description": "Social impact — community profiles, programs, benefit sharing, grievances, stakeholder management",
        "priority": 2,
    },

    # PRECIOUS STONES
    "precious_stones/gemstones.json": {
        "keywords": ["diamond", "ruby", "emerald", "tanzanite", "tsavorite", "gemstone", "gem", "cut", "clarity", "carat", "color", "jewelry"],
        "category": "precious_stones",
        "description": "Gemstones — diamonds, rubies, emeralds, tanzanite, tsavorite",
        "priority": 1,
    },

    # RARE EARTH
    "rare_earth/rare_earth_metals.json": {
        "keywords": ["rare earth", "ree", "neodymium", "dysprosium", "terbium", "lanthanum", "cerium", "magnet", "battery", "catalyst", "phosphor"],
        "category": "rare_earth",
        "description": "Rare earth elements — 17 elements, deposits, processing, market intelligence",
        "priority": 2,
    },
    "rare_earth/processing_flows.json": {
        "keywords": ["monazite", "bastnasite", "ion clay", "separation", "solvent", "extraction", "rare earth processing"],
        "category": "rare_earth",
        "description": "Rare earth processing — monazite, bastnasite, ion clay flowsheets",
        "priority": 2,
    },

    # REGIONS
    "regions/kapoeta_gold.json": {
        "keywords": ["kapoeta", "south sudan", "didinga", "gold district", "artisanal", "kapoeta east", "kapoeta north", "kapoeta south"],
        "category": "regions",
        "description": "Kapoeta gold district — overview, coordinates, geology, exploration, artisanal mining",
        "priority": 1,
    },
    "regions/kapoeta_climate_exploration.json": {
        "keywords": ["kapoeta", "climate", "rainfall", "temperature", "season", "el nino", "drought", "flood", "humidity", "wind"],
        "category": "regions",
        "description": "Kapoeta/Didinga Hills climate data — monthly/annual normals, trends, projections",
        "priority": 2,
    },
    "regions/regional_geology.json": {
        "keywords": ["south sudan", "kenya", "uganda", "drc", "tanzania", "regional", "geology", "basement", "greenstone", "mobile belt"],
        "category": "regions",
        "description": "Regional geology — South Sudan, Kenya, Uganda, DRC, Tanzania",
        "priority": 1,
    },

    # SOIL
    "soil/soil_geochemistry_data.json": {
        "keywords": ["soil", "geochemistry", "sample", "au", "as", "sb", "bi", "cu", "zn", "pb", "anomaly", "threshold", "ppm"],
        "category": "soil",
        "description": "Soil geochemistry data — Au/As/Sb/Bi/Cu/Zn/Pb measurements and classifications",
        "priority": 1,
    },
    "soil/soil_analysis.json": {
        "keywords": ["soil", "sampling", "rock", "field", "laboratory", "analysis", "technique", "interpretation", "exploration"],
        "category": "soil",
        "description": "Soil and rock sampling protocols, field techniques, laboratory methods, data interpretation",
        "priority": 1,
    },

    # GLOBAL
    "global/mining_hotspots.json": {
        "keywords": ["africa", "hotspot", "producer", "gold producer", "gemstone producer", "rare earth", "investment", "regulation", "supply chain"],
        "category": "global",
        "description": "Mining hotspots — gold, gemstone, rare earth producers in Africa, market analysis",
        "priority": 2,
    },

    # TRAINING
    "training/competency_framework.json": {
        "keywords": ["training", "competency", "certification", "skill", "assessment", "learning", "compliance", " qualification"],
        "category": "training",
        "description": "Competency framework — training programs, certifications, learning pathways",
        "priority": 2,
    },

    # COMPANY / OPERATIONS / SAFETY / REGULATIONS (Compulsory, auto-loaded)
    "company/org_structure.json": {
        "keywords": ["company", "org", "structure", "department", "team", "employee", "management", "hierarchy"],
        "category": "company",
        "description": "Company organizational structure — departments, teams, management hierarchy",
        "priority": 1,
    },
    "operations/shift_protocols.json": {
        "keywords": ["shift", "protocol", "roster", "handover", "rotation", "schedule", "duty", "crew"],
        "category": "operations",
        "description": "Shift protocols — handover procedures, roster management, crew rotation",
        "priority": 1,
    },
    "safety/safety_protocols.json": {
        "keywords": ["safety", "protocol", "ppe", "incident", "hazard", "risk", "emergency", "first aid"],
        "category": "safety",
        "description": "Safety protocols — PPE requirements, hazard identification, incident reporting",
        "priority": 1,
    },
    "regulations/mining_regulations.json": {
        "keywords": ["regulation", "compliance", "licence", "permit", "law", "legal", "environmental", "act"],
        "category": "regulations",
        "description": "Mining regulations — licence requirements, environmental compliance, legal framework",
        "priority": 1,
    },

    # BAGULEY LIMITED — Ophir Company Ltd Exploration Reports (COMPULSORY)
    "baguley_limited/ophir_july_2026_report.json": {
        "keywords": ["ophir", "camp15", "july 2026", "exploration", "trenching", "geological mapping", "alteration", "structural", "quartz veins", "hydrothermal", "gold", "south sudan", "sampson nsiah"],
        "category": "baguley_limited",
        "description": "Ophir Co Ltd — July 2026 exploration report: Camp 15 project, geological/structural mapping, trenching TR001-TR002, 32 samples, 437.8g gold produced, hydrothermal alteration, quartz-vein systems, gold mineralization indicators",
        "priority": 1,
    },
    "baguley_limited/ophir_june_2026_report.json": {
        "keywords": ["ophir", "camp15", "june 2026", "exploration", "sampling", "GPS", "UTM", "SGS laboratory", "artisanal mining", "block 1", "eastern shear zone", "koyokonyo", "73 degrees", "quartz vein", "gold trap", "placer deposit", "laiya basin"],
        "category": "baguley_limited",
        "description": "Ophir Co Ltd — June 2026 exploration report: 135 samples collected, 45 sent to lab, GPS/UTM coordinates for all samples, Block 1 eastern shear zone, artisanal workings, 73-degree structural dips, gold trap sites, placer targets",
        "priority": 1,
    },
    "baguley_limited/ophir_may_2026_report.json": {
        "keywords": ["ophir", "camp15", "may 2026", "exploration", "regional geology", "precambrian", "east african orogen", "mozambique belt", "pan-african", "gneiss", "amphibolite", "gold", "brecciated quartz vein", "2m width", "150m strike", "pyrite", "arsenopyrite", "drill recommendations"],
        "category": "baguley_limited",
        "description": "Ophir Co Ltd — May 2026 exploration report: Regional geology, Precambrian basement, licence SSML04-2024/06/20-09, 67 samples, 2m breccia with 150m strike, 267-319 degree trend, 65-degree SW dip, pyrite/arsenopyrite boxwork, drill recommendations >1 g/t Au",
        "priority": 1,
    },
    "baguley_limited/ophir_part1_presentation.json": {
        "keywords": ["logirim", "chukudum", "gold corridor", "kapoeta", "900 km2", "320 degrees", "colluvial", "alluvial", "eluvial", "placer", "7500 tonnes", "pebble lines", "200m long", "1.5-2m thick", "wash plant", "artisanal miners", "women miners", "women artisanal"],
        "category": "baguley_limited",
        "description": "Ophir Co Ltd — Part 1 Presentation: Logirim-Chukudum Gold Corridor summary, 900km2 licence, 320-degree strike-slip fault, colluvial/alluvial target 20km NW, 7500 tonnes potential tailings, 200m pebble lines, 1.5-2m thick, wash plant testing",
        "priority": 1,
    },
    "baguley_limited/ophir_part2_presentation.json": {
        "keywords": ["pebble lines", "hydraulic traps", "natural riffles", "paystreak", "in-situ gold", "alteration halo", "1000m x 500m", "chlorite", "epidote", "sericite", "potassic", "phyllic", "argillic", "propylitic", "trenching", "trench 0001", "clay alteration", "magnetism", "gold mineralization", "september 2026"],
        "category": "baguley_limited",
        "description": "Ophir Co Ltd — Part 2 Presentation: Pebble line significance, in-situ gold targets 5km+ east, alteration halo 1000m x 500m, alteration zonation model (potassic/phyllic/argillic/propylitic), trench 0001 results, September 2026 plans",
        "priority": 1,
    },
}

# Cache for loaded dataset contents
_dataset_cache: Dict[str, str] = {}
_digest_cache: Optional[str] = None


def _load_dataset_content(file_path: str) -> Optional[str]:
    """Load and return the full text content of a dataset file."""
    if file_path in _dataset_cache:
        return _dataset_cache[file_path]

    full_path = DATASETS_DIR / file_path
    if not full_path.exists():
        logger.warning(f"Dataset file not found: {full_path}")
        return None

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert to readable text
        if isinstance(data, list):
            # Array of records
            parts = []
            for i, record in enumerate(data):
                title = record.get("title", record.get("name", f"Record {i+1}"))
                content = record.get("content", json.dumps(record, indent=2))
                parts.append(f"[{title}]\n{content}")
            text = "\n\n".join(parts)
        elif isinstance(data, dict):
            # Structured object — convert to readable format
            parts = []
            for key, value in data.items():
                if key in ("title", "version", "last_updated", "description", "metadata"):
                    continue  # Skip metadata keys
                if isinstance(value, dict):
                    sub_parts = []
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (list, dict)):
                            sub_parts.append(f"  {sub_key}: {json.dumps(sub_value, indent=4)}")
                        else:
                            sub_parts.append(f"  {sub_key}: {sub_value}")
                    parts.append(f"{key}:\n" + "\n".join(sub_parts))
                elif isinstance(value, list):
                    parts.append(f"{key}: {json.dumps(value, indent=2)}")
                else:
                    parts.append(f"{key}: {value}")
            text = "\n\n".join(parts)
        else:
            text = str(data)

        _dataset_cache[file_path] = text
        return text

    except Exception as e:
        logger.error(f"Error loading dataset {file_path}: {e}")
        return None


def _match_query_to_datasets(query: str) -> List[Tuple[str, int, str]]:
    """
    Match a user query to relevant datasets.
    Returns list of (file_path, priority, description) sorted by relevance.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    # Remove common stop words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "shall", "can", "to", "of", "in", "for",
                  "on", "with", "at", "by", "from", "as", "into", "about", "this",
                  "that", "these", "those", "it", "its", "and", "or", "but", "not",
                  "what", "how", "when", "where", "who", "which", "tell", "me",
                  "give", "show", "i", "my", "you", "your", "we", "our", "they"}
    query_words -= stop_words

    matches = []
    for file_path, meta in DATASET_REGISTRY.items():
        keywords = meta["keywords"]
        priority = meta["priority"]
        description = meta["description"]

        # Count matching keywords
        score = 0
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Exact word match
            if keyword_lower in query_words:
                score += 3
            # Partial match (keyword is contained in query)
            elif keyword_lower in query_lower:
                score += 2
            # Query word matches start of keyword
            for qw in query_words:
                if qw.startswith(keyword_lower[:4]) or keyword_lower.startswith(qw[:4]):
                    score += 1

        if score > 0:
            matches.append((file_path, priority, description, score))

    # Sort by score (desc), then priority (asc = higher priority first)
    matches.sort(key=lambda x: (-x[3], x[1]))
    return [(m[0], m[1], m[2]) for m in matches]


def load_relevant_datasets(query: str, max_chars: int = 25000) -> str:
    """
    Load the full content of relevant datasets for a query.
    Always includes compulsory datasets.
    Returns a formatted string to inject into the system prompt.
    """
    sections = []

    # 1. Always load compulsory datasets
    compulsory_content = []
    for ds_path in COMPULSORY_DATASETS:
        content = _load_dataset_content(ds_path)
        if content:
            meta = DATASET_REGISTRY.get(ds_path, {})
            desc = meta.get("description", ds_path)
            compulsory_content.append(f"### {desc} (Source: {ds_path})\n{content[:3000]}")

    if compulsory_content:
        sections.append("## COMPULSORY REFERENCE DATA\nAlways use this data when answering questions about these topics:\n\n" + "\n\n".join(compulsory_content))

    # 2. Load query-matched datasets
    matched = _match_query_to_datasets(query)
    total_chars = sum(len(s) for s in sections)
    matched_content = []

    for ds_path, priority, description in matched:
        if ds_path in COMPULSORY_DATASETS:
            continue  # Already loaded
        if total_chars >= max_chars:
            break

        content = _load_dataset_content(ds_path)
        if content:
            # Truncate to fit within budget
            remaining = max_chars - total_chars
            truncated = content[:remaining]
            matched_content.append(f"### {description} (Source: {ds_path})\n{truncated}")
            total_chars += len(truncated)

    if matched_content:
        sections.append("## RELEVANT DATASET CONTENT\nLoaded based on your question — use this data to answer:\n\n" + "\n\n".join(matched_content))

    if not sections:
        return ""

    result = "\n\n".join(sections)
    logger.info(f"Loaded {len(matched)} matched datasets + {len(COMPULSARY_DATASETS)} compulsory for query: {query[:80]}...")
    return result


def _get_dataset_summary(file_path: str) -> str:
    """Generate a concise summary of a dataset file's contents."""
    full_path = DATASETS_DIR / file_path
    if not full_path.exists():
        return ""

    cache_key = f"summary_{file_path}"
    if cache_key in _dataset_cache:
        return _dataset_cache[cache_key]

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        summary_parts = []

        if isinstance(data, list):
            n = len(data)
            if n > 0:
                first = data[0]
                keys = [k for k in first.keys() if k not in ("id", "category", "last_reviewed", "revision")]
                summary_parts.append(f"{n} records with fields: {', '.join(keys[:8])}")
                titles = [r.get("title", "") for r in data[:5] if r.get("title")]
                if titles:
                    summary_parts.append(f"Topics: {'; '.join(titles[:5])}")

        elif isinstance(data, dict):
            top_keys = [k for k in data.keys() if k not in ("title", "version", "last_updated", "description", "metadata")]
            if top_keys:
                summary_parts.append(f"Sections: {', '.join(top_keys[:10])}")
            desc = data.get("description", "")
            if desc:
                summary_parts.append(desc[:200])
            total_items = 0
            for key in top_keys[:10]:
                val = data[key]
                if isinstance(val, list):
                    total_items += len(val)
                elif isinstance(val, dict):
                    total_items += len(val)
            if total_items > 0:
                summary_parts.append(f"~{total_items} data points")

        summary = " | ".join(summary_parts) if summary_parts else "Structured mining data"
        _dataset_cache[cache_key] = summary
        return summary

    except Exception:
        return "Structured mining data"


def get_dataset_digest() -> str:
    """
    Get a pre-computed digest of ALL datasets — a concise summary of every file
    so the AI always knows what information exists and where to find it.
    This is ALWAYS injected into the system prompt (~2-3KB).
    """
    global _digest_cache
    if _digest_cache:
        return _digest_cache

    lines = [
        "## COMPLETE COMPANY DATA INDEX — ALWAYS AVAILABLE",
        "You have access to the following authoritative company datasets.",
        "Use this index to know WHAT data exists and WHERE to find it.",
        "For detailed information, use the load_knowledge_base_file tool to load the full dataset.",
        "",
        "### COMPULSORY DATASETS (always loaded in full for every query):",
    ]

    for ds_path in COMPULSORY_DATASETS:
        meta = DATASET_REGISTRY.get(ds_path, {})
        desc = meta.get("description", ds_path)
        summary = _get_dataset_summary(ds_path)
        lines.append(f"- **{ds_path}**: {desc}")
        if summary:
            lines.append(f"  {summary}")
        lines.append("")

    lines.append("### ALL OTHER DATASETS (loaded on demand based on your question):")
    lines.append("")

    # Group by category
    categories = {}
    for ds_path, meta in DATASET_REGISTRY.items():
        if ds_path in COMPULSORY_DATASETS:
            continue
        cat = meta.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((ds_path, meta))

    for cat, datasets in sorted(categories.items()):
        lines.append(f"**{cat.upper()}:**")
        for ds_path, meta in sorted(datasets, key=lambda x: x[1].get("priority", 9)):
            desc = meta.get("description", ds_path)
            keywords = meta.get("keywords", [])[:6]
            summary = _get_dataset_summary(ds_path)
            lines.append(f"  - {ds_path}: {desc}")
            if summary:
                lines.append(f"    {summary}")
            lines.append(f"    Keywords: {', '.join(keywords)}")
        lines.append("")

    _digest_cache = "\n".join(lines)
    return _digest_cache


def clear_cache():
    """Clear the dataset cache. Call after new datasets are uploaded."""
    global _dataset_cache, _digest_cache
    _dataset_cache.clear()
    _digest_cache = None
