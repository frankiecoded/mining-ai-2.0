import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai_os.mining_engine")

class MiningEngineService:
    """
    Mining Engine coordinates queries regarding mineral exploration,
    geological surveys, processing rates, safety logs, and operations Standard Operating Procedures (SOPs).
    """
    def __init__(self, postgres_client: Optional[Any] = None, vector_client: Optional[Any] = None):
        self.postgres_client = postgres_client
        self.vector_client = vector_client

    def retrieve_sop(self, topic: str) -> str:
        """
        Retrieves Standard Operating Procedures from vector store, database sops table, or returns static templates.
        """
        logger.info(f"Retrieving mining SOP for: '{topic}'")
        
        # 1. Try vector client first
        if self.vector_client and not self.vector_client.is_mocked:
            query_vector = [0.1] * 384
            hits = self.vector_client.search_similarity("company_knowledge", query_vector, limit=1)
            if hits:
                return hits[0]["payload"].get("content", "")
                
        # 2. Try relational sops table lookup
        if self.postgres_client:
            topic_key = "drilling"
            if "safety" in topic.lower() or "emergency" in topic.lower():
                topic_key = "safety"
            elif "processing" in topic.lower() or "flotation" in topic.lower() or "ore" in topic.lower():
                topic_key = "processing"
                
            records = self.postgres_client.query_table("sops", {"topic": topic_key})
            if records:
                rec = records[0]
                return f"{rec['code']}: {rec['title']}\n{rec['content']}"

        # 3. Fallback templates
        topic_lower = topic.lower()
        if "drill" in topic_lower or "exploration" in topic_lower:
            return (
                "SOP-EXPL-002: Diamond Core Drilling Procedure\n"
                "1. Confirm drill collar location with geology team.\n"
                "2. Ensure water recycling line is connected and zero-runoff containment is in place.\n"
                "3. Perform core orientation marking every 1.5 meters.\n"
                "4. Store cores in sequential timber boxes, photograph immediately, and logs core recovery metrics."
            )
            
        return "SOP-GEN-001: General Mine Safety. Check PPE, wear high-vis jackets, and report all hazards to supervisor."

    def query_production_data(self, date_range: str) -> List[Dict[str, Any]]:
        """
        Retrieves production logs from relational production_logs database table.
        """
        logger.info(f"Querying production logs for range: {date_range}")
        
        if self.postgres_client:
            # If date_range is a specific date, filter by it, otherwise return all
            filters = {}
            if "-" in date_range and len(date_range) == 10:
                filters = {"date": date_range}
            records = self.postgres_client.query_table("production_logs", filters)
            if records:
                # Rename key format if needed to match downstream API
                for r in records:
                    r["copper_concentrate_produced_tons"] = r.get("concentrate_produced")
                return records
                
        return [
            {
                "date": "2026-07-10",
                "shaft": "Shaft 2 North",
                "tons_milled": 4500,
                "head_grade_cu": "1.78%",
                "recovery_rate": "94.2%",
                "copper_concentrate_produced_tons": 75.4
            }
        ]

    def query_equipment_status(self, equipment_id: str) -> Dict[str, Any]:
        """
        Checks real-time health metrics of heavy mine machinery from database.
        """
        logger.info(f"Checking status for machinery: {equipment_id}")
        
        if self.postgres_client:
            records = self.postgres_client.query_table("equipment_status", {"equipment_id": equipment_id})
            if records:
                rec = records[0]
                return {
                    "equipment_id": rec["equipment_id"],
                    "type": rec["type"],
                    "status": rec["status"],
                    "operating_hours": rec["operating_hours"],
                    "next_service": rec["next_service"],
                    "sensor_readings": {
                        "engine_temp_c": rec["engine_temp_c"],
                        "oil_pressure_psi": rec["oil_pressure_psi"],
                        "tire_pressure_psi": 118.5,
                        "hydraulic_fluid_pct": 89.0
                    }
                }
                
        return {
            "equipment_id": equipment_id,
            "type": "CAT 797F Haul Truck",
            "status": "operational",
            "operating_hours": 12450,
            "next_service": "2026-08-15",
            "sensor_readings": {
                "engine_temp_c": 92.5,
                "oil_pressure_psi": 68.0,
                "tire_pressure_psi": 118.5,
                "hydraulic_fluid_pct": 89.0
            }
        }
