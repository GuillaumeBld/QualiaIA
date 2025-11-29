"""
QualiaIA Main Entry Point

System orchestrator that initializes and coordinates all components.
"""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional
import logging

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import start_http_server, Counter, Gauge

from .config import get_config, QualiaIAConfig
from .core.state import get_state, SystemStatus
from .core.wallet import get_wallet
from .core.ventures import get_venture_manager
from .communication import get_hub, Priority
from .council.deliberation import get_council

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)

# Prometheus metrics
DECISIONS_TOTAL = Counter('qualiaIA_decisions_total', 'Total decisions', ['type', 'tier'])
TRANSACTIONS_TOTAL = Counter('qualiaIA_transactions_total', 'Total transactions', ['status'])
WALLET_BALANCE = Gauge('qualiaIA_wallet_balance_usd', 'Wallet balance in USD')
VENTURES_ACTIVE = Gauge('qualiaIA_ventures_active', 'Number of active ventures')
SYSTEM_UPTIME = Gauge('qualiaIA_uptime_seconds', 'System uptime in seconds')


class QualiaIA:
    """
    Main QualiaIA orchestrator.
    
    Coordinates all system components:
    - Communication hub (Telegram, Discord, Email, etc.)
    - Council deliberation
    - Wallet management
    - Venture management
    - Scheduled tasks
    """
    
    def __init__(self, config: Optional[QualiaIAConfig] = None):
        self.config = config or get_config()
        self.state = get_state()
        self.scheduler = AsyncIOScheduler()
        
        # Components (lazy initialized)
        self.hub = None
        self.council = None
        self.wallet = None
        self.ventures = None
        
        # Shutdown event
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Initialize and start the system"""
        logger.info("Starting QualiaIA autonomous business system...")
        
        try:
            # Initialize state
            await self.state.update(status=SystemStatus.INITIALIZING)
            
            # Start Prometheus metrics server
            if self.config.monitoring.prometheus_enabled:
                start_http_server(self.config.monitoring.prometheus_port)
                logger.info(f"Prometheus metrics on port {self.config.monitoring.prometheus_port}")
            
            # Initialize communication hub
            logger.info("Initializing communication hub...")
            self.hub = await get_hub()
            
            # Initialize council
            logger.info("Initializing council...")
            self.council = get_council()
            
            # Initialize wallet
            logger.info("Initializing wallet...")
            self.wallet = await get_wallet()
            
            # Initialize venture manager
            logger.info("Initializing venture manager...")
            self.ventures = get_venture_manager()
            self.ventures.communication = self.hub
            self.ventures.council = self.council
            self.ventures.wallet = self.wallet
            
            # Update state with wallet balance
            balances = await self.wallet.get_balances()
            await self.state.update(wallets=balances)
            WALLET_BALANCE.set(sum(balances.values()))
            
            # Setup scheduled tasks
            self._setup_scheduler()
            self.scheduler.start()
            
            # System is running
            await self.state.update(status=SystemStatus.RUNNING)
            
            # Send startup notification
            await self.hub.send(
                event_type="system_started",
                message=f"🚀 QualiaIA system started\n\nWallet: ${sum(balances.values()):,.2f} USDC\nVentures: {len(self.ventures.get_active_ventures())}",
                priority=Priority.STANDARD,
            )
            
            logger.info("QualiaIA started successfully")
            
            # Wait for shutdown
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Startup error: {e}")
            await self.state.update(status=SystemStatus.ERROR)
            raise
    
    async def stop(self, reason: str = "Manual shutdown") -> None:
        """Gracefully shutdown the system"""
        logger.info(f"Shutting down QualiaIA: {reason}")
        
        await self.state.update(status=SystemStatus.SHUTTING_DOWN)
        
        # Notify before shutdown
        if self.hub:
            await self.hub.send(
                event_type="system_shutdown",
                message=f"🔴 QualiaIA shutting down\n\nReason: {reason}",
                priority=Priority.URGENT,
            )
        
        # Stop scheduler
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        # Shutdown hub
        if self.hub:
            await self.hub.shutdown()
        
        await self.state.update(status=SystemStatus.SHUTDOWN)
        self._shutdown_event.set()
        
        logger.info("QualiaIA shutdown complete")
    
    async def emergency_shutdown(self, reason: str) -> None:
        """Emergency shutdown - alert and stop immediately"""
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")
        
        if self.hub:
            await self.hub.emergency_shutdown_alert(reason)
        
        await self.stop(f"EMERGENCY: {reason}")
    
    def _setup_scheduler(self) -> None:
        """Setup scheduled tasks"""
        cfg = self.config.scheduler
        
        # Daily report
        self.scheduler.add_job(
            self._daily_report,
            'cron',
            hour=cfg.daily_report_hour,
            minute=cfg.daily_report_minute,
            id='daily_report'
        )
        
        # Health check
        self.scheduler.add_job(
            self._health_check,
            'interval',
            seconds=cfg.health_check_interval,
            id='health_check'
        )
        
        # Balance check
        self.scheduler.add_job(
            self._balance_check,
            'interval',
            seconds=cfg.balance_check_interval,
            id='balance_check'
        )
        
        # Metrics update
        self.scheduler.add_job(
            self._update_metrics,
            'interval',
            seconds=60,
            id='metrics_update'
        )
        
        logger.info("Scheduler configured with periodic tasks")
    
    async def _daily_report(self) -> None:
        """Send daily summary report"""
        state = self.state
        ventures = self.ventures.get_portfolio_summary() if self.ventures else {}
        
        report = f"""
📊 **QualiaIA Daily Report**
📅 {datetime.now().strftime('%Y-%m-%d')}

**System**
• Status: {state.status.value}
• Uptime: {state.uptime}

**Today's Activity**
• Decisions: {state.today.decisions_total}
  - Autonomous: {state.today.decisions_autonomous}
  - Council: {state.today.decisions_council}
  - Human: {state.today.decisions_human}
• Revenue: ${state.today.revenue:,.2f}
• Expenses: ${state.today.expenses:,.2f}
• Profit: ${state.today.profit:,.2f}

**Portfolio**
• Active Ventures: {ventures.get('active_ventures', 0)}
• Total Revenue: ${ventures.get('total_revenue', 0):,.2f}
• Total Profit: ${ventures.get('total_profit', 0):,.2f}

**Wallet**
• Balance: ${sum(state.wallets.values()) if state.wallets else 0:,.2f}
"""
        
        await self.hub.send(
            event_type="daily_report",
            message=report.strip(),
            priority=Priority.ASYNC,
        )
        
        # Reset daily metrics
        await state.check_daily_reset()
    
    async def _health_check(self) -> None:
        """Periodic health check"""
        # Check wallet balance
        if self.wallet:
            balances = await self.wallet.get_balances()
            total = sum(balances.values())
            
            threshold = self.config.monitoring.alerts.wallet_low_balance_usd
            if total < threshold:
                await self.hub.send(
                    event_type="wallet_balance_low",
                    message=f"⚠️ Low wallet balance: ${total:,.2f}\n\nThreshold: ${threshold:,.2f}",
                    priority=Priority.URGENT,
                )
        
        # Check error rate
        if self.state.today.decisions_total > 0:
            error_rate = self.state.today.errors_count / self.state.today.decisions_total
            if error_rate > self.config.monitoring.alerts.error_rate_threshold:
                await self.hub.send(
                    event_type="error_rate_high",
                    message=f"⚠️ High error rate: {error_rate:.1%}",
                    priority=Priority.URGENT,
                )
    
    async def _balance_check(self) -> None:
        """Update wallet balance in state"""
        if self.wallet:
            balances = await self.wallet.get_balances()
            await self.state.update(wallets=balances)
            WALLET_BALANCE.set(sum(balances.values()))
    
    async def _update_metrics(self) -> None:
        """Update Prometheus metrics"""
        SYSTEM_UPTIME.set(self.state.uptime_seconds)
        
        if self.ventures:
            active = len(self.ventures.get_active_ventures())
            VENTURES_ACTIVE.set(active)
            await self.state.update(ventures=[v.to_dict() for v in self.ventures.get_active_ventures()])
    
    async def make_decision(
        self,
        action: str,
        amount: float = 0,
        context: dict = None,
    ) -> tuple[bool, str]:
        """
        Make a decision using the tier system.
        
        Args:
            action: Description of the action
            amount: Dollar amount involved
            context: Additional context
            
        Returns:
            Tuple of (approved: bool, reason: str)
        """
        context = context or {}
        thresholds = self.config.thresholds
        
        # Tier 1: Autonomous
        if amount < thresholds.auto_approve_usd:
            await self.state.record_decision("autonomous")
            DECISIONS_TOTAL.labels(type="autonomous", tier="1").inc()
            logger.info(f"Auto-approved: {action} (${amount})")
            return True, "Auto-approved (under threshold)"
        
        # Tier 2: Council
        if amount < thresholds.human_required_usd:
            result = await self.council.deliberate(
                question=f"Should we: {action}?",
                context={**context, "amount": amount}
            )
            
            await self.state.record_decision("council")
            DECISIONS_TOTAL.labels(type="council", tier="2").inc()
            
            if result.consensus and result.vote == "approve":
                return True, f"Council approved ({result.confidence:.0%} confidence)"
            elif result.consensus and result.vote == "reject":
                return False, f"Council rejected: {result.reasoning}"
            else:
                # No consensus - escalate to human
                pass
        
        # Tier 3: Human approval
        approved, comment = await self.hub.request_approval(
            decision_type="financial" if amount > 0 else "operational",
            action=action,
            amount=amount if amount > 0 else None,
            reason=context.get("reason", "Requires human approval"),
            council_recommendation=result.vote if 'result' in locals() else None,
            council_confidence=result.confidence if 'result' in locals() else None,
        )
        
        await self.state.record_decision("human")
        DECISIONS_TOTAL.labels(type="human", tier="3").inc()
        
        return approved, comment or "Human decision"


# Global instance
_instance: Optional[QualiaIA] = None


def get_qualiaIA() -> QualiaIA:
    """Get QualiaIA singleton"""
    global _instance
    if _instance is None:
        _instance = QualiaIA()
    return _instance


async def main():
    """Main entry point"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Configure logging level
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    qualiaIA = get_qualiaIA()
    
    # Handle signals
    loop = asyncio.get_event_loop()
    
    def handle_signal(sig):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(qualiaIA.stop(f"Signal {sig}"))
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
    
    try:
        await qualiaIA.start()
    except KeyboardInterrupt:
        await qualiaIA.stop("Keyboard interrupt")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await qualiaIA.emergency_shutdown(str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
