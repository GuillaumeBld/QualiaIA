"""
QualiaIA Venture Manager

Autonomous business creation and lifecycle management.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import uuid

from ..config import get_config

logger = logging.getLogger(__name__)


class VentureStatus(str, Enum):
    """Venture lifecycle status"""
    IDEATION = "ideation"
    VALIDATION = "validation"
    BUILDING = "building"
    LAUNCHING = "launching"
    ACTIVE = "active"
    SCALING = "scaling"
    PAUSED = "paused"
    SHUTDOWN = "shutdown"


class VentureType(str, Enum):
    """Types of ventures"""
    ECOMMERCE = "e-commerce"
    SAAS = "saas"
    CONTENT = "content"
    SERVICE = "service"
    MARKETPLACE = "marketplace"
    OTHER = "other"


@dataclass
class VentureMetrics:
    """Venture performance metrics"""
    revenue: float = 0.0
    expenses: float = 0.0
    customers: int = 0
    conversion_rate: float = 0.0
    churn_rate: float = 0.0
    
    @property
    def profit(self) -> float:
        return self.revenue - self.expenses
    
    @property
    def margin(self) -> float:
        return self.profit / self.revenue if self.revenue > 0 else 0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "revenue": self.revenue,
            "expenses": self.expenses,
            "profit": self.profit,
            "margin": self.margin,
            "customers": self.customers,
            "conversion_rate": self.conversion_rate,
            "churn_rate": self.churn_rate,
        }


@dataclass
class Venture:
    """A QualiaIA venture/business"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    type: VentureType = VentureType.OTHER
    status: VentureStatus = VentureStatus.IDEATION
    market: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    metrics: VentureMetrics = field(default_factory=VentureMetrics)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Legal entity (optional)
    entity_type: Optional[str] = None  # "SASU", "LLC"
    jurisdiction: Optional[str] = None  # "France", "Wyoming"
    registration_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "market": self.market,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "metrics": self.metrics.to_dict(),
            "entity_type": self.entity_type,
            "jurisdiction": self.jurisdiction,
        }


class VentureManager:
    """
    Manages QualiaIA's portfolio of autonomous ventures.
    
    Features:
    - Venture creation with council approval
    - Performance monitoring
    - Scaling decisions
    - Shutdown procedures
    """
    
    def __init__(self, config=None, communication=None, council=None, wallet=None):
        if config is None:
            config = get_config().ventures
        
        self.config = config
        self.communication = communication
        self.council = council
        self.wallet = wallet
        
        # Ventures
        self.ventures: Dict[str, Venture] = {}
        
        # Thresholds
        self.thresholds = {
            "min_validation_score": config.min_validation_score,
            "min_profit_margin": config.min_profit_margin,
            "max_burn_months": config.max_burn_months,
            "scale_trigger_revenue": config.scale_trigger_revenue_usd,
            "scale_trigger_margin": config.scale_trigger_margin,
            "shutdown_loss_threshold": config.shutdown_loss_threshold_usd,
            "shutdown_consecutive_months": config.shutdown_consecutive_loss_months,
        }
    
    async def create_venture(
        self,
        name: str,
        venture_type: VentureType,
        market: str,
        initial_investment: float = 0,
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Venture]:
        """
        Create a new venture after council approval.
        
        Args:
            name: Venture name
            venture_type: Type of business
            market: Target market
            initial_investment: Initial investment amount
            description: Business description
            config: Additional configuration
            
        Returns:
            Venture if approved, None if rejected
        """
        # Council deliberation if council available
        if self.council and initial_investment > 0:
            from ..council.deliberation import get_council
            council = get_council()
            
            result = await council.deliberate(
                question=f"Should we launch new venture: {name}?",
                context={
                    "name": name,
                    "type": venture_type.value,
                    "market": market,
                    "initial_investment": initial_investment,
                    "description": description,
                }
            )
            
            if not result.consensus or result.vote != "approve":
                logger.info(f"Council rejected venture: {name}")
                if self.communication:
                    await self.communication.send(
                        event_type="venture_rejected",
                        message=f"❌ Council rejected venture: {name}\n\n{result.reasoning}"
                    )
                return None
        
        # Create venture
        venture = Venture(
            name=name,
            type=venture_type,
            market=market,
            description=description,
            config=config or {},
        )
        
        self.ventures[venture.id] = venture
        
        # Notify
        if self.communication:
            await self.communication.send(
                event_type="venture_launch",
                message=f"🚀 New venture created: {name}\n\nType: {venture_type.value}\nMarket: {market}",
                context=venture.to_dict(),
            )
        
        logger.info(f"Venture created: {name} ({venture.id})")
        return venture
    
    async def update_metrics(
        self,
        venture_id: str,
        revenue: Optional[float] = None,
        expenses: Optional[float] = None,
        customers: Optional[int] = None,
        conversion_rate: Optional[float] = None,
        churn_rate: Optional[float] = None,
    ) -> Optional[Venture]:
        """Update venture metrics"""
        if venture_id not in self.ventures:
            return None
        
        venture = self.ventures[venture_id]
        
        if revenue is not None:
            venture.metrics.revenue = revenue
        if expenses is not None:
            venture.metrics.expenses = expenses
        if customers is not None:
            venture.metrics.customers = customers
        if conversion_rate is not None:
            venture.metrics.conversion_rate = conversion_rate
        if churn_rate is not None:
            venture.metrics.churn_rate = churn_rate
        
        # Check health triggers
        await self._evaluate_health(venture)
        
        return venture
    
    async def _evaluate_health(self, venture: Venture) -> None:
        """Evaluate venture health and trigger actions"""
        
        # Shutdown trigger
        if venture.metrics.profit < self.thresholds["shutdown_loss_threshold"]:
            await self._consider_shutdown(venture)
        
        # Scale trigger
        elif (venture.status == VentureStatus.ACTIVE and
              venture.metrics.revenue > self.thresholds["scale_trigger_revenue"] and
              venture.metrics.margin > self.thresholds["scale_trigger_margin"]):
            await self._consider_scaling(venture)
    
    async def _consider_shutdown(self, venture: Venture) -> None:
        """Consider shutting down underperforming venture"""
        if self.council:
            from ..council.deliberation import get_council
            council = get_council()
            
            result = await council.deliberate(
                question=f"Should we shut down {venture.name}?",
                context={
                    "venture_id": venture.id,
                    "name": venture.name,
                    "profit": venture.metrics.profit,
                    "revenue": venture.metrics.revenue,
                    "threshold": self.thresholds["shutdown_loss_threshold"],
                }
            )
            
            if result.consensus and result.vote == "approve":
                await self.shutdown_venture(venture.id, "Accumulated losses exceeded threshold")
    
    async def _consider_scaling(self, venture: Venture) -> None:
        """Consider scaling a successful venture"""
        logger.info(f"Venture {venture.name} qualified for scaling review")
        venture.status = VentureStatus.SCALING
        
        if self.communication:
            await self.communication.send(
                event_type="venture_scaling",
                message=f"📈 {venture.name} entering scaling phase\n\nRevenue: ${venture.metrics.revenue:,.2f}\nMargin: {venture.metrics.margin:.0%}"
            )
    
    async def shutdown_venture(self, venture_id: str, reason: str = "") -> bool:
        """Shutdown a venture"""
        if venture_id not in self.ventures:
            return False
        
        venture = self.ventures[venture_id]
        venture.status = VentureStatus.SHUTDOWN
        
        if self.communication:
            await self.communication.send(
                event_type="venture_shutdown",
                message=f"🔴 Venture {venture.name} shut down\n\nReason: {reason}",
                context={
                    "venture_id": venture_id,
                    "final_revenue": venture.metrics.revenue,
                    "final_profit": venture.metrics.profit,
                }
            )
        
        logger.info(f"Venture shutdown: {venture.name} - {reason}")
        return True
    
    def get_active_ventures(self) -> List[Venture]:
        """Get all active ventures"""
        active_statuses = {
            VentureStatus.BUILDING,
            VentureStatus.LAUNCHING,
            VentureStatus.ACTIVE,
            VentureStatus.SCALING,
        }
        return [v for v in self.ventures.values() if v.status in active_statuses]
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary"""
        active = self.get_active_ventures()
        
        return {
            "total_ventures": len(self.ventures),
            "active_ventures": len(active),
            "total_revenue": sum(v.metrics.revenue for v in active),
            "total_expenses": sum(v.metrics.expenses for v in active),
            "total_profit": sum(v.metrics.profit for v in active),
            "total_customers": sum(v.metrics.customers for v in active),
            "ventures": [v.to_dict() for v in active],
        }


# Singleton
_manager: Optional[VentureManager] = None


def get_venture_manager() -> VentureManager:
    """Get venture manager singleton"""
    global _manager
    if _manager is None:
        _manager = VentureManager()
    return _manager
