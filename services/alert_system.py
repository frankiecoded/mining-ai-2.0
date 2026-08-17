"""
Alert and Notification System for Mining Operations
Proactive alerts based on conditions, thresholds, and escalation rules.
Supports multiple notification channels and escalation policies.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class NotificationChannel(Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PA = "pa_system"


@dataclass
class AlertCondition:
    metric: str
    operator: str
    value: float
    duration_minutes: int = 0
    description: str = ""


@dataclass
class Alert:
    id: str
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    source: str
    category: str
    created_at: datetime
    updated_at: datetime
    conditions: List[AlertCondition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    escalation_level: int = 0


@dataclass
class EscalationPolicy:
    name: str
    severity: AlertSeverity
    escalation_delays: List[int]
    notification_channels: List[List[NotificationChannel]]
    recipients: List[List[str]]


@dataclass
class Notification:
    id: str
    alert_id: str
    channel: NotificationChannel
    recipient: str
    message: str
    sent_at: datetime
    status: str


class AlertRule:
    """Defines conditions that trigger alerts."""

    def __init__(self, rule_id: str, name: str, conditions: List[Dict],
                 severity: AlertSeverity, message_template: str,
                 category: str = "general", cooldown_minutes: int = 30):
        self.rule_id = rule_id
        self.name = name
        self.conditions = [AlertCondition(**c) for c in conditions]
        self.severity = severity
        self.message_template = message_template
        self.category = category
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered: Optional[datetime] = None
        self.enabled = True

    def check_conditions(self, metrics: Dict[str, float]) -> bool:
        """Check if all conditions are met."""
        if not self.enabled:
            return False

        if self.last_triggered:
            time_since = datetime.now() - self.last_triggered
            if time_since < timedelta(minutes=self.cooldown_minutes):
                return False

        for condition in self.conditions:
            metric_value = metrics.get(condition.metric)
            if metric_value is None:
                return False

            if not self._evaluate_condition(metric_value, condition.operator, condition.value):
                return False

        return True

    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate a single condition."""
        ops = {
            ">": lambda v, t: v > t,
            ">=": lambda v, t: v >= t,
            "<": lambda v, t: v < t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t,
        }
        return ops.get(operator, lambda v, t: False)(value, threshold)

    def format_message(self, metrics: Dict[str, float]) -> str:
        """Format the alert message with current values."""
        message = self.message_template
        for metric, value in metrics.items():
            message = message.replace(f"{{{metric}}}", f"{value:.2f}")
        return message


class AlertSystem:
    """Complete alert and notification system."""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.rules: List[AlertRule] = []
        self.escalation_policies: Dict[AlertSeverity, EscalationPolicy] = {}
        self.notifications: List[Notification] = []
        self.notification_handlers: Dict[NotificationChannel, Callable] = {}
        self._alert_counter = 0
        self._notification_counter = 0
        self._setup_default_rules()
        self._setup_escalation_policies()

    def _setup_default_rules(self):
        """Set up default alert rules for mining operations."""
        default_rules = [
            AlertRule(
                rule_id="safety_critical",
                name="Safety Critical Alert",
                conditions=[
                    {"metric": "safety_incidents", "operator": ">", "value": 0}
                ],
                severity=AlertSeverity.CRITICAL,
                message_template="SAFETY INCIDENT DETECTED: {safety_incidents} incidents reported. Immediate investigation required.",
                category="safety",
                cooldown_minutes=5
            ),
            AlertRule(
                rule_id="production_drop",
                name="Production Drop Alert",
                conditions=[
                    {"metric": "tonnage_mined", "operator": "<", "value": 20000}
                ],
                severity=AlertSeverity.WARNING,
                message_template="Production drop detected: {tonnage_mined:.0f} tonnes mined (target: 25,000).",
                category="production",
                cooldown_minutes=60
            ),
            AlertRule(
                rule_id="grade_low",
                name="Low Grade Alert",
                conditions=[
                    {"metric": "gold_grade", "operator": "<", "value": 3.5}
                ],
                severity=AlertSeverity.WARNING,
                message_template="Low gold grade detected: {gold_grade:.2f} g/t (minimum: 3.5 g/t).",
                category="grade",
                cooldown_minutes=120
            ),
            AlertRule(
                rule_id="equipment_downtime",
                name="Equipment Downtime Alert",
                conditions=[
                    {"metric": "equipment_uptime", "operator": "<", "value": 85}
                ],
                severity=AlertSeverity.WARNING,
                message_template="Equipment uptime low: {equipment_uptime:.1f}% (target: 90%).",
                category="equipment",
                cooldown_minutes=30
            ),
            AlertRule(
                rule_id="cost_overrun",
                name="Cost Overrun Alert",
                conditions=[
                    {"metric": "cost_per_ounce", "operator": ">", "value": 1400}
                ],
                severity=AlertSeverity.WARNING,
                message_template="AISC exceeds budget: ${cost_per_ounce:.0f}/oz (budget: $1,400/oz).",
                category="financial",
                cooldown_minutes=60
            ),
            AlertRule(
                rule_id="energy_spike",
                name="Energy Consumption Spike",
                conditions=[
                    {"metric": "energy_consumption", "operator": ">", "value": 55000}
                ],
                severity=AlertSeverity.INFO,
                message_template="Energy consumption spike: {energy_consumption:.0f} kWh (normal: ~45,000 kWh).",
                category="operations",
                cooldown_minutes=120
            ),
            AlertRule(
                rule_id="recovery_low",
                name="Recovery Rate Alert",
                conditions=[
                    {"metric": "recovery_rate", "operator": "<", "value": 88}
                ],
                severity=AlertSeverity.WARNING,
                message_template="Recovery rate below target: {recovery_rate:.1f}% (target: 92%).",
                category="metallurgy",
                cooldown_minutes=60
            ),
        ]
        self.rules.extend(default_rules)

    def _setup_escalation_policies(self):
        """Set up escalation policies for different severity levels."""
        self.escalation_policies = {
            AlertSeverity.INFO: EscalationPolicy(
                name="Info Escalation",
                severity=AlertSeverity.INFO,
                escalation_delays=[0, 60, 180],
                notification_channels=[[NotificationChannel.IN_APP], [NotificationChannel.EMAIL], [NotificationChannel.EMAIL]],
                recipients=[["operations"], ["supervisor"], ["manager"]]
            ),
            AlertSeverity.WARNING: EscalationPolicy(
                name="Warning Escalation",
                severity=AlertSeverity.WARNING,
                escalation_delays=[0, 30, 120],
                notification_channels=[[NotificationChannel.IN_APP, NotificationChannel.EMAIL], [NotificationChannel.SMS], [NotificationChannel.PA]],
                recipients=[["operations", "supervisor"], ["manager"], ["director"]]
            ),
            AlertSeverity.CRITICAL: EscalationPolicy(
                name="Critical Escalation",
                severity=AlertSeverity.CRITICAL,
                escalation_delays=[0, 15, 60],
                notification_channels=[[NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.SMS], [NotificationChannel.SMS, NotificationChannel.PA], [NotificationChannel.PA, NotificationChannel.WEBHOOK]],
                recipients=[["operations", "safety"], ["manager", "director"], ["executive"]]
            ),
            AlertSeverity.EMERGENCY: EscalationPolicy(
                name="Emergency Escalation",
                severity=AlertSeverity.EMERGENCY,
                escalation_delays=[0, 5, 15],
                notification_channels=[[NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PA], [NotificationChannel.SMS, NotificationChannel.PA], [NotificationChannel.PA, NotificationChannel.WEBHOOK]],
                recipients=[["all"], ["emergency_team"], ["external"]]
            ),
        }

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules.append(rule)

    def check_alerts(self, metrics: Dict[str, float]) -> List[Alert]:
        """Check all rules against current metrics and generate alerts."""
        new_alerts = []

        for rule in self.rules:
            if rule.check_conditions(metrics):
                alert = self._create_alert(rule, metrics)
                new_alerts.append(alert)
                self.alerts.append(alert)
                rule.last_triggered = datetime.now()

                logger.warning(f"Alert triggered: {alert.title} - {alert.message}")
                self._send_notifications(alert)

        return new_alerts

    def _create_alert(self, rule: AlertRule, metrics: Dict[str, float]) -> Alert:
        """Create a new alert from a rule."""
        self._alert_counter += 1
        now = datetime.now()

        return Alert(
            id=f"alert_{self._alert_counter:06d}",
            title=rule.name,
            message=rule.format_message(metrics),
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            source="alert_engine",
            category=rule.category,
            created_at=now,
            updated_at=now,
            conditions=rule.conditions,
            metadata={
                "rule_id": rule.rule_id,
                "metrics_at_trigger": {k: v for k, v in metrics.items()}
            }
        )

    def _send_notifications(self, alert: Alert):
        """Send notifications for an alert."""
        policy = self.escalation_policies.get(alert.severity)
        if not policy:
            return

        channels = policy.notification_channels[0] if policy.notification_channels else [NotificationChannel.IN_APP]
        recipients = policy.recipients[0] if policy.recipients else ["operations"]

        for channel in channels:
            for recipient in recipients:
                self._notification_counter += 1
                notification = Notification(
                    id=f"notif_{self._notification_counter:06d}",
                    alert_id=alert.id,
                    channel=channel,
                    recipient=recipient,
                    message=f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}",
                    sent_at=datetime.now(),
                    status="sent"
                )
                self.notifications.append(notification)

                handler = self.notification_handlers.get(channel)
                if handler:
                    try:
                        handler(notification)
                    except Exception as e:
                        logger.error(f"Notification handler failed: {e}")

    def acknowledge_alert(self, alert_id: str, user: str, notes: str = "") -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_by = user
                alert.acknowledged_at = datetime.now()
                alert.updated_at = datetime.now()
                if notes:
                    alert.resolution_notes = notes
                return True
        return False

    def resolve_alert(self, alert_id: str, notes: str = "") -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                alert.updated_at = datetime.now()
                if notes:
                    alert.resolution_notes = notes
                return True
        return False

    def escalate_alert(self, alert_id: str) -> bool:
        """Manually escalate an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.ESCALATED
                alert.escalated_at = datetime.now()
                alert.escalation_level += 1
                alert.updated_at = datetime.now()
                self._send_escalation_notifications(alert)
                return True
        return False

    def _send_escalation_notifications(self, alert: Alert):
        """Send escalation notifications."""
        policy = self.escalation_policies.get(alert.severity)
        if not policy:
            return

        level = min(alert.escalation_level, len(policy.notification_channels) - 1)
        channels = policy.notification_channels[level]
        recipients = policy.recipients[level]

        for channel in channels:
            for recipient in recipients:
                self._notification_counter += 1
                notification = Notification(
                    id=f"notif_{self._notification_counter:06d}",
                    alert_id=alert.id,
                    channel=channel,
                    recipient=recipient,
                    message=f"[ESCALATED - Level {alert.escalation_level}] {alert.title}: {alert.message}",
                    sent_at=datetime.now(),
                    status="sent"
                )
                self.notifications.append(notification)

    def get_active_alerts(self, category: Optional[str] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by category."""
        alerts = [a for a in self.alerts if a.status in [AlertStatus.ACTIVE, AlertStatus.ESCALATED]]
        if category:
            alerts = [a for a in alerts if a.category == category]
        return alerts

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity."""
        return [a for a in self.alerts if a.severity == severity and a.status != AlertStatus.RESOLVED]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        active = self.get_active_alerts()
        by_severity = defaultdict(int)
        by_category = defaultdict(int)

        for alert in self.alerts:
            by_severity[alert.severity.value] += 1
            by_category[alert.category] += 1

        return {
            "total_alerts": len(self.alerts),
            "active_alerts": len(active),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
            "rules_active": len([r for r in self.rules if r.enabled]),
            "notifications_sent": len(self.notifications)
        }

    def get_notification_history(self, alert_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get notification history."""
        notifications = self.notifications
        if alert_id:
            notifications = [n for n in notifications if n.alert_id == alert_id]

        return [
            {
                "id": n.id,
                "alert_id": n.alert_id,
                "channel": n.channel.value,
                "recipient": n.recipient,
                "message": n.message[:100],
                "sent_at": n.sent_at.isoformat(),
                "status": n.status
            }
            for n in notifications[-limit:]
        ]

    def register_notification_handler(self, channel: NotificationChannel, handler: Callable):
        """Register a handler for a notification channel."""
        self.notification_handlers[channel] = handler

    def format_alerts_for_display(self, alerts: List[Alert]) -> str:
        """Format alerts for human-readable display."""
        if not alerts:
            return "No active alerts."

        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🔴"
        }

        lines = ["## Active Alerts\n"]
        for alert in alerts[:20]:
            emoji = severity_emoji.get(alert.severity, "")
            age = datetime.now() - alert.created_at
            age_str = f"{int(age.total_seconds() / 60)}m ago"
            lines.append(f"{emoji} **{alert.title}** [{alert.severity.value}] - {age_str}")
            lines.append(f"   {alert.message}")
            if alert.acknowledged_by:
                lines.append(f"   Acknowledged by: {alert.acknowledged_by}")
            lines.append("")

        return "\n".join(lines)
