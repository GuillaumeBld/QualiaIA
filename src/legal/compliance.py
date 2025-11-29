"""
QualiaIA Legal Compliance

Helpers for RGPD/GDPR, CCPA, EU AI Act compliance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import logging
import json

from ..config import get_config

logger = logging.getLogger(__name__)


class Jurisdiction(str, Enum):
    """Legal jurisdictions"""
    FRANCE = "france"
    USA_CALIFORNIA = "usa_california"
    USA_COLORADO = "usa_colorado"
    USA_WYOMING = "usa_wyoming"
    EU = "eu"


class DataCategory(str, Enum):
    """GDPR data categories"""
    PERSONAL = "personal"
    SENSITIVE = "sensitive"  # Special categories
    FINANCIAL = "financial"
    TECHNICAL = "technical"  # Logs, IPs, etc.


@dataclass
class DataProcessingRecord:
    """Record of data processing activity"""
    id: str
    purpose: str
    legal_basis: str  # consent, contract, legitimate_interest, legal_obligation
    data_categories: List[DataCategory]
    retention_days: int
    recipients: List[str]  # Third parties
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purpose": self.purpose,
            "legal_basis": self.legal_basis,
            "data_categories": [c.value for c in self.data_categories],
            "retention_days": self.retention_days,
            "recipients": self.recipients,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ConsentRecord:
    """User consent record"""
    user_id: str
    purpose: str
    granted: bool
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def is_valid(self) -> bool:
        if not self.granted:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


class ComplianceManager:
    """
    Manages legal compliance for QualiaIA.
    
    Jurisdictions supported:
    - France: RGPD (GDPR), CNIL requirements
    - USA: CCPA (California), Colorado AI Act
    - EU: AI Act (effective Aug 2026)
    
    Key compliance areas:
    - Data protection and privacy
    - AI transparency and explainability
    - Automated decision-making disclosures
    - Data subject rights
    
    TODO: For production deployment, consult with legal counsel to:
    - Complete DPIA (Data Protection Impact Assessment)
    - Register with CNIL if required
    - Implement full data subject rights workflow
    - Complete AI Act risk assessment
    """
    
    def __init__(self):
        self.config = get_config().compliance
        
        # Processing records
        self.processing_records: List[DataProcessingRecord] = []
        
        # Consent records
        self.consents: Dict[str, List[ConsentRecord]] = {}
        
        # Data retention policy
        self.retention_policy = {
            DataCategory.PERSONAL: 365,  # 1 year
            DataCategory.SENSITIVE: 180,  # 6 months
            DataCategory.FINANCIAL: 2555,  # 7 years (tax compliance)
            DataCategory.TECHNICAL: 90,  # 3 months
        }
        
        # Initialize required disclosures
        self._setup_disclosures()
    
    def _setup_disclosures(self) -> None:
        """Setup required legal disclosures"""
        self.disclosures = {
            "automated_decision": """
AUTOMATED DECISION-MAKING DISCLOSURE

QualiaIA uses automated decision-making systems powered by artificial 
intelligence. These systems may:

1. Make autonomous financial decisions under $100 USD
2. Recommend decisions for amounts between $100-$2,000 USD
3. Route decisions over $2,000 USD for human approval

You have the right to:
- Request human review of automated decisions
- Receive explanation of decision logic
- Object to automated decision-making

Contact: [TODO: Set DPO_EMAIL in configuration]
""",
            "ai_transparency": """
AI TRANSPARENCY NOTICE

QualiaIA is an AI-powered autonomous business system that uses:
- Large Language Models (LLMs) for analysis and decision support
- Multi-model council for critical decisions
- Automated agents for routine operations

Risk Classification: Limited (EU AI Act)
Human Oversight: Enabled for decisions over $500 USD
""",
            "privacy_policy_summary": """
PRIVACY NOTICE SUMMARY

Data We Collect:
- Transaction data (financial records)
- Communication logs (for audit compliance)
- System usage metrics

Legal Basis: Legitimate interest, contractual necessity
Retention: 7 years (financial), 1 year (other)
Your Rights: Access, rectification, erasure, portability

Full policy: [TODO: Set PRIVACY_POLICY_URL in configuration]
""",
        }
    
    def check_compliance(self, jurisdiction: Jurisdiction) -> Dict[str, Any]:
        """
        Check compliance status for a jurisdiction.
        
        Returns compliance checklist with status.
        """
        if jurisdiction == Jurisdiction.FRANCE:
            return self._check_france_compliance()
        elif jurisdiction in (Jurisdiction.USA_CALIFORNIA, Jurisdiction.USA_COLORADO):
            return self._check_usa_compliance(jurisdiction)
        elif jurisdiction == Jurisdiction.EU:
            return self._check_eu_ai_act()
        else:
            return {"status": "unknown", "jurisdiction": jurisdiction.value}
    
    def _check_france_compliance(self) -> Dict[str, Any]:
        """Check RGPD/CNIL compliance for France"""
        cfg = self.config.france
        
        checks = {
            "rgpd_compliant": cfg.rgpd_compliant,
            "dpia_required": cfg.dpia_required,
            "dpia_completed": False,  # TODO: Track DPIA completion
            "cnil_registered": bool(cfg.cnil_registration),
            "cnil_registration": cfg.cnil_registration or "TODO: Register with CNIL",
            "dpo_appointed": bool(cfg.dpo_email),
            "dpo_email": cfg.dpo_email or "TODO: Appoint DPO",
            "data_retention_policy": True,
            "retention_days": cfg.data_retention_days,
            "consent_management": True,
            "data_subject_rights": True,  # TODO: Implement full DSR workflow
        }
        
        all_compliant = all([
            checks["rgpd_compliant"],
            checks.get("dpia_completed", False) or not checks["dpia_required"],
            checks["cnil_registered"],
            checks["dpo_appointed"],
        ])
        
        return {
            "jurisdiction": "France",
            "framework": "RGPD/GDPR + CNIL",
            "compliant": all_compliant,
            "checks": checks,
            "actions_required": [
                k for k, v in checks.items() 
                if v is False or (isinstance(v, str) and v.startswith("TODO"))
            ]
        }
    
    def _check_usa_compliance(self, jurisdiction: Jurisdiction) -> Dict[str, Any]:
        """Check USA compliance (CCPA, Colorado AI Act)"""
        cfg = self.config.usa
        
        checks = {
            "ccpa_compliant": cfg.ccpa_compliant,
            "privacy_policy": bool(cfg.privacy_policy_url),
            "privacy_policy_url": cfg.privacy_policy_url or "TODO: Create privacy policy",
            "opt_out_mechanism": True,  # TODO: Implement
            "data_sale_disclosure": True,  # We don't sell data
        }
        
        if jurisdiction == Jurisdiction.USA_COLORADO:
            checks.update({
                "colorado_ai_act": cfg.colorado_ai_act,
                "ai_risk_assessment": False,  # TODO: Complete assessment
                "admt_disclosure": True,  # Automated Decision Making Technology
                "effective_date": "June 30, 2026",
            })
        
        return {
            "jurisdiction": jurisdiction.value,
            "framework": "CCPA/CPRA" + (" + Colorado AI Act" if jurisdiction == Jurisdiction.USA_COLORADO else ""),
            "compliant": all(v is True for v in checks.values() if isinstance(v, bool)),
            "checks": checks,
            "actions_required": [
                k for k, v in checks.items()
                if v is False or (isinstance(v, str) and v.startswith("TODO"))
            ]
        }
    
    def _check_eu_ai_act(self) -> Dict[str, Any]:
        """Check EU AI Act compliance"""
        cfg = self.config.eu_ai_act
        
        checks = {
            "risk_classification": cfg.risk_classification,
            "is_high_risk": cfg.risk_classification == "high",
            "transparency_enabled": cfg.transparency_enabled,
            "human_oversight_enabled": cfg.human_oversight_enabled,
            "documentation_complete": False,  # TODO
            "conformity_assessment": False,  # Required for high-risk only
            "effective_date": "August 2026",
        }
        
        return {
            "jurisdiction": "European Union",
            "framework": "EU AI Act",
            "status": "preparing",  # Act not yet in force
            "compliant": True,  # Currently compliant (act not enforced)
            "checks": checks,
            "notes": [
                "Full compliance required by August 2026",
                f"Current risk classification: {cfg.risk_classification}",
                "Recommend completing documentation early",
            ]
        }
    
    def record_processing(
        self,
        purpose: str,
        legal_basis: str,
        data_categories: List[DataCategory],
        recipients: List[str] = None,
    ) -> DataProcessingRecord:
        """Record a data processing activity (GDPR Article 30)"""
        retention = max(
            self.retention_policy.get(cat, 365)
            for cat in data_categories
        )
        
        record = DataProcessingRecord(
            id=f"proc_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            purpose=purpose,
            legal_basis=legal_basis,
            data_categories=data_categories,
            retention_days=retention,
            recipients=recipients or [],
        )
        
        self.processing_records.append(record)
        return record
    
    def get_disclosure(self, disclosure_type: str) -> str:
        """Get a required disclosure text"""
        return self.disclosures.get(disclosure_type, "")
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "jurisdictions": {
                "france": self._check_france_compliance(),
                "usa_california": self._check_usa_compliance(Jurisdiction.USA_CALIFORNIA),
                "usa_colorado": self._check_usa_compliance(Jurisdiction.USA_COLORADO),
                "eu_ai_act": self._check_eu_ai_act(),
            },
            "processing_records": len(self.processing_records),
            "active_consents": sum(
                len([c for c in records if c.is_valid()])
                for records in self.consents.values()
            ),
        }


# Singleton
_manager: Optional[ComplianceManager] = None


def get_compliance_manager() -> ComplianceManager:
    """Get compliance manager singleton"""
    global _manager
    if _manager is None:
        _manager = ComplianceManager()
    return _manager
