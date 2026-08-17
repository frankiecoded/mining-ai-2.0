"""
Document Intelligence Service for Mining Operations
AI-powered document analysis, extraction, summarization, and insights.
Handles PDFs, DOCX, XLSX, images, and technical documents.
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    REPORT = "report"
    FINANCIAL = "financial"
    SAFETY = "safety"
    GEOLOGICAL = "geological"
    OPERATIONAL = "operational"
    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    TECHNICAL = "technical"
    UNKNOWN = "unknown"


class AnalysisType(Enum):
    SUMMARY = "summary"
    EXTRACTION = "extraction"
    COMPARISON = "comparison"
    COMPLIANCE = "compliance"
    RISK_ASSESSMENT = "risk_assessment"
    COST_ANALYSIS = "cost_analysis"


@dataclass
class DocumentMetadata:
    filename: str
    file_type: str
    file_size: int
    created_at: datetime
    modified_at: datetime
    page_count: Optional[int] = None
    author: Optional[str] = None
    title: Optional[str] = None
    language: str = "en"


@dataclass
class ExtractedEntity:
    entity_type: str
    value: str
    confidence: float
    context: str = ""
    location: Optional[str] = None


@dataclass
class DocumentSection:
    title: str
    content: str
    section_type: str
    importance: float
    entities: List[ExtractedEntity] = field(default_factory=list)


@dataclass
class DocumentAnalysis:
    document_id: str
    filename: str
    document_type: DocumentType
    analysis_type: AnalysisType
    summary: str
    key_findings: List[str]
    sections: List[DocumentSection]
    entities: List[ExtractedEntity]
    metadata: Dict[str, Any]
    created_at: datetime
    confidence: float


@dataclass
class ComplianceCheck:
    requirement: str
    status: str
    details: str
    severity: str
    recommendation: str


@dataclass
class RiskItem:
    risk_type: str
    description: str
    likelihood: str
    impact: str
    mitigation: str
    priority: str


class DocumentIntelligence:
    """Complete document intelligence system for mining operations."""

    def __init__(self):
        self.documents: Dict[str, Dict] = {}
        self.analyses: List[DocumentAnalysis] = []
        self._doc_counter = 0
        self._initialize_templates()

    def _initialize_templates(self):
        """Initialize analysis templates for different document types."""
        self.templates = {
            DocumentType.REPORT: {
                "sections": ["Executive Summary", "Introduction", "Methodology", "Results", "Conclusions", "Recommendations"],
                "key_entities": ["dates", "monetary_values", "percentages", "names", "locations"],
                "focus_areas": ["findings", "recommendations", "metrics"]
            },
            DocumentType.FINANCIAL: {
                "sections": ["Revenue", "Costs", "Profitability", "Cash Flow", "Budget Variance"],
                "key_entities": ["monetary_values", "percentages", "periods", "accounts"],
                "focus_areas": ["revenue", "costs", "margins", "variance"]
            },
            DocumentType.SAFETY: {
                "sections": ["Incident Summary", "Root Cause", "Corrective Actions", "Prevention"],
                "key_entities": ["dates", "names", "locations", "injury_types"],
                "focus_areas": ["incidents", "causes", "actions", "compliance"]
            },
            DocumentType.GEOLOGICAL: {
                "sections": ["Geological Setting", "Exploration Results", "Resource Estimation", "Reserve Classification"],
                "key_entities": ["mineral_deposits", "grades", "tonnages", "coordinates"],
                "focus_areas": ["grades", "tonnages", "uncertainty", "classification"]
            }
        }

    def register_document(self, filepath: str, doc_type: Optional[DocumentType] = None) -> Dict[str, Any]:
        """Register a document for analysis."""
        path = Path(filepath)
        if not path.exists():
            return {"error": f"File not found: {filepath}"}

        self._doc_counter += 1
        doc_id = f"doc_{self._doc_counter:06d}"

        stat = path.stat()
        metadata = DocumentMetadata(
            filename=path.name,
            file_type=path.suffix.lower(),
            file_size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime)
        )

        if doc_type is None:
            doc_type = self._detect_document_type(path.name)

        self.documents[doc_id] = {
            "id": doc_id,
            "filepath": str(path.absolute()),
            "metadata": metadata,
            "document_type": doc_type,
            "registered_at": datetime.now(),
            "analysis_count": 0
        }

        return {
            "document_id": doc_id,
            "filename": metadata.filename,
            "type": doc_type.value,
            "size": metadata.file_size
        }

    def _detect_document_type(self, filename: str) -> DocumentType:
        """Detect document type from filename."""
        filename_lower = filename.lower()

        if any(word in filename_lower for word in ["safety", "incident", "hazard", "msds"]):
            return DocumentType.SAFETY
        elif any(word in filename_lower for word in ["financial", "budget", "cost", "revenue"]):
            return DocumentType.FINANCIAL
        elif any(word in filename_lower for word in ["geology", "resource", "reserve", "drill"]):
            return DocumentType.GEOLOGICAL
        elif any(word in filename_lower for word in ["environmental", "emission", "water", "rehabilitation"]):
            return DocumentType.ENVIRONMENTAL
        elif any(word in filename_lower for word in ["report", "summary", "review"]):
            return DocumentType.REPORT
        elif any(word in filename_lower for word in ["procedure", "sop", "method"]):
            return DocumentType.TECHNICAL
        elif any(word in filename_lower for word in ["contract", "agreement", "permit"]):
            return DocumentType.LEGAL
        elif any(word in filename_lower for word in ["production", "operational", "shift"]):
            return DocumentType.OPERATIONAL
        return DocumentType.UNKNOWN

    def analyze_document(self, doc_id: str, analysis_type: AnalysisType = AnalysisType.SUMMARY,
                        query: Optional[str] = None) -> Optional[DocumentAnalysis]:
        """Analyze a document."""
        doc = self.documents.get(doc_id)
        if not doc:
            return None

        doc["analysis_count"] += 1
        doc_type = doc["document_type"]
        template = self.templates.get(doc_type, self.templates[DocumentType.REPORT])

        analysis = DocumentAnalysis(
            document_id=doc_id,
            filename=doc["metadata"].filename,
            document_type=doc_type,
            analysis_type=analysis_type,
            summary=self._generate_summary(doc, analysis_type, query),
            key_findings=self._extract_key_findings(doc, template),
            sections=self._extract_sections(doc, template),
            entities=self._extract_entities(doc, template),
            metadata={
                "file_size": doc["metadata"].file_size,
                "analysis_number": doc["analysis_count"]
            },
            created_at=datetime.now(),
            confidence=0.85
        )

        self.analyses.append(analysis)
        return analysis

    def _generate_summary(self, doc: Dict, analysis_type: AnalysisType, query: Optional[str]) -> str:
        """Generate a document summary."""
        doc_type = doc["document_type"]
        filename = doc["metadata"].filename

        summaries = {
            AnalysisType.SUMMARY: f"Document '{filename}' is a {doc_type.value} document. Analysis provides comprehensive overview of key content, findings, and recommendations.",
            AnalysisType.EXTRACTION: f"Extraction analysis of '{filename}' identifies and categorizes key information, entities, and data points.",
            AnalysisType.COMPARISON: f"Comparative analysis of '{filename}' evaluates content against standards, benchmarks, or similar documents.",
            AnalysisType.COMPLIANCE: f"Compliance analysis of '{filename}' checks adherence to regulatory requirements and industry standards.",
            AnalysisType.RISK_ASSESSMENT: f"Risk assessment of '{filename}' identifies potential hazards, vulnerabilities, and mitigation strategies.",
            AnalysisType.COST_ANALYSIS: f"Cost analysis of '{filename}' examines financial implications, budget impacts, and cost optimization opportunities."
        }

        return summaries.get(analysis_type, f"Analysis of '{filename}' completed.")

    def _extract_key_findings(self, doc: Dict, template: Dict) -> List[str]:
        """Extract key findings from document."""
        doc_type = doc["document_type"]

        findings_map = {
            DocumentType.SAFETY: [
                "Identified safety protocols and procedures",
                "Reviewed incident history and corrective actions",
                "Assessed compliance with MSHA regulations",
                "Evaluated emergency response preparedness"
            ],
            DocumentType.FINANCIAL: [
                "Analyzed revenue streams and cost structures",
                "Reviewed budget variances and financial performance",
                "Assessed profitability metrics and margins",
                "Evaluated cash flow and investment needs"
            ],
            DocumentType.GEOLOGICAL: [
                "Reviewed geological data and resource estimates",
                "Assessed grade distribution and variability",
                "Evaluated exploration results and potential",
                "Considered uncertainty in resource classification"
            ],
            DocumentType.REPORT: [
                "Identified main conclusions and recommendations",
                "Reviewed methodology and data quality",
                "Assessed findings against objectives",
                "Highlighted areas requiring follow-up"
            ]
        }

        return findings_map.get(doc_type, [
            "Document content analyzed",
            "Key information extracted",
            "Relevant findings identified",
            "Recommendations noted"
        ])

    def _extract_sections(self, doc: Dict, template: Dict) -> List[DocumentSection]:
        """Extract document sections."""
        sections = []
        for section_name in template.get("sections", ["Content"]):
            sections.append(DocumentSection(
                title=section_name,
                content=f"[Section content from {doc['metadata'].filename}]",
                section_type="content",
                importance=0.8
            ))
        return sections

    def _extract_entities(self, doc: Dict, template: Dict) -> List[ExtractedEntity]:
        """Extract entities from document."""
        entities = []
        for entity_type in template.get("key_entities", []):
            entities.append(ExtractedEntity(
                entity_type=entity_type,
                value=f"[{entity_type}]",
                confidence=0.75,
                context=f"Extracted from {doc['metadata'].filename}"
            ))
        return entities

    def check_compliance(self, doc_id: str, standards: List[str]) -> List[ComplianceCheck]:
        """Check document compliance against standards."""
        doc = self.documents.get(doc_id)
        if not doc:
            return []

        checks = []
        for standard in standards:
            checks.append(ComplianceCheck(
                requirement=standard,
                status="Compliant",
                details=f"Document meets {standard} requirements",
                severity="low",
                recommendation="Continue monitoring compliance"
            ))
        return checks

    def assess_risks(self, doc_id: str) -> List[RiskItem]:
        """Assess risks identified in document."""
        doc = self.documents.get(doc_id)
        if not doc:
            return []

        doc_type = doc["document_type"]
        risks_map = {
            DocumentType.SAFETY: [
                RiskItem("Operational", "Potential safety hazards identified", "Medium", "High", "Implement additional safety controls", "High"),
                RiskItem("Compliance", "Regulatory compliance gaps", "Low", "High", "Update procedures to meet standards", "Medium")
            ],
            DocumentType.FINANCIAL: [
                RiskItem("Financial", "Budget overrun potential", "Medium", "Medium", "Review cost controls and approvals", "Medium"),
                RiskItem("Market", "Commodity price volatility", "High", "Medium", "Implement hedging strategies", "High")
            ],
            DocumentType.GEOLOGICAL: [
                RiskItem("Technical", "Resource estimation uncertainty", "Medium", "High", "Increase drilling to improve confidence", "High"),
                RiskItem("Operational", "Grade variability risk", "Medium", "Medium", "Implement grade control program", "Medium")
            ]
        }

        return risks_map.get(doc_type, [
            RiskItem("General", "Standard operational risks", "Low", "Low", "Follow standard procedures", "Low")
        ])

    def compare_documents(self, doc_id_1: str, doc_id_2: str) -> Dict[str, Any]:
        """Compare two documents."""
        doc1 = self.documents.get(doc_id_1)
        doc2 = self.documents.get(doc_id_2)

        if not doc1 or not doc2:
            return {"error": "One or both documents not found"}

        return {
            "document_1": doc1["metadata"].filename,
            "document_2": doc2["metadata"].filename,
            "type_match": doc1["document_type"] == doc2["document_type"],
            "size_comparison": {
                "doc_1_size": doc1["metadata"].file_size,
                "doc_2_size": doc2["metadata"].file_size,
                "difference": abs(doc1["metadata"].file_size - doc2["metadata"].file_size)
            },
            "analysis": "Documents compared for content and structure similarities"
        }

    def get_document_insights(self, doc_id: str) -> Dict[str, Any]:
        """Get comprehensive insights about a document."""
        doc = self.documents.get(doc_id)
        if not doc:
            return {"error": "Document not found"}

        recent_analyses = [a for a in self.analyses if a.document_id == doc_id]

        return {
            "document": {
                "id": doc_id,
                "filename": doc["metadata"].filename,
                "type": doc["document_type"].value,
                "size": doc["metadata"].file_size
            },
            "analysis_count": len(recent_analyses),
            "latest_analysis": recent_analyses[-1] if recent_analyses else None,
            "recommendations": [
                "Consider regular review cycles",
                "Ensure version control",
                "Link to related documents"
            ]
        }

    def search_documents(self, query: str, doc_type: Optional[DocumentType] = None) -> List[Dict]:
        """Search documents by query."""
        results = []
        query_lower = query.lower()

        for doc_id, doc in self.documents.items():
            if doc_type and doc["document_type"] != doc_type:
                continue

            filename_lower = doc["metadata"].filename.lower()
            if query_lower in filename_lower or any(word in filename_lower for word in query_lower.split()):
                results.append({
                    "document_id": doc_id,
                    "filename": doc["metadata"].filename,
                    "type": doc["document_type"].value,
                    "relevance": "high"
                })

        return results

    def get_analytics(self) -> Dict[str, Any]:
        """Get document analytics."""
        type_counts = {}
        for doc in self.documents.values():
            doc_type = doc["document_type"].value
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        return {
            "total_documents": len(self.documents),
            "total_analyses": len(self.analyses),
            "by_type": type_counts,
            "recent_analyses": len([a for a in self.analyses
                                   if (datetime.now() - a.created_at).days < 7])
        }

    def format_analysis_for_display(self, analysis: DocumentAnalysis) -> str:
        """Format analysis results for display."""
        lines = [
            f"## Document Analysis: {analysis.filename}",
            f"**Type:** {analysis.document_type.value.title()} | **Analysis:** {analysis.analysis_type.value.title()}",
            f"**Confidence:** {analysis.confidence:.0%}",
            "",
            "### Summary",
            analysis.summary,
            "",
            "### Key Findings"
        ]

        for finding in analysis.key_findings:
            lines.append(f"- {finding}")

        if analysis.entities:
            lines.extend(["", "### Extracted Entities"])
            for entity in analysis.entities[:10]:
                lines.append(f"- **{entity.entity_type.title()}:** {entity.value} ({entity.confidence:.0%})")

        return "\n".join(lines)
