import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai_os.finance_engine")

class FinanceEngineService:
    """
    Finance Engine coordinates querying and updating financial accounts,
    budgets, payroll ledgers, audits, taxes, and procurement pipelines.
    """
    def __init__(self, postgres_client: Optional[Any] = None):
        self.postgres_client = postgres_client

    def get_budget_vs_actual(self, department: str, fiscal_year: str = "2026") -> Dict[str, Any]:
        """
        Retrieves budget allocation vs actual spend logs from database department_budgets table.
        """
        logger.info(f"Retrieving budget analysis for {department} - FY{fiscal_year}")
        
        if self.postgres_client:
            records = self.postgres_client.query_table("department_budgets", {"department": department.lower()})
            if records:
                rec = records[0]
                return {
                    "department": rec["department"],
                    "fiscal_year": fiscal_year,
                    "budget_allocated": rec["allocated"],
                    "actual_spend": rec["spent"],
                    "variance": rec["variance"],
                    "status": rec["status"]
                }
                
        # Simulated financial records fallback
        data = {
            "exploration": {
                "budget_allocated": 15000000.0,
                "actual_spend": 12850000.0,
                "variance": 2150000.0,
                "status": "under_budget"
            },
            "operations": {
                "budget_allocated": 45000000.0,
                "actual_spend": 46200000.0,
                "variance": -1200000.0,
                "status": "over_budget"
            },
            "environmental": {
                "budget_allocated": 5000000.0,
                "actual_spend": 4300000.0,
                "variance": 700000.0,
                "status": "under_budget"
            }
        }
        
        dept_key = department.lower()
        if dept_key in data:
            return {
                "department": department,
                "fiscal_year": fiscal_year,
                **data[dept_key]
            }
            
        return {
            "department": department,
            "fiscal_year": fiscal_year,
            "budget_allocated": 10000000.0,
            "actual_spend": 9800000.0,
            "variance": 200000.0,
            "status": "on_track"
        }

    def get_payroll_summary(self, month: str = "2026-06") -> Dict[str, Any]:
        """
        Retrieves general company payroll figures.
        """
        logger.info(f"Retrieving payroll report for: {month}")
        return {
            "month": month,
            "total_employees": 1240,
            "gross_payroll": 4850000.0,
            "tax_withheld": 1250000.0,
            "benefits_cost": 650000.0,
            "net_paid": 2950000.0
        }

    def submit_procurement_request(self, requested_by: str, item_description: str, cost: float) -> Dict[str, Any]:
        """
        Submits and logs procurement requests.
        Requires logging in the relational DB.
        """
        logger.info(f"Submitting procurement order: '{item_description}' by {requested_by} costing ${cost}")
        
        status = "pending_approval" if cost > 10000.0 else "approved"
        
        # Log to PostgreSQL if active
        task_id = -1
        if self.postgres_client:
            task_desc = f"Procurement Request: {item_description} (${cost}) - {requested_by}"
            task_id = self.postgres_client.create_task(
                description=task_desc,
                assigned_to="Finance Manager"
            )
            # Log audit
            self.postgres_client.log_audit(
                phone_number=None,
                action="PROCUREMENT_REQUESTED",
                details={"item": item_description, "cost": cost, "task_id": task_id, "status": status}
            )
            
        return {
            "procurement_id": task_id if task_id != -1 else 101,
            "item": item_description,
            "cost": cost,
            "status": status,
            "requires_cfo_signoff": cost > 50000.0
        }
