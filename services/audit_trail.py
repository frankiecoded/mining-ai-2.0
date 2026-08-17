"""
Audit Trail System for Mining Operations
Complete logging and tracking of all AI decisions, actions, and system events.
Provides accountability, compliance, and forensic analysis capabilities.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class ActionType(Enum):
    # User actions
    QUERY = "query"
    COMMAND = "command"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    CONFIGURATION_CHANGE = "configuration_change"

    # AI actions
    AI_ANALYSIS = "ai_analysis"
    AI_TOOL_CALL = "ai_tool_call"
    AI_DECISION = "ai_decision"
    AI_RECOMMENDATION = "ai_recommendation"
    AI_RESPONSE = "ai_response"

    # System actions
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"
    SYSTEM_ALERT = "system_alert"

    # Data actions
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"

    # Security actions
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_FAILURE = "auth_failure"
    PERMISSION_CHANGE = "permission_change"

    # Mining-specific
    REPORT_GENERATION = "report_generation"
    ALERT_TRIGGERED = "alert_triggered"
    ANOMALY_DETECTED = "anomaly_detected"
    SAFETY_CHECK = "safety_check"
    PRODUCTION_LOG = "production_log"


class ActionStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class AuditEntry:
    id: str
    timestamp: datetime
    action_type: ActionType
    action_name: str
    status: ActionStatus
    user_id: str
    session_id: Optional[str]
    source: str
    description: str
    details: Dict[str, Any]
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None
    duration_ms: Optional[float] = None
    ip_address: Optional[str] = None
    checksum: str = ""


@dataclass
class AuditQuery:
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    action_types: Optional[List[ActionType]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source: Optional[str] = None
    status: Optional[ActionStatus] = None
    limit: int = 100
    offset: int = 0


@dataclass
class ComplianceReport:
    report_id: str
    period_start: datetime
    period_end: datetime
    total_actions: int
    actions_by_type: Dict[str, int]
    actions_by_user: Dict[str, int]
    failures: int
    security_events: int
    ai_decisions: int
    recommendations: List[str]


class AuditTrail:
    """Complete audit trail system for mining operations."""

    def __init__(self):
        self.entries: List[AuditEntry] = []
        self._entry_counter = 0
        self._session_users: Dict[str, str] = {}
        self._retention_days = 365
        self._enable_integrity_check = True

    def _generate_checksum(self, entry_data: Dict[str, Any]) -> str:
        """Generate checksum for entry integrity."""
        data_str = json.dumps(entry_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def log_action(self, action_type: ActionType, action_name: str,
                   user_id: str, description: str,
                   status: ActionStatus = ActionStatus.SUCCESS,
                   session_id: Optional[str] = None,
                   source: str = "system",
                   details: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None,
                   parent_id: Optional[str] = None,
                   duration_ms: Optional[float] = None,
                   ip_address: Optional[str] = None) -> str:
        """Log an audit entry."""
        self._entry_counter += 1
        now = datetime.now()

        entry_id = f"audit_{self._entry_counter:08d}"

        if session_id and user_id:
            self._session_users[session_id] = user_id

        entry_data = {
            "id": entry_id,
            "timestamp": now.isoformat(),
            "action_type": action_type.value,
            "action_name": action_name,
            "status": status.value,
            "user_id": user_id,
            "session_id": session_id,
            "source": source,
            "description": description,
            "details": details or {},
            "metadata": metadata or {}
        }

        checksum = self._generate_checksum(entry_data) if self._enable_integrity_check else ""

        entry = AuditEntry(
            id=entry_id,
            timestamp=now,
            action_type=action_type,
            action_name=action_name,
            status=status,
            user_id=user_id,
            session_id=session_id,
            source=source,
            description=description,
            details=details or {},
            metadata=metadata or {},
            parent_id=parent_id,
            duration_ms=duration_ms,
            ip_address=ip_address,
            checksum=checksum
        )

        self.entries.append(entry)

        if action_type in [ActionType.AUTH_FAILURE, ActionType.SYSTEM_ERROR, ActionType.SECURITY_EVENT]:
            logger.warning(f"Security/Error event: {entry_id} - {description}")

        return entry_id

    def log_user_query(self, user_id: str, query: str, session_id: str,
                      response_time_ms: float, success: bool) -> str:
        """Log a user query."""
        return self.log_action(
            action_type=ActionType.QUERY,
            action_name="user_query",
            user_id=user_id,
            description=f"User query: {query[:100]}",
            status=ActionStatus.SUCCESS if success else ActionStatus.FAILURE,
            session_id=session_id,
            source="chat",
            details={"query": query, "response_time_ms": response_time_ms},
            duration_ms=response_time_ms
        )

    def log_ai_decision(self, user_id: str, decision: str, reasoning: str,
                       tools_used: List[str], session_id: str) -> str:
        """Log an AI decision."""
        return self.log_action(
            action_type=ActionType.AI_DECISION,
            action_name="ai_decision",
            user_id=user_id,
            description=f"AI decision: {decision[:100]}",
            status=ActionStatus.SUCCESS,
            session_id=session_id,
            source="orchestrator",
            details={
                "decision": decision,
                "reasoning": reasoning,
                "tools_used": tools_used
            }
        )

    def log_tool_call(self, user_id: str, tool_name: str, arguments: Dict,
                     result: str, duration_ms: float, session_id: str) -> str:
        """Log an AI tool call."""
        return self.log_action(
            action_type=ActionType.AI_TOOL_CALL,
            action_name=tool_name,
            user_id=user_id,
            description=f"Tool call: {tool_name}",
            status=ActionStatus.SUCCESS,
            session_id=session_id,
            source="tool_executor",
            details={
                "arguments": arguments,
                "result_preview": result[:200] if result else "",
                "duration_ms": duration_ms
            },
            duration_ms=duration_ms
        )

    def log_file_operation(self, user_id: str, operation: str, filepath: str,
                          session_id: str, success: bool) -> str:
        """Log a file operation."""
        action_type = {
            "read": ActionType.DATA_READ,
            "write": ActionType.DATA_WRITE,
            "delete": ActionType.DATA_DELETE,
            "upload": ActionType.FILE_UPLOAD,
            "download": ActionType.FILE_DOWNLOAD
        }.get(operation, ActionType.DATA_READ)

        return self.log_action(
            action_type=action_type,
            action_name=f"file_{operation}",
            user_id=user_id,
            description=f"File {operation}: {filepath}",
            status=ActionStatus.SUCCESS if success else ActionStatus.FAILURE,
            session_id=session_id,
            source="file_system",
            details={"filepath": filepath, "operation": operation}
        )

    def log_security_event(self, event_type: str, user_id: str,
                          description: str, details: Dict[str, Any]) -> str:
        """Log a security event."""
        return self.log_action(
            action_type=ActionType.AUTH_FAILURE if "auth" in event_type.lower() else ActionType.SYSTEM_ALERT,
            action_name=event_type,
            user_id=user_id,
            description=description,
            status=ActionStatus.FAILURE,
            source="security",
            details=details
        )

    def log_safety_check(self, user_id: str, checklist_name: str,
                        items_checked: int, items_total: int,
                        issues_found: List[str], session_id: str) -> str:
        """Log a safety check."""
        return self.log_action(
            action_type=ActionType.SAFETY_CHECK,
            action_name="safety_checklist",
            user_id=user_id,
            description=f"Safety check: {checklist_name} - {items_checked}/{items_total} items",
            status=ActionStatus.SUCCESS if not issues_found else ActionStatus.PARTIAL,
            session_id=session_id,
            source="safety_system",
            details={
                "checklist": checklist_name,
                "items_checked": items_checked,
                "items_total": items_total,
                "issues_found": issues_found,
                "completion_rate": items_checked / items_total if items_total > 0 else 0
            }
        )

    def log_report_generation(self, user_id: str, report_type: str,
                            output_format: str, filepath: str,
                            session_id: str) -> str:
        """Log report generation."""
        return self.log_action(
            action_type=ActionType.REPORT_GENERATION,
            action_name="generate_report",
            user_id=user_id,
            description=f"Generated {report_type} report in {output_format}",
            status=ActionStatus.SUCCESS,
            session_id=session_id,
            source="report_engine",
            details={
                "report_type": report_type,
                "output_format": output_format,
                "filepath": filepath
            }
        )

    def query_entries(self, query: AuditQuery) -> List[AuditEntry]:
        """Query audit entries."""
        results = self.entries

        if query.start_time:
            results = [e for e in results if e.timestamp >= query.start_time]
        if query.end_time:
            results = [e for e in results if e.timestamp <= query.end_time]
        if query.action_types:
            results = [e for e in results if e.action_type in query.action_types]
        if query.user_id:
            results = [e for e in results if e.user_id == query.user_id]
        if query.session_id:
            results = [e for e in results if e.session_id == query.session_id]
        if query.source:
            results = [e for e in results if e.source == query.source]
        if query.status:
            results = [e for e in results if e.status == query.status]

        return results[query.offset:query.offset + query.limit]

    def get_user_activity(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get activity summary for a user."""
        cutoff = datetime.now() - timedelta(days=days)
        user_entries = [e for e in self.entries if e.user_id == user_id and e.timestamp >= cutoff]

        action_counts = defaultdict(int)
        for entry in user_entries:
            action_counts[entry.action_type.value] += 1

        return {
            "user_id": user_id,
            "period_days": days,
            "total_actions": len(user_entries),
            "actions_by_type": dict(action_counts),
            "first_activity": user_entries[0].timestamp.isoformat() if user_entries else None,
            "last_activity": user_entries[-1].timestamp.isoformat() if user_entries else None
        }

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary for a session."""
        session_entries = [e for e in self.entries if e.session_id == session_id]

        if not session_entries:
            return {"session_id": session_id, "status": "no_data"}

        action_counts = defaultdict(int)
        for entry in session_entries:
            action_counts[entry.action_type.value] += 1

        start_time = session_entries[0].timestamp
        end_time = session_entries[-1].timestamp
        duration = (end_time - start_time).total_seconds()

        return {
            "session_id": session_id,
            "total_actions": len(session_entries),
            "actions_by_type": dict(action_counts),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "user_id": session_entries[0].user_id
        }

    def get_security_events(self, days: int = 7) -> List[Dict]:
        """Get security events."""
        cutoff = datetime.now() - timedelta(days=days)
        security_types = [ActionType.AUTH_FAILURE, ActionType.AUTH_LOGIN, ActionType.PERMISSION_CHANGE]

        events = [e for e in self.entries
                 if e.timestamp >= cutoff and e.action_type in security_types]

        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "type": e.action_type.value,
                "user": e.user_id,
                "description": e.description,
                "status": e.status.value
            }
            for e in events
        ]

    def get_ai_decision_log(self, days: int = 7) -> List[Dict]:
        """Get AI decision log."""
        cutoff = datetime.now() - timedelta(days=days)
        decisions = [e for e in self.entries
                    if e.timestamp >= cutoff and e.action_type == ActionType.AI_DECISION]

        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "user": e.user_id,
                "decision": e.details.get("decision", ""),
                "tools_used": e.details.get("tools_used", []),
                "session": e.session_id
            }
            for e in decisions
        ]

    def generate_compliance_report(self, start_date: datetime, end_date: datetime) -> ComplianceReport:
        """Generate a compliance report."""
        period_entries = [e for e in self.entries
                         if start_date <= e.timestamp <= end_date]

        by_type = defaultdict(int)
        by_user = defaultdict(int)
        failures = 0
        security_events = 0
        ai_decisions = 0

        for entry in period_entries:
            by_type[entry.action_type.value] += 1
            by_user[entry.user_id] += 1
            if entry.status == ActionStatus.FAILURE:
                failures += 1
            if entry.action_type in [ActionType.AUTH_FAILURE, ActionType.SYSTEM_ALERT]:
                security_events += 1
            if entry.action_type == ActionType.AI_DECISION:
                ai_decisions += 1

        recommendations = []
        if failures > len(period_entries) * 0.1:
            recommendations.append("High failure rate detected - review system health")
        if security_events > 10:
            recommendations.append("Elevated security events - review access controls")
        if ai_decisions > len(period_entries) * 0.5:
            recommendations.append("High AI decision volume - ensure proper oversight")

        return ComplianceReport(
            report_id=f"compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            period_start=start_date,
            period_end=end_date,
            total_actions=len(period_entries),
            actions_by_type=dict(by_type),
            actions_by_user=dict(by_user),
            failures=failures,
            security_events=security_events,
            ai_decisions=ai_decisions,
            recommendations=recommendations
        )

    def verify_integrity(self, last_n: int = 100) -> Dict[str, Any]:
        """Verify audit trail integrity."""
        entries_to_check = self.entries[-last_n:]
        valid = 0
        invalid = 0

        for entry in entries_to_check:
            if entry.checksum:
                entry_data = {
                    "id": entry.id,
                    "timestamp": entry.timestamp.isoformat(),
                    "action_type": entry.action_type.value,
                    "action_name": entry.action_name,
                    "status": entry.status.value,
                    "user_id": entry.user_id,
                    "session_id": entry.session_id,
                    "source": entry.source,
                    "description": entry.description,
                    "details": entry.details,
                    "metadata": entry.metadata
                }
                expected_checksum = self._generate_checksum(entry_data)
                if entry.checksum == expected_checksum:
                    valid += 1
                else:
                    invalid += 1
                    logger.warning(f"Integrity check failed for entry {entry.id}")
            else:
                valid += 1

        return {
            "entries_checked": len(entries_to_check),
            "valid": valid,
            "invalid": invalid,
            "integrity_status": "pass" if invalid == 0 else "fail"
        }

    def cleanup_old_entries(self, days: Optional[int] = None):
        """Remove entries older than retention period."""
        retention = days or self._retention_days
        cutoff = datetime.now() - timedelta(days=retention)
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.timestamp >= cutoff]
        removed = original_count - len(self.entries)
        if removed > 0:
            logger.info(f"Audit cleanup: removed {removed} entries older than {retention} days")

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        if not self.entries:
            return {"total_entries": 0}

        action_counts = defaultdict(int)
        user_counts = defaultdict(int)
        source_counts = defaultdict(int)

        for entry in self.entries:
            action_counts[entry.action_type.value] += 1
            user_counts[entry.user_id] += 1
            source_counts[entry.source] += 1

        return {
            "total_entries": len(self.entries),
            "date_range": {
                "earliest": self.entries[0].timestamp.isoformat(),
                "latest": self.entries[-1].timestamp.isoformat()
            },
            "by_action_type": dict(action_counts),
            "by_user": dict(user_counts),
            "by_source": dict(source_counts),
            "entries_per_day": len(self.entries) / max(1, (self.entries[-1].timestamp - self.entries[0].timestamp).days + 1)
        }

    def format_entries_for_display(self, entries: List[AuditEntry], limit: int = 20) -> str:
        """Format audit entries for display."""
        if not entries:
            return "No audit entries found."

        status_emoji = {
            ActionStatus.SUCCESS: "✅",
            ActionStatus.FAILURE: "❌",
            ActionStatus.PARTIAL: "⚠️",
            ActionStatus.PENDING: "⏳",
            ActionStatus.CANCELLED: "🚫"
        }

        lines = ["## Audit Trail\n"]

        for entry in entries[:limit]:
            emoji = status_emoji.get(entry.status, "")
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{emoji} `{time_str}` **{entry.action_name}** by {entry.user_id}")
            lines.append(f"   {entry.description}")
            if entry.duration_ms:
                lines.append(f"   Duration: {entry.duration_ms:.0f}ms")
            lines.append("")

        if len(entries) > limit:
            lines.append(f"... and {len(entries) - limit} more entries")

        return "\n".join(lines)
