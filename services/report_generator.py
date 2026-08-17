"""
Automated Report Generator for Mining Operations
Generates comprehensive PDF/DOCX reports from data, analyses, and templates.
Supports production reports, safety reports, financial reports, and custom templates.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ReportType(Enum):
    PRODUCTION = "production"
    SAFETY = "safety"
    FINANCIAL = "financial"
    GEOLOGICAL = "geological"
    ENVIRONMENTAL = "environmental"
    EQUIPMENT = "equipment"
    SHIFT = "shift"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    CUSTOM = "custom"


class ReportFormat(Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    CSV = "csv"


@dataclass
class ReportSection:
    title: str
    content: str
    section_type: str
    order: int
    charts: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportMetadata:
    report_id: str
    title: str
    report_type: ReportType
    format: ReportFormat
    generated_at: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    author: str = "AI Mining OS"
    version: str = "1.0"


@dataclass
class ReportData:
    production: Dict[str, Any] = field(default_factory=dict)
    safety: Dict[str, Any] = field(default_factory=dict)
    financial: Dict[str, Any] = field(default_factory=dict)
    equipment: Dict[str, Any] = field(default_factory=dict)
    geological: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)


class ReportTemplate:
    """Defines a report template with sections and formatting."""

    def __init__(self, name: str, report_type: ReportType,
                 sections: List[str], description: str = ""):
        self.name = name
        self.report_type = report_type
        self.sections = sections
        self.description = description


class ReportGenerator:
    """Generates comprehensive reports for mining operations."""

    def __init__(self):
        self.templates: Dict[str, ReportTemplate] = {}
        self.reports: Dict[str, Dict] = {}
        self._report_counter = 0
        self._setup_default_templates()

    def _setup_default_templates(self):
        """Set up default report templates."""
        self.templates = {
            "daily_production": ReportTemplate(
                name="Daily Production Report",
                report_type=ReportType.PRODUCTION,
                sections=["Executive Summary", "Production Metrics", "Grade Control", "Equipment Performance", "Issues & Actions"],
                description="Daily production summary with key metrics and performance"
            ),
            "weekly_safety": ReportTemplate(
                name="Weekly Safety Report",
                report_type=ReportType.SAFETY,
                sections=["Safety Overview", "Incidents", "Near Misses", "Inspections", "Training", "Action Items"],
                description="Weekly safety review and compliance status"
            ),
            "monthly_financial": ReportTemplate(
                name="Monthly Financial Report",
                report_type=ReportType.FINANCIAL,
                sections=["Financial Summary", "Revenue", "Costs", "Budget Variance", "Forecast"],
                description="Monthly financial performance and budget analysis"
            ),
            "shift_handover": ReportTemplate(
                name="Shift Handover Report",
                report_type=ReportType.SHIFT,
                sections=["Shift Summary", "Production", "Equipment Status", "Safety", "Handover Notes"],
                description="End-of-shift summary for handover"
            ),
            "equipment_status": ReportTemplate(
                name="Equipment Status Report",
                report_type=ReportType.EQUIPMENT,
                sections=["Fleet Overview", "Availability", "Maintenance", "Performance Metrics"],
                description="Equipment fleet status and performance"
            ),
            "anomaly_investigation": ReportTemplate(
                name="Anomaly Investigation Report",
                report_type=ReportType.CUSTOM,
                sections=["Anomaly Description", "Root Cause Analysis", "Impact Assessment", "Corrective Actions", "Recommendations"],
                description="Investigation report for detected anomalies"
            )
        }

    def register_template(self, template: ReportTemplate):
        """Register a custom report template."""
        self.templates[template.name.lower().replace(" ", "_")] = template

    def generate_report(self, template_name: str, data: ReportData,
                       title: Optional[str] = None,
                       period_start: Optional[datetime] = None,
                       period_end: Optional[datetime] = None,
                       custom_sections: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Generate a report from a template and data."""
        template = self.templates.get(template_name)
        if not template:
            return {"error": f"Template '{template_name}' not found"}

        self._report_counter += 1
        report_id = f"report_{self._report_counter:06d}"

        metadata = ReportMetadata(
            report_id=report_id,
            title=title or template.name,
            report_type=template.report_type,
            format=ReportFormat.MARKDOWN,
            generated_at=datetime.now(),
            period_start=period_start,
            period_end=period_end
        )

        sections = []
        for i, section_title in enumerate(template.sections):
            content = self._generate_section_content(section_title, template.report_type, data, custom_sections)
            sections.append(ReportSection(
                title=section_title,
                content=content,
                section_type="content",
                order=i + 1
            ))

        report_content = self._compile_report(metadata, sections)

        self.reports[report_id] = {
            "metadata": metadata,
            "sections": sections,
            "content": report_content,
            "data_summary": self._summarize_data(data)
        }

        return {
            "report_id": report_id,
            "title": metadata.title,
            "type": metadata.report_type.value,
            "format": metadata.format.value,
            "generated_at": metadata.generated_at.isoformat(),
            "content": report_content
        }

    def _generate_section_content(self, section_title: str, report_type: ReportType,
                                 data: ReportData, custom_sections: Optional[Dict[str, str]]) -> str:
        """Generate content for a report section."""
        if custom_sections and section_title in custom_sections:
            return custom_sections[section_title]

        content_map = {
            "Executive Summary": self._generate_executive_summary(data),
            "Production Metrics": self._generate_production_section(data),
            "Grade Control": self._generate_grade_section(data),
            "Equipment Performance": self._generate_equipment_section(data),
            "Safety Overview": self._generate_safety_section(data),
            "Financial Summary": self._generate_financial_section(data),
            "Shift Summary": self._generate_shift_section(data),
            "Issues & Actions": self._generate_issues_section(data),
        }

        return content_map.get(section_title, f"## {section_title}\n\n[Section content to be populated with relevant data]")

    def _generate_executive_summary(self, data: ReportData) -> str:
        """Generate executive summary section."""
        lines = ["### Key Highlights\n"]

        if data.production:
            tonnage = data.production.get("tonnage_mined", 0)
            grade = data.production.get("gold_grade", 0)
            recovery = data.production.get("recovery_rate", 0)
            lines.append(f"- **Tonnage Mined:** {tonnage:,.0f} tonnes")
            lines.append(f"- **Gold Grade:** {grade:.2f} g/t")
            lines.append(f"- **Recovery Rate:** {recovery:.1f}%")

        if data.safety:
            incidents = data.safety.get("incidents", 0)
            lines.append(f"- **Safety Incidents:** {incidents}")
            lines.append(f"- **Safety Status:** {'GREEN' if incidents == 0 else 'AMBER' if incidents < 3 else 'RED'}")

        if data.financial:
            cost = data.financial.get("cost_per_ounce", 0)
            lines.append(f"- **AISC:** ${cost:,.0f}/oz")

        if data.alerts:
            critical = len([a for a in data.alerts if a.get("severity") == "critical"])
            lines.append(f"- **Critical Alerts:** {critical}")

        return "\n".join(lines)

    def _generate_production_section(self, data: ReportData) -> str:
        """Generate production metrics section."""
        if not data.production:
            return "### Production Metrics\n\nNo production data available."

        prod = data.production
        lines = [
            "### Daily Production Metrics\n",
            "| Metric | Value | Target | Status |",
            "|--------|-------|--------|--------|",
        ]

        metrics = [
            ("Tonnage Mined", prod.get("tonnage_mined", 0), "25,000 tonnes", "tonnage_mined"),
            ("Tonnage Milled", prod.get("tonnage_milled", 0), "24,000 tonnes", "tonnage_milled"),
            ("Gold Grade", f"{prod.get('gold_grade', 0):.2f} g/t", "5.0 g/t", "gold_grade"),
            ("Recovery Rate", f"{prod.get('recovery_rate', 0):.1f}%", "92%", "recovery_rate"),
            ("Gold Produced", f"{prod.get('gold_produced', 0):.0f} oz", "350 oz", "gold_produced"),
        ]

        for name, value, target, key in metrics:
            status = "✅" if self._check_target(key, prod.get(key, 0)) else "⚠️"
            lines.append(f"| {name} | {value} | {target} | {status} |")

        return "\n".join(lines)

    def _generate_grade_section(self, data: ReportData) -> str:
        """Generate grade control section."""
        lines = ["### Grade Control Analysis\n"]

        if data.geological:
            geo = data.geological
            lines.append(f"- **Average Grade:** {geo.get('avg_grade', 0):.2f} g/t")
            lines.append(f"- **Grade Range:** {geo.get('min_grade', 0):.2f} - {geo.get('max_grade', 0):.2f} g/t")
            lines.append(f"- **Variability:** {geo.get('variability', 'Normal')}")
        else:
            lines.append("Grade control data to be populated from geological surveys.")

        return "\n".join(lines)

    def _generate_equipment_section(self, data: ReportData) -> str:
        """Generate equipment performance section."""
        if not data.equipment:
            return "### Equipment Performance\n\nEquipment data to be populated from fleet management system."

        equip = data.equipment
        lines = [
            "### Equipment Fleet Performance\n",
            "| Equipment | Availability | Hours | Status |",
            "|-----------|--------------|-------|--------|"
        ]

        for eq_name, stats in equip.items():
            if isinstance(stats, dict):
                avail = stats.get("availability", 0)
                hours = stats.get("hours", 0)
                status = "✅" if avail >= 90 else "⚠️" if avail >= 80 else "🔴"
                lines.append(f"| {eq_name} | {avail:.1f}% | {hours:.0f}h | {status} |")

        return "\n".join(lines)

    def _generate_safety_section(self, data: ReportData) -> str:
        """Generate safety section."""
        lines = ["### Safety Performance\n"]

        if data.safety:
            safety = data.safety
            lines.append(f"- **Incidents:** {safety.get('incidents', 0)}")
            lines.append(f"- **Near Misses:** {safety.get('near_misses', 0)}")
            lines.append(f"- **Inspections Completed:** {safety.get('inspections', 0)}")
            lines.append(f"- **Safety Score:** {safety.get('score', 0):.0f}/100")
        else:
            lines.append("Safety data to be populated from safety management system.")

        return "\n".join(lines)

    def _generate_financial_section(self, data: ReportData) -> str:
        """Generate financial section."""
        if not data.financial:
            return "### Financial Summary\n\nFinancial data to be populated from accounting system."

        fin = data.financial
        lines = [
            "### Financial Summary\n",
            f"- **Revenue:** ${fin.get('revenue', 0):,.0f}",
            f"- **Operating Costs:** ${fin.get('operating_costs', 0):,.0f}",
            f"- **AISC:** ${fin.get('cost_per_ounce', 0):,.0f}/oz",
            f"- **Margin:** ${fin.get('margin', 0):,.0f}/oz"
        ]

        return "\n".join(lines)

    def _generate_shift_section(self, data: ReportData) -> str:
        """Generate shift section."""
        lines = ["### Shift Summary\n"]

        if data.production:
            lines.append(f"- **Shift Tonnage:** {data.production.get('tonnage_mined', 0):,.0f} tonnes")
            lines.append(f"- **Shift Grade:** {data.production.get('gold_grade', 0):.2f} g/t")

        if data.equipment:
            active = len([e for e in data.equipment.values() if isinstance(e, dict) and e.get("status") == "active"])
            lines.append(f"- **Equipment Active:** {active}/{len(data.equipment)}")

        return "\n".join(lines)

    def _generate_issues_section(self, data: ReportData) -> str:
        """Generate issues and actions section."""
        lines = ["### Issues & Required Actions\n"]

        if data.alerts:
            critical_alerts = [a for a in data.alerts if a.get("severity") in ["critical", "high"]]
            if critical_alerts:
                lines.append("**Critical Issues:**")
                for alert in critical_alerts[:5]:
                    lines.append(f"- ⚠️ {alert.get('title', 'Unknown issue')}")
            else:
                lines.append("No critical issues detected.")
        else:
            lines.append("No issues to report.")

        return "\n".join(lines)

    def _check_target(self, metric: str, value: float) -> bool:
        """Check if a metric meets its target."""
        targets = {
            "tonnage_mined": 25000,
            "tonnage_milled": 24000,
            "gold_grade": 4.5,
            "recovery_rate": 90,
            "gold_produced": 300
        }
        return value >= targets.get(metric, 0)

    def _compile_report(self, metadata: ReportMetadata, sections: List[ReportSection]) -> str:
        """Compile sections into a complete report."""
        lines = [
            f"# {metadata.title}",
            f"",
            f"**Generated:** {metadata.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Period:** {metadata.period_start.strftime('%Y-%m-%d') if metadata.period_start else 'N/A'} to {metadata.period_end.strftime('%Y-%m-%d') if metadata.period_end else 'N/A'}",
            f"**Author:** {metadata.author}",
            f"",
            "---",
            ""
        ]

        for section in sorted(sections, key=lambda s: s.order):
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"\n*Report generated by AI Mining OS - {metadata.report_id}*")

        return "\n".join(lines)

    def _summarize_data(self, data: ReportData) -> Dict[str, Any]:
        """Summarize the data used in the report."""
        return {
            "has_production_data": bool(data.production),
            "has_safety_data": bool(data.safety),
            "has_financial_data": bool(data.financial),
            "has_equipment_data": bool(data.equipment),
            "has_geological_data": bool(data.geological),
            "alert_count": len(data.alerts),
            "anomaly_count": len(data.anomalies)
        }

    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get a generated report."""
        return self.reports.get(report_id)

    def list_reports(self, report_type: Optional[ReportType] = None) -> List[Dict]:
        """List all generated reports."""
        reports = []
        for report_id, report in self.reports.items():
            metadata = report["metadata"]
            if report_type and metadata.report_type != report_type:
                continue
            reports.append({
                "report_id": report_id,
                "title": metadata.title,
                "type": metadata.report_type.value,
                "generated_at": metadata.generated_at.isoformat()
            })
        return reports

    def export_report(self, report_id: str, format: ReportFormat) -> Optional[str]:
        """Export a report in the specified format."""
        report = self.reports.get(report_id)
        if not report:
            return None

        if format == ReportFormat.MARKDOWN:
            return report["content"]
        elif format == ReportFormat.HTML:
            return self._convert_to_html(report["content"])
        elif format == ReportFormat.JSON:
            return json.dumps({
                "metadata": {
                    "report_id": report_id,
                    "title": report["metadata"].title,
                    "type": report["metadata"].report_type.value,
                    "generated_at": report["metadata"].generated_at.isoformat()
                },
                "content": report["content"]
            }, indent=2)
        return None

    def _convert_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML (basic conversion)."""
        html = markdown
        html = html.replace("# ", "<h1>").replace("\n#", "\n<h1>")
        html = html.replace("## ", "<h2>").replace("\n##", "\n<h2>")
        html = html.replace("### ", "<h3>").replace("\n###", "\n<h3>")
        html = html.replace("**", "<strong>").replace("**", "</strong>", 1)
        html = html.replace("- ", "<li>")
        html = html.replace("| ", "<td>")
        return f"<div class='report'>{html}</div>"

    def get_templates(self) -> List[Dict[str, str]]:
        """Get all available report templates."""
        return [
            {
                "name": template.name,
                "type": template.report_type.value,
                "description": template.description,
                "sections": template.sections
            }
            for template in self.templates.values()
        ]

    def generate_quick_summary(self, data: ReportData) -> str:
        """Generate a quick summary without full report structure."""
        lines = ["## Quick Summary\n"]

        if data.production:
            lines.append(f"**Production:** {data.production.get('tonnage_mined', 0):,.0f} tonnes @ {data.production.get('gold_grade', 0):.2f} g/t")

        if data.safety:
            status = "GREEN" if data.safety.get('incidents', 0) == 0 else "AMBER"
            lines.append(f"**Safety:** {status} - {data.safety.get('incidents', 0)} incidents")

        if data.financial:
            lines.append(f"**Financial:** AISC ${data.financial.get('cost_per_ounce', 0):,.0f}/oz")

        if data.alerts:
            critical = len([a for a in data.alerts if a.get("severity") == "critical"])
            lines.append(f"**Alerts:** {critical} critical")

        return "\n".join(lines)
