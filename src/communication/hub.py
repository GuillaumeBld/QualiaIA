"""
QualiaIA Communication Hub

Central router for all human-AI communication.
Routes messages to appropriate channels based on priority.
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
import logging

from ..config import get_config
from ..core.state import get_state, PendingDecision

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Message priority levels"""
    CRITICAL = 1   # Phone/SMS - immediate response needed
    URGENT = 2     # Telegram - minutes response time
    STANDARD = 3   # Discord/Telegram - hours response time
    ASYNC = 4      # Email - days response time
    PASSIVE = 5    # Dashboard only - on-demand


class Channel(str, Enum):
    """Available communication channels"""
    PHONE = "phone"
    SMS = "sms"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    DASHBOARD = "dashboard"


@dataclass
class Message:
    """A communication message"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    priority: Priority = Priority.STANDARD
    subject: str = ""
    body: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    requires_response: bool = False
    timeout_hours: int = 24
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority.name,
            "subject": self.subject,
            "body": self.body,
            "context": self.context,
            "requires_response": self.requires_response,
            "timeout_hours": self.timeout_hours,
            "created_at": self.created_at.isoformat(),
        }


# Event type to priority mapping
EVENT_PRIORITY_MAP = {
    # Critical - immediate human attention required
    "security_breach": Priority.CRITICAL,
    "unauthorized_access": Priority.CRITICAL,
    "wallet_drained": Priority.CRITICAL,
    "system_compromised": Priority.CRITICAL,
    "emergency_shutdown": Priority.CRITICAL,
    
    # Urgent - response needed within minutes
    "wallet_balance_low": Priority.URGENT,
    "transaction_failed": Priority.URGENT,
    "threshold_exceeded": Priority.URGENT,
    "council_deadlock": Priority.URGENT,
    "high_value_approval": Priority.URGENT,
    "legal_decision_required": Priority.URGENT,
    "agent_hire_approval": Priority.URGENT,
    "error_rate_high": Priority.URGENT,
    
    # Standard - response within hours
    "opportunity_found": Priority.STANDARD,
    "task_completed": Priority.STANDARD,
    "venture_status_update": Priority.STANDARD,
    "market_alert": Priority.STANDARD,
    "council_decision": Priority.STANDARD,
    "system_started": Priority.STANDARD,
    "system_paused": Priority.STANDARD,
    "system_resumed": Priority.STANDARD,
    
    # Async - response within days
    "daily_report": Priority.ASYNC,
    "weekly_summary": Priority.ASYNC,
    "monthly_report": Priority.ASYNC,
    "legal_document_review": Priority.ASYNC,
    "tax_filing_reminder": Priority.ASYNC,
    "venture_launch": Priority.ASYNC,
    
    # Passive - no notification, dashboard only
    "audit_log": Priority.PASSIVE,
    "metrics_update": Priority.PASSIVE,
    "debug_info": Priority.PASSIVE,
    "heartbeat": Priority.PASSIVE,
}


class CommunicationHub:
    """
    Central communication hub for QualiaIA.
    
    Routes messages to appropriate channels based on priority.
    Manages pending decisions and human approvals.
    """
    
    def __init__(self):
        self.config = get_config().communication
        self.state = get_state()
        
        # Channel instances (lazy loaded)
        self._channels: Dict[Channel, Any] = {}
        self._initialized = False
        
        # Message history
        self.message_history: List[Message] = []
        self._max_history = 1000
        
        # Response callbacks
        self._response_callbacks: Dict[str, asyncio.Future] = {}
    
    async def initialize(self) -> None:
        """Initialize all enabled communication channels"""
        if self._initialized:
            return
        
        logger.info("Initializing communication channels...")
        
        # Import and initialize channels
        from .channels.telegram import TelegramChannel
        from .channels.twilio import TwilioChannel
        from .channels.discord import DiscordChannel
        from .channels.email import EmailChannel
        from .channels.dashboard import DashboardChannel
        
        # Telegram (required)
        try:
            self._channels[Channel.TELEGRAM] = TelegramChannel(self.config.telegram)
            await self._channels[Channel.TELEGRAM].start()
            logger.info("✓ Telegram channel initialized")
        except Exception as e:
            logger.error(f"✗ Telegram initialization failed: {e}")
            raise  # Telegram is required
        
        # Twilio (optional)
        if self.config.twilio.enabled:
            try:
                self._channels[Channel.SMS] = TwilioChannel(self.config.twilio, mode="sms")
                self._channels[Channel.PHONE] = TwilioChannel(self.config.twilio, mode="voice")
                await self._channels[Channel.SMS].start()
                await self._channels[Channel.PHONE].start()
                logger.info("✓ Twilio (SMS/Voice) initialized")
            except Exception as e:
                logger.warning(f"✗ Twilio initialization failed: {e}")
        
        # Discord (optional)
        if self.config.discord.enabled:
            try:
                self._channels[Channel.DISCORD] = DiscordChannel(self.config.discord)
                await self._channels[Channel.DISCORD].start()
                logger.info("✓ Discord channel initialized")
            except Exception as e:
                logger.warning(f"✗ Discord initialization failed: {e}")
        
        # Email (optional)
        if self.config.email.enabled:
            try:
                self._channels[Channel.EMAIL] = EmailChannel(self.config.email)
                await self._channels[Channel.EMAIL].start()
                logger.info("✓ Email channel initialized")
            except Exception as e:
                logger.warning(f"✗ Email initialization failed: {e}")
        
        # Dashboard (always available)
        try:
            self._channels[Channel.DASHBOARD] = DashboardChannel(self.config.dashboard)
            await self._channels[Channel.DASHBOARD].start()
            logger.info("✓ Dashboard channel initialized")
        except Exception as e:
            logger.warning(f"✗ Dashboard initialization failed: {e}")
        
        # Inject state into channels
        for channel in self._channels.values():
            if hasattr(channel, 'set_state'):
                channel.set_state(self.state)
            if hasattr(channel, 'set_hub'):
                channel.set_hub(self)
        
        self._initialized = True
        logger.info(f"Communication hub initialized with {len(self._channels)} channels")
    
    async def shutdown(self) -> None:
        """Shutdown all channels"""
        for name, channel in self._channels.items():
            try:
                if hasattr(channel, 'stop'):
                    await channel.stop()
                logger.info(f"Channel {name} stopped")
            except Exception as e:
                logger.error(f"Error stopping channel {name}: {e}")
        
        self._channels.clear()
        self._initialized = False
    
    def _get_priority_for_event(self, event_type: str) -> Priority:
        """Get priority level for event type"""
        return EVENT_PRIORITY_MAP.get(event_type, Priority.STANDARD)
    
    def _get_channels_for_priority(self, priority: Priority) -> List[Channel]:
        """Get ordered list of channels for priority level"""
        routing = self.config.priority_routing
        
        if priority == Priority.CRITICAL:
            channels = routing.get("critical", ["phone", "sms", "telegram"])
        elif priority == Priority.URGENT:
            channels = routing.get("urgent", ["telegram", "sms"])
        elif priority == Priority.STANDARD:
            channels = routing.get("standard", ["discord", "telegram"])
        elif priority == Priority.ASYNC:
            channels = routing.get("async", ["email"])
        else:
            channels = routing.get("passive", ["dashboard"])
        
        return [Channel(c) for c in channels if Channel(c) in self._channels]
    
    async def send(
        self,
        event_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        priority: Optional[Priority] = None,
        require_response: bool = False,
        timeout_hours: int = 24,
    ) -> Optional[str]:
        """
        Send a message through appropriate channels.
        
        Args:
            event_type: Type of event (determines default priority)
            message: Message body
            context: Additional context data
            priority: Override default priority
            require_response: Wait for human response
            timeout_hours: Timeout for response
            
        Returns:
            Response string if require_response=True, else None
        """
        if not self._initialized:
            await self.initialize()
        
        # Determine priority
        if priority is None:
            priority = self._get_priority_for_event(event_type)
        
        # Create message
        msg = Message(
            priority=priority,
            subject=event_type.replace("_", " ").title(),
            body=message,
            context=context or {},
            requires_response=require_response,
            timeout_hours=timeout_hours,
        )
        
        # Store in history
        self.message_history.append(msg)
        if len(self.message_history) > self._max_history:
            self.message_history = self.message_history[-self._max_history:]
        
        # Record event
        await self.state.record_event(event_type, {
            "message_id": msg.id,
            "priority": priority.name,
            "body_preview": message[:100],
        })
        
        # Get channels for this priority
        channels = self._get_channels_for_priority(priority)
        
        if not channels:
            logger.warning(f"No channels available for priority {priority.name}")
            return None
        
        # Send through channels
        for channel_type in channels:
            channel = self._channels.get(channel_type)
            if not channel:
                continue
            
            try:
                if require_response and hasattr(channel, 'send_and_wait'):
                    response = await channel.send_and_wait(msg)
                    if response:
                        return response
                else:
                    await channel.send(msg)
                    if not require_response:
                        return None
            except Exception as e:
                logger.error(f"Failed to send via {channel_type}: {e}")
                continue
        
        return None
    
    async def request_approval(
        self,
        decision_type: str,
        action: str,
        amount: Optional[float] = None,
        reason: str = "",
        council_recommendation: Optional[str] = None,
        council_confidence: Optional[float] = None,
        timeout_hours: int = 24,
    ) -> tuple[bool, Optional[str]]:
        """
        Request human approval for a decision.
        
        Args:
            decision_type: Type of decision (financial, operational, etc.)
            action: Description of the action
            amount: Dollar amount if applicable
            reason: Reason for the decision
            council_recommendation: Council's recommendation if consulted
            council_confidence: Council's confidence level
            timeout_hours: Hours before auto-reject
            
        Returns:
            Tuple of (approved: bool, comment: Optional[str])
        """
        # Create pending decision
        decision = PendingDecision(
            id=str(uuid.uuid4())[:8],
            decision_type=decision_type,
            action=action,
            amount=amount,
            reason=reason,
            council_recommendation=council_recommendation,
            council_confidence=council_confidence,
            timeout_hours=timeout_hours,
        )
        
        # Add to state
        await self.state.add_pending_decision(decision)
        
        # Format message
        amount_str = f"${amount:,.2f}" if amount else "N/A"
        council_str = council_recommendation or "Not consulted"
        confidence_str = f"{council_confidence:.0%}" if council_confidence else "N/A"
        
        message = f"""
🔔 **APPROVAL REQUIRED**

**ID:** `{decision.id}`
**Type:** {decision_type}
**Action:** {action}
**Amount:** {amount_str}
**Reason:** {reason}

**Council:** {council_str}
**Confidence:** {confidence_str}

⏰ Auto-reject in {timeout_hours}h if no response

Reply: APPROVE / REJECT
"""
        
        # Determine priority based on amount
        if amount and amount > 2000:
            priority = Priority.URGENT
        else:
            priority = Priority.STANDARD
        
        # Send and wait for response
        response = await self.send(
            event_type="high_value_approval",
            message=message.strip(),
            context=decision.to_dict(),
            priority=priority,
            require_response=True,
            timeout_hours=timeout_hours,
        )
        
        # Process response
        if response:
            response_lower = response.lower().strip()
            approved = response_lower in ["approve", "approved", "yes", "ok", "y", "1"]
            await self.state.resolve_decision(decision.id, "approved" if approved else "rejected", "human")
            return approved, response
        
        # Timeout
        await self.state.resolve_decision(decision.id, "timeout", "system")
        return False, "Timeout - auto-rejected"
    
    async def broadcast(
        self,
        message: str,
        priority: Priority = Priority.CRITICAL,
        channels: Optional[List[Channel]] = None,
    ) -> None:
        """Broadcast message to multiple channels simultaneously"""
        if channels is None:
            channels = list(self._channels.keys())
        
        msg = Message(
            priority=priority,
            subject="Broadcast",
            body=message,
        )
        
        tasks = []
        for channel_type in channels:
            channel = self._channels.get(channel_type)
            if channel:
                tasks.append(channel.send(msg))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def emergency_shutdown_alert(self, reason: str) -> None:
        """Send emergency alert through ALL channels"""
        message = f"""
🚨🚨🚨 **EMERGENCY SHUTDOWN** 🚨🚨🚨

QualiaIA autonomous system has initiated emergency shutdown.

**Reason:** {reason}
**Time:** {datetime.now().isoformat()}

All operations suspended. Manual intervention required.
"""
        await self.broadcast(message.strip(), Priority.CRITICAL)
    
    def get_pending_decisions(self) -> List[PendingDecision]:
        """Get all pending decisions"""
        return self.state.get_pending_decisions()
    
    def get_message_history(self, limit: int = 100) -> List[Message]:
        """Get recent message history"""
        return sorted(
            self.message_history,
            key=lambda m: m.created_at,
            reverse=True
        )[:limit]


# Global hub singleton
_hub: Optional[CommunicationHub] = None


async def get_hub() -> CommunicationHub:
    """Get global communication hub singleton"""
    global _hub
    if _hub is None:
        _hub = CommunicationHub()
        await _hub.initialize()
    return _hub
