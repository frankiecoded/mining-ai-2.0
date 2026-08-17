"""
Anomaly Detection Engine for Mining Operations
Detects unusual patterns in production, safety, equipment, and financial data.
Uses statistical methods and pattern recognition for early warning.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    PRODUCTION_SPIKE = "production_spike"
    PRODUCTION_DROP = "production_drop"
    EQUIPMENT_DEGRADATION = "equipment_degradation"
    SAFETY_VIOLATION = "safety_violation"
    COST_ANOMALY = "cost_anomaly"
    GRADE_VARIATION = "grade_variation"
    ENERGY_CONSUMPTION = "energy_consumption"
    WEATHER_IMPACT = "weather_impact"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    id: str
    type: AnomalyType
    severity: Severity
    title: str
    description: str
    metric_name: str
    current_value: float
    expected_value: float
    deviation_percent: float
    detected_at: datetime
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class MetricThreshold:
    name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warning_threshold: float = 2.0
    critical_threshold: float = 3.0
    unit: str = ""
    description: str = ""


class AnomalyDetector:
    """Detects anomalies in mining operation data using statistical analysis."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics_history: Dict[str, deque] = {}
        self.thresholds: Dict[str, MetricThreshold] = {}
        self.anomalies: List[Anomaly] = []
        self._anomaly_counter = 0
        self._setup_default_thresholds()

    def _setup_default_thresholds(self):
        """Define default thresholds for common mining metrics."""
        defaults = [
            MetricThreshold("gold_grade", min_value=0.0, max_value=100.0,
                          warning_threshold=2.0, critical_threshold=3.0,
                          unit="g/t", description="Gold grade in grams per tonne"),
            MetricThreshold("tonnage_mined", min_value=0, max_value=100000,
                          warning_threshold=2.5, critical_threshold=3.5,
                          unit="tonnes", description="Daily tonnes mined"),
            MetricThreshold("tonnage_milled", min_value=0, max_value=100000,
                          warning_threshold=2.5, critical_threshold=3.5,
                          unit="tonnes", description="Daily tonnes milled"),
            MetricThreshold("recovery_rate", min_value=0, max_value=100,
                          warning_threshold=2.0, critical_threshold=3.0,
                          unit="%", description="Metallurgical recovery rate"),
            MetricThreshold("water_usage", min_value=0, max_value=1000000,
                          warning_threshold=2.5, critical_threshold=3.5,
                          unit="m3", description="Daily water consumption"),
            MetricThreshold("energy_consumption", min_value=0, max_value=100000,
                          warning_threshold=2.0, critical_threshold=3.0,
                          unit="kWh", description="Daily energy consumption"),
            MetricThreshold("diesel_consumption", min_value=0, max_value=50000,
                          warning_threshold=2.5, critical_threshold=3.5,
                          unit="litres", description="Daily diesel consumption"),
            MetricThreshold("safety_incidents", min_value=0, max_value=100,
                          warning_threshold=1.5, critical_threshold=2.5,
                          unit="count", description="Safety incident count"),
            MetricThreshold("equipment_uptime", min_value=0, max_value=100,
                          warning_threshold=2.0, critical_threshold=3.0,
                          unit="%", description="Equipment availability"),
            MetricThreshold("cost_per_ounce", min_value=0, max_value=5000,
                          warning_threshold=2.0, critical_threshold=3.0,
                          unit="USD/oz", description="All-in sustaining cost"),
        ]
        for threshold in defaults:
            self.thresholds[threshold.name] = threshold

    def add_threshold(self, threshold: MetricThreshold):
        """Add or update a metric threshold."""
        self.thresholds[threshold.name] = threshold

    def record_metric(self, name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a metric value for anomaly detection."""
        if name not in self.metrics_history:
            self.metrics_history[name] = deque(maxlen=self.window_size)

        self.metrics_history[name].append({
            "value": value,
            "timestamp": timestamp or datetime.now()
        })

        anomalies = self._detect_anomalies(name, value)
        for anomaly in anomalies:
            self.anomalies.append(anomaly)
            logger.warning(f"Anomaly detected: {anomaly.title} - {anomaly.description}")

        return anomalies

    def _detect_anomalies(self, metric_name: str, current_value: float) -> List[Anomaly]:
        """Detect anomalies for a given metric."""
        anomalies = []
        history = self.metrics_history.get(metric_name, deque())

        if len(history) < 10:
            return anomalies

        values = [h["value"] for h in history]
        mean = statistics.mean(values[:-1])
        stdev = statistics.stdev(values[:-1]) if len(values) > 1 else 0.001

        if stdev == 0:
            stdev = 0.001

        z_score = (current_value - mean) / stdev

        threshold = self.thresholds.get(metric_name)
        warning_threshold = threshold.warning_threshold if threshold else 2.0
        critical_threshold = threshold.critical_threshold if threshold else 3.0

        if abs(z_score) >= critical_threshold:
            severity = Severity.CRITICAL
        elif abs(z_score) >= warning_threshold:
            severity = Severity.HIGH
        elif abs(z_score) >= 1.5:
            severity = Severity.MEDIUM
        else:
            return anomalies

        deviation_percent = ((current_value - mean) / mean * 100) if mean != 0 else 0

        anomaly_type = self._determine_anomaly_type(metric_name, current_value, mean)

        self._anomaly_counter += 1
        anomaly = Anomaly(
            id=f"anomaly_{self._anomaly_counter:06d}",
            type=anomaly_type,
            severity=severity,
            title=f"{metric_name.replace('_', ' ').title()} Anomaly Detected",
            description=self._generate_description(metric_name, current_value, mean, z_score, deviation_percent),
            metric_name=metric_name,
            current_value=current_value,
            expected_value=mean,
            deviation_percent=deviation_percent,
            detected_at=datetime.now(),
            source="anomaly_detector",
            metadata={
                "z_score": z_score,
                "stdev": stdev,
                "sample_size": len(values),
                "mean": mean
            }
        )

        anomalies.append(anomaly)
        return anomalies

    def _determine_anomaly_type(self, metric_name: str, current: float, expected: float) -> AnomalyType:
        """Determine the type of anomaly based on metric and direction."""
        type_map = {
            "gold_grade": AnomalyType.GRADE_VARIATION,
            "tonnage_mined": AnomalyType.PRODUCTION_SPIKE if current > expected else AnomalyType.PRODUCTION_DROP,
            "tonnage_milled": AnomalyType.PRODUCTION_SPIKE if current > expected else AnomalyType.PRODUCTION_DROP,
            "recovery_rate": AnomalyType.PRODUCTION_DROP if current < expected else AnomalyType.PRODUCTION_SPIKE,
            "water_usage": AnomalyType.ENERGY_CONSUMPTION,
            "energy_consumption": AnomalyType.ENERGY_CONSUMPTION,
            "diesel_consumption": AnomalyType.ENERGY_CONSUMPTION,
            "safety_incidents": AnomalyType.SAFETY_VIOLATION,
            "equipment_uptime": AnomalyType.EQUIPMENT_DEGRADATION if current < expected else AnomalyType.PRODUCTION_SPIKE,
            "cost_per_ounce": AnomalyType.COST_ANOMALY,
        }
        return type_map.get(metric_name, AnomalyType.PRODUCTION_SPIKE)

    def _generate_description(self, metric_name: str, current: float, expected: float, z_score: float, deviation: float) -> str:
        """Generate a human-readable description of the anomaly."""
        direction = "increased" if current > expected else "decreased"
        severity_word = "significantly" if abs(z_score) > 3 else "moderately"
        return (
            f"{metric_name.replace('_', ' ').title()} has {severity_word} {direction} to {current:.2f} "
            f"(expected ~{expected:.2f}, {deviation:+.1f}% deviation). "
            f"Z-score: {z_score:.2f}"
        )

    def get_active_anomalies(self, limit: int = 50) -> List[Anomaly]:
        """Get unacknowledged anomalies."""
        return [a for a in self.anomalies if not a.acknowledged][:limit]

    def get_anomalies_by_severity(self, severity: Severity) -> List[Anomaly]:
        """Get anomalies filtered by severity."""
        return [a for a in self.anomalies if a.severity == severity and not a.resolved]

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Acknowledge an anomaly."""
        for anomaly in self.anomalies:
            if anomaly.id == anomaly_id:
                anomaly.acknowledged = True
                return True
        return False

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Mark an anomaly as resolved."""
        for anomaly in self.anomalies:
            if anomaly.id == anomaly_id:
                anomaly.resolved = True
                return True
        return False

    def get_metric_statistics(self, metric_name: str) -> Dict[str, Any]:
        """Get statistics for a metric."""
        history = self.metrics_history.get(metric_name, deque())
        if not history:
            return {"error": "No data available"}

        values = [h["value"] for h in history]
        return {
            "metric": metric_name,
            "current": values[-1] if values else None,
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "samples": len(values),
            "threshold": self.thresholds.get(metric_name)
        }

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary of all metrics."""
        active = self.get_active_anomalies()
        critical = self.get_anomalies_by_severity(Severity.CRITICAL)
        high = self.get_anomalies_by_severity(Severity.HIGH)

        health_score = 100
        health_score -= len(critical) * 20
        health_score -= len(high) * 10
        health_score -= len(active) * 2
        health_score = max(0, health_score)

        return {
            "health_score": health_score,
            "status": "critical" if critical else "warning" if high else "healthy",
            "active_anomalies": len(active),
            "critical_count": len(critical),
            "high_count": len(high),
            "metrics_tracked": len(self.metrics_history),
            "total_anomalies_detected": len(self.anomalies)
        }


class TrendAnalyzer:
    """Analyzes trends in mining metrics over time."""

    def __init__(self):
        self.trends: Dict[str, List[float]] = {}

    def add_data_point(self, metric_name: str, value: float):
        """Add a data point for trend analysis."""
        if metric_name not in self.trends:
            self.trends[metric_name] = []
        self.trends[metric_name].append(value)

    def analyze_trend(self, metric_name: str, window: int = 7) -> Dict[str, Any]:
        """Analyze trend for a metric over a window."""
        data = self.trends.get(metric_name, [])
        if len(data) < window:
            return {"trend": "insufficient_data", "data_points": len(data)}

        recent = data[-window:]
        earlier = data[-2*window:-window] if len(data) >= 2*window else data[:window]

        recent_avg = statistics.mean(recent)
        earlier_avg = statistics.mean(earlier)

        change = recent_avg - earlier_avg
        change_percent = (change / earlier_avg * 100) if earlier_avg != 0 else 0

        if change_percent > 10:
            trend = "increasing"
        elif change_percent < -10:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "metric": metric_name,
            "trend": trend,
            "change_percent": change_percent,
            "recent_average": recent_avg,
            "earlier_average": earlier_avg,
            "data_points": len(data),
            "window": window
        }

    def get_all_trends(self) -> Dict[str, Dict[str, Any]]:
        """Get trends for all metrics."""
        return {name: self.analyze_trend(name) for name in self.trends}


class ForecastEngine:
    """Simple forecasting for mining metrics."""

    def __init__(self):
        self.history: Dict[str, List[float]] = {}

    def add_observation(self, metric_name: str, value: float):
        """Add an observation for forecasting."""
        if metric_name not in self.history:
            self.history[metric_name] = []
        self.history[metric_name].append(value)

    def forecast_next(self, metric_name: str, periods: int = 7) -> Dict[str, Any]:
        """Forecast next N periods using moving average."""
        data = self.history.get(metric_name, [])
        if len(data) < 5:
            return {"error": "Insufficient data for forecasting"}

        window = min(7, len(data))
        recent = data[-window:]
        moving_avg = statistics.mean(recent)

        trend = 0
        if len(data) >= 2 * window:
            prev_window = data[-2*window:-window]
            trend = (statistics.mean(recent) - statistics.mean(prev_window)) / window

        forecasts = []
        for i in range(1, periods + 1):
            forecast_value = moving_avg + (trend * i)
            forecasts.append({
                "period": i,
                "forecast": max(0, forecast_value),
                "confidence": max(0.5, 1.0 - (i * 0.05))
            })

        return {
            "metric": metric_name,
            "current_value": data[-1],
            "moving_average": moving_avg,
            "trend_per_period": trend,
            "forecasts": forecasts
        }


class MiningAnomalySystem:
    """Complete anomaly detection system for mining operations."""

    def __init__(self):
        self.detector = AnomalyDetector()
        self.trend_analyzer = TrendAnalyzer()
        self.forecaster = ForecastEngine()
        self._initialized = False

    def initialize_sample_data(self):
        """Initialize with sample mining data for demonstration."""
        import random

        base_grade = 5.2
        base_tonnage = 25000
        base_recovery = 92.5

        for i in range(60):
            day = datetime.now() - timedelta(days=60-i)

            grade = base_grade + random.gauss(0, 0.3)
            self.detector.record_metric("gold_grade", grade, day)
            self.trend_analyzer.add_data_point("gold_grade", grade)
            self.forecaster.add_observation("gold_grade", grade)

            tonnage = base_tonnage + random.gauss(0, 500)
            self.detector.record_metric("tonnage_mined", tonnage, day)
            self.trend_analyzer.add_data_point("tonnage_mined", tonnage)
            self.forecaster.add_observation("tonnage_mined", tonnage)

            recovery = base_recovery + random.gauss(0, 0.8)
            self.detector.record_metric("recovery_rate", recovery, day)
            self.trend_analyzer.add_data_point("recovery_rate", recovery)

            energy = 45000 + random.gauss(0, 2000)
            self.detector.record_metric("energy_consumption", energy, day)
            self.trend_analyzer.add_data_point("energy_consumption", energy)

            cost = 1250 + random.gauss(0, 50)
            self.detector.record_metric("cost_per_ounce", cost, day)
            self.trend_analyzer.add_data_point("cost_per_ounce", cost)

        self._initialized = True
        logger.info("Anomaly detection system initialized with sample data")

    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status."""
        return {
            "initialized": self._initialized,
            "health": self.detector.get_health_summary(),
            "trends": self.trend_analyzer.get_all_trends(),
            "active_anomalies": [
                {
                    "id": a.id,
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "description": a.description,
                    "detected_at": a.detected_at.isoformat()
                }
                for a in self.detector.get_active_anomalies()
            ]
        }

    def analyze_query(self, query: str) -> Dict[str, Any]:
        """Analyze a query and provide relevant anomaly data."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["health", "status", "overview"]):
            return self.get_system_status()

        if any(word in query_lower for word in ["trend", "trending", "direction"]):
            return {"trends": self.trend_analyzer.get_all_trends()}

        if any(word in query_lower for word in ["anomal", "unusual", "alert", "warning"]):
            return {
                "active_anomalies": [
                    {
                        "id": a.id,
                        "type": a.type.value,
                        "severity": a.severity.value,
                        "title": a.title,
                        "description": a.description,
                        "current_value": a.current_value,
                        "expected_value": a.expected_value
                    }
                    for a in self.detector.get_active_anomalies()
                ]
            }

        if any(word in query_lower for word in ["forecast", "predict", "future", "outlook"]):
            forecasts = {}
            for metric in ["gold_grade", "tonnage_mined", "cost_per_ounce"]:
                forecast = self.forecaster.forecast_next(metric)
                if "error" not in forecast:
                    forecasts[metric] = forecast
            return {"forecasts": forecasts}

        return self.get_system_status()
