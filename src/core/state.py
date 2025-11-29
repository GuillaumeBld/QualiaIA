"""
QualiaIA State Management

Centralized state for the autonomous system.
Thread-safe, observable, and persistent.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class SystemStatus(str, Enum):
    """System operational status"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"


@dataclass
class DailyMetrics:
    """Daily operational metrics"""
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    revenue: float = 0.0
    expenses: float = 0.0
    decisions_total: int = 0
    decisions_autonomous: int = 0
    decisions_council: int = 0
    decisions_human: int = 0
    transactions_count: int = 0
    transactions_volume: float = 0.0
    errors_count: int = 0
    
    @property
    def profit(self) -> float:
        return self.revenue - self.expenses
    
    def reset(self):
        """Reset for new day"""
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.revenue = 0.0
        self.expenses = 0.0
        self.decisions_total = 0
        self.decisions_autonomous = 0
        self.decisions_council = 0
        self.decisions_human = 0
        self.transactions_count = 0
        self.transactions_volume = 0.0
        self.errors_count = 0


@dataclass
class PendingDecision:
    """A decision awaiting approval"""
    id: str
    decision_type: str  # "financial", "operational", "legal", "strategic"
    action: str
    amount: Optional[float]
    reason: str
    council_recommendation: Optional[str] = None
    council_confidence: Optional[float] = None
    status: str = "pending"  # pending, approved, rejected, timeout
    created_at: datetime = field(default_factory=datetime.now)
    timeout_hours: int = 24
    responded_at: Optional[datetime] = None
    responded_by: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.created_at + timedelta(hours=self.timeout_hours)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "decision_type": self.decision_type,
            "action": self.action,
            "amount": self.amount,
            "reason": self.reason,
            "council_recommendation": self.council_recommendation,
            "council_confidence": self.council_confidence,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "timeout_hours": self.timeout_hours,
            "is_expired": self.is_expired,
        }


class SystemState:
    """
    Centralized state management for QualiaIA.
    
    Thread-safe with asyncio locks.
    Supports observers for state changes.
    """
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._observers: Dict[str, List[Callable]] = {}
        
        # Core state
        self.status = SystemStatus.INITIALIZING
        self.start_time = datetime.now()
        
        # Wallet balances
        self.wallets: Dict[str, float] = {}
        
        # Ventures
        self.ventures: List[Dict[str, Any]] = []
        
        # Daily metrics
        self.today = DailyMetrics()
        
        # Pending decisions
        self.pending_decisions: Dict[str, PendingDecision] = {}
        
        # Configuration cache
        self.config: Dict[str, Any] = {}
        
        # Event history (last 1000)
        self.event_history: List[Dict[str, Any]] = []
        self._max_history = 1000
    
    @property
    def uptime(self) -> str:
        """Get formatted uptime string"""
        delta = datetime.now() - self.start_time
        return str(delta).split('.')[0]  # Remove microseconds
    
    @property
    def uptime_seconds(self) -> int:
        """Get uptime in seconds"""
        return int((datetime.now() - self.start_time).total_seconds())
    
    async def update(self, **kwargs) -> None:
        """Update state values and notify observers"""
        async with self._lock:
            changed_keys = []
            for key, value in kwargs.items():
                if hasattr(self, key):
                    old_value = getattr(self, key)
                    if old_value != value:
                        setattr(self, key, value)
                        changed_keys.append(key)
            
            # Notify observers
            for key in changed_keys:
                await self._notify(key, kwargs[key])
    
    async def add_pending_decision(self, decision: PendingDecision) -> None:
        """Add a pending decision"""
        async with self._lock:
            self.pending_decisions[decision.id] = decision
            await self._notify("pending_decision_added", decision)
    
    async def resolve_decision(
        self, 
        decision_id: str, 
        status: str, 
        responded_by: str
    ) -> Optional[PendingDecision]:
        """Resolve a pending decision"""
        async with self._lock:
            if decision_id not in self.pending_decisions:
                return None
            
            decision = self.pending_decisions[decision_id]
            decision.status = status
            decision.responded_at = datetime.now()
            decision.responded_by = responded_by
            
            await self._notify("decision_resolved", decision)
            return decision
    
    def get_pending_decisions(self, status: str = "pending") -> List[PendingDecision]:
        """Get decisions by status"""
        return [
            d for d in self.pending_decisions.values() 
            if d.status == status
        ]
    
    async def record_decision(self, decision_type: str) -> None:
        """Record a decision in metrics"""
        async with self._lock:
            self.today.decisions_total += 1
            if decision_type == "autonomous":
                self.today.decisions_autonomous += 1
            elif decision_type == "council":
                self.today.decisions_council += 1
            elif decision_type == "human":
                self.today.decisions_human += 1
    
    async def record_transaction(self, amount: float, is_expense: bool = True) -> None:
        """Record a transaction in metrics"""
        async with self._lock:
            self.today.transactions_count += 1
            self.today.transactions_volume += abs(amount)
            if is_expense:
                self.today.expenses += abs(amount)
            else:
                self.today.revenue += abs(amount)
    
    async def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record an event in history"""
        async with self._lock:
            event = {
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            self.event_history.append(event)
            
            # Trim history
            if len(self.event_history) > self._max_history:
                self.event_history = self.event_history[-self._max_history:]
            
            await self._notify("event", event)
    
    async def check_daily_reset(self) -> bool:
        """Check and reset daily metrics if needed"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.today.date != today:
            async with self._lock:
                old_metrics = self.today
                self.today = DailyMetrics()
                await self._notify("daily_reset", old_metrics)
                return True
        return False
    
    def subscribe(self, event: str, callback: Callable) -> None:
        """Subscribe to state changes"""
        if event not in self._observers:
            self._observers[event] = []
        self._observers[event].append(callback)
    
    def unsubscribe(self, event: str, callback: Callable) -> None:
        """Unsubscribe from state changes"""
        if event in self._observers:
            self._observers[event] = [
                cb for cb in self._observers[event] if cb != callback
            ]
    
    async def _notify(self, event: str, data: Any) -> None:
        """Notify observers of state change"""
        callbacks = self._observers.get(event, []) + self._observers.get("*", [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, data)
                else:
                    callback(event, data)
            except Exception as e:
                logger.error(f"Observer callback error: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Export state as dictionary"""
        return {
            "status": self.status.value,
            "uptime": self.uptime,
            "uptime_seconds": self.uptime_seconds,
            "start_time": self.start_time.isoformat(),
            "wallets": self.wallets,
            "ventures_count": len(self.ventures),
            "pending_decisions_count": len(self.get_pending_decisions()),
            "today": {
                "date": self.today.date,
                "revenue": self.today.revenue,
                "expenses": self.today.expenses,
                "profit": self.today.profit,
                "decisions_total": self.today.decisions_total,
                "decisions_autonomous": self.today.decisions_autonomous,
                "decisions_council": self.today.decisions_council,
                "decisions_human": self.today.decisions_human,
                "transactions_count": self.today.transactions_count,
                "transactions_volume": self.today.transactions_volume,
                "errors_count": self.today.errors_count,
            }
        }
    
    def to_json(self) -> str:
        """Export state as JSON"""
        return json.dumps(self.to_dict(), indent=2)


# Global state singleton
_state: Optional[SystemState] = None


def get_state() -> SystemState:
    """Get global state singleton"""
    global _state
    if _state is None:
        _state = SystemState()
    return _state
