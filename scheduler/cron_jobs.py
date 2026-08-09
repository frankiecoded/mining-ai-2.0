import logging
from datetime import datetime
from typing import Optional, Any
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger("ai_os.scheduler")

class OperatingSystemScheduler:
    """
    Manages background tasks, periodic telemetry monitoring,
    automated reports scheduling, and proactive compliance alerts.
    """
    def __init__(self, mining_service: Optional[Any] = None, finance_service: Optional[Any] = None, gpu_manager: Optional[Any] = None):
        self.scheduler = BackgroundScheduler()
        self.mining_service = mining_service
        self.finance_service = finance_service
        self.gpu_manager = gpu_manager
        
    def start(self):
        """
        Starts the background scheduler thread.
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Background Scheduler started.")
            self.register_default_jobs()

    def shutdown(self):
        """
        Stops the scheduler.
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Background Scheduler stopped.")

    def register_default_jobs(self):
        """
        Registers periodic checks (SOP compliance, payroll checks, telemetry anomalies).
        """
        # Job 1: Monitor mine equipment telemetry every hour
        self.scheduler.add_job(
            func=self.check_equipment_alerts,
            trigger="interval",
            hours=1,
            id="equipment_monitoring",
            replace_existing=True
        )
        
        # Job 2: Generate production report daily
        self.scheduler.add_job(
            func=self.generate_daily_production_summary,
            trigger="cron",
            hour=18,  # 6 PM every day
            minute=0,
            id="daily_production_report",
            replace_existing=True
        )
        
        # Job 3: Monitor GPU VM idle timeout every minute
        if self.gpu_manager:
            self.scheduler.add_job(
                func=self.check_gpu_idle_timeout,
                trigger="interval",
                minutes=1,
                id="gpu_idle_monitoring",
                replace_existing=True
            )
            logger.info("Registered GPU VM idle timeout monitoring job (1 minute intervals).")
        
        logger.info("Registered default periodic cron jobs.")

    def check_gpu_idle_timeout(self):
        """
        Periodically checks if the GPU VM has been idle past the threshold.
        """
        logger.info("Scheduled Job: Checking GPU VM idle state...")
        if self.gpu_manager:
            self.gpu_manager.check_idle_shutdown()

    def check_equipment_alerts(self):
        """
        Checks telemetry parameters for anomalies.
        """
        logger.info("Scheduled Job: Checking equipment telemetry metrics...")
        if self.mining_service:
            # Query status of a core haul truck
            status = self.mining_service.query_equipment_status("truck_TRK-88")
            temp = status["sensor_readings"]["engine_temp_c"]
            if temp > 90.0:
                logger.warning(f"[ALERT] Haul truck TRK-88 engine temperature high: {temp}C!")

    def generate_daily_production_summary(self):
        """
        Triggers daily production report compilation.
        """
        logger.info("Scheduled Job: Auto-generating daily production report...")
        if self.mining_service:
            today_str = datetime.now().strftime("%Y-%m-%d")
            records = self.mining_service.query_production_data(today_str)
            logger.info(f"Production summary compiled: processed {len(records)} active shafts.")
            
    def add_custom_alert(self, job_id: str, minutes: int, func_to_run: Any):
        """
        Allows dynamically scheduling a future task/alert.
        """
        logger.info(f"Scheduling custom job '{job_id}' to run in {minutes} minutes.")
        self.scheduler.add_job(
            func=func_to_run,
            trigger="interval",
            minutes=minutes,
            id=job_id,
            replace_existing=True
        )
