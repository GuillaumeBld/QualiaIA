"""
QualiaIA Telegram Channel

Primary real-time communication channel.
Provides commands for monitoring and control.
"""

import asyncio
from typing import Any, Dict, List, Optional
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from ..hub import Message, Priority

logger = logging.getLogger(__name__)


class TelegramChannel:
    """
    Telegram bot for real-time QualiaIA communication.
    
    Commands:
        /start  - Welcome message
        /help   - List all commands
        /status - System status and metrics
        /balance - Wallet balances
        /pending - Pending decisions
        /ventures - List ventures
        /pause  - Pause autonomous operations
        /resume - Resume operations
        /config - View configuration
        /history - Recent activity
        /kill   - Emergency shutdown
    """
    
    def __init__(self, config):
        self.config = config
        self.authorized_users = set(config.authorized_user_ids)
        
        # Validate configuration
        if not config.bot_token or ":" not in config.bot_token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN not configured. "
                "Create a bot via @BotFather on Telegram and set the token."
            )
        
        if not self.authorized_users:
            raise ValueError(
                "TELEGRAM_AUTHORIZED_USER_IDS not configured. "
                "Get your user ID via @userinfobot on Telegram."
            )
        
        self.app: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # State and hub references (injected)
        self.state = None
        self.hub = None
        
        # Response futures for blocking calls
        self._response_futures: Dict[str, asyncio.Future] = {}
    
    def set_state(self, state) -> None:
        """Inject state reference"""
        self.state = state
    
    def set_hub(self, hub) -> None:
        """Inject hub reference"""
        self.hub = hub
    
    async def start(self) -> None:
        """Initialize and start the Telegram bot"""
        self.app = Application.builder().token(self.config.bot_token).build()
        self.bot = self.app.bot
        
        # Register command handlers
        commands = [
            ("start", self._cmd_start),
            ("help", self._cmd_help),
            ("status", self._cmd_status),
            ("balance", self._cmd_balance),
            ("pending", self._cmd_pending),
            ("ventures", self._cmd_ventures),
            ("pause", self._cmd_pause),
            ("resume", self._cmd_resume),
            ("config", self._cmd_config),
            ("history", self._cmd_history),
            ("kill", self._cmd_kill),
        ]
        
        for cmd, handler in commands:
            self.app.add_handler(CommandHandler(cmd, handler))
        
        # Callback handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Message handler for text responses
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_message
        ))
        
        # Initialize and start polling
        await self.app.initialize()
        await self.app.start()
        asyncio.create_task(self.app.updater.start_polling(drop_pending_updates=True))
        
        logger.info(f"Telegram bot started, authorized users: {self.authorized_users}")
    
    async def stop(self) -> None:
        """Stop the Telegram bot"""
        if self.app:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users
    
    async def send(self, message: Message) -> None:
        """Send a message to all authorized users"""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return
        
        emoji_map = {
            "CRITICAL": "🚨",
            "URGENT": "⚠️",
            "STANDARD": "📢",
            "ASYNC": "📧",
            "PASSIVE": "ℹ️",
        }
        
        emoji = emoji_map.get(message.priority.name, "📢")
        text = f"{emoji} **{message.subject}**\n\n{message.body}"
        
        # Truncate if too long
        if len(text) > 4096:
            text = text[:4090] + "\n\n..."
        
        for user_id in self.authorized_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=self.config.parse_mode,
                    disable_notification=(
                        message.priority >= Priority.STANDARD and 
                        self.config.disable_notification_standard
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
    
    async def send_and_wait(self, message: Message) -> Optional[str]:
        """Send message with buttons and wait for response"""
        if not self.bot:
            return None
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.id}"),
            ],
            [
                InlineKeyboardButton("🔍 More Info", callback_data=f"info_{message.id}"),
                InlineKeyboardButton("⏸️ Pause System", callback_data=f"pause_{message.id}"),
            ]
        ]
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._response_futures[message.id] = future
        
        emoji = "⚠️" if message.priority <= Priority.URGENT else "📢"
        text = f"{emoji} **{message.subject}**\n\n{message.body}"
        
        for user_id in self.authorized_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=self.config.parse_mode,
                )
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
        
        # Wait for response with timeout
        try:
            timeout = message.timeout_hours * 3600
            response = await asyncio.wait_for(future, timeout=min(timeout, 86400))
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Message {message.id} timed out")
            return None
        finally:
            self._response_futures.pop(message.id, None)
    
    async def _handle_callback(self, update: Update, context) -> None:
        """Handle inline button callbacks"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_authorized(user_id):
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        
        data = query.data
        parts = data.rsplit("_", 1)
        if len(parts) != 2:
            return
        
        action, message_id = parts
        
        await query.answer(f"Action: {action.upper()}")
        
        # Resolve waiting future
        if message_id in self._response_futures:
            self._response_futures[message_id].set_result(action)
        
        # Update message
        await query.edit_message_text(
            f"✅ **Decision Recorded**\n\n"
            f"Action: `{action.upper()}`\n"
            f"ID: `{message_id}`\n"
            f"By: {query.from_user.username or user_id}",
            parse_mode="Markdown"
        )
        
        # Handle special actions
        if action == "pause":
            if self.state:
                from ..core.state import SystemStatus
                await self.state.update(status=SystemStatus.PAUSED)
    
    async def _handle_message(self, update: Update, context) -> None:
        """Handle text message responses"""
        if not self._is_authorized(update.effective_user.id):
            return
        
        text = update.message.text.strip().lower()
        
        # Try to resolve pending futures
        for msg_id, future in list(self._response_futures.items()):
            if not future.done():
                if text in ["approve", "approved", "yes", "ok", "y", "1"]:
                    future.set_result("approve")
                    await update.message.reply_text("✅ Approved")
                elif text in ["reject", "rejected", "no", "deny", "n", "0"]:
                    future.set_result("reject")
                    await update.message.reply_text("❌ Rejected")
                break
    
    # Command handlers
    async def _cmd_start(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized. Contact QualiaIA admin.")
            return
        
        await update.message.reply_text(
            "🤖 **Welcome to QualiaIA Control**\n\n"
            "I'm your autonomous business system interface.\n\n"
            "Use /help to see available commands.",
            parse_mode="Markdown"
        )
    
    async def _cmd_help(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        help_text = """
🤖 **QualiaIA Commands**

**Monitoring**
/status - System status & metrics
/balance - Wallet balances
/ventures - List all ventures
/history - Recent activity log

**Control**
/pending - Decisions awaiting approval
/pause - Pause autonomous operations
/resume - Resume operations
/config - View configuration

**Emergency**
/kill - Emergency shutdown ⚠️

**Info**
/help - This message
"""
        await update.message.reply_text(help_text.strip(), parse_mode="Markdown")
    
    async def _cmd_status(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not self.state:
            await update.message.reply_text("⚠️ System state not available")
            return
        
        s = self.state
        wallet_total = sum(s.wallets.values()) if s.wallets else 0
        
        status = f"""
📊 **QualiaIA System Status**

**Status:** {s.status.value}
**Uptime:** {s.uptime}
**Ventures:** {len(s.ventures)}

**Today ({s.today.date}):**
• Decisions: {s.today.decisions_total} (auto: {s.today.decisions_autonomous}, council: {s.today.decisions_council}, human: {s.today.decisions_human})
• Revenue: ${s.today.revenue:,.2f}
• Expenses: ${s.today.expenses:,.2f}
• Profit: ${s.today.profit:,.2f}
• Transactions: {s.today.transactions_count}

**Wallet:** ${wallet_total:,.2f}
**Pending:** {len(s.get_pending_decisions())} decisions
"""
        await update.message.reply_text(status.strip(), parse_mode="Markdown")
    
    async def _cmd_balance(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not self.state or not self.state.wallets:
            await update.message.reply_text("💰 No wallet data available")
            return
        
        lines = ["💰 **QualiaIA Wallet Balances**\n"]
        total = 0
        for currency, balance in self.state.wallets.items():
            lines.append(f"**{currency}:** ${balance:,.2f}")
            total += balance
        lines.append(f"\n**Total:** ${total:,.2f}")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    async def _cmd_pending(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not self.state:
            await update.message.reply_text("⚠️ System state not available")
            return
        
        pending = self.state.get_pending_decisions()
        
        if not pending:
            await update.message.reply_text("📋 No pending decisions")
            return
        
        lines = ["📋 **Pending Decisions**\n"]
        for d in pending[:10]:  # Limit to 10
            amount_str = f"${d.amount:,.2f}" if d.amount else "N/A"
            lines.append(
                f"• `{d.id}` - {d.decision_type}\n"
                f"  {d.action[:50]}...\n"
                f"  Amount: {amount_str}"
            )
        
        if len(pending) > 10:
            lines.append(f"\n_...and {len(pending) - 10} more_")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    async def _cmd_ventures(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not self.state or not self.state.ventures:
            await update.message.reply_text("🏢 No active ventures")
            return
        
        lines = ["🏢 **QualiaIA Ventures**\n"]
        for v in self.state.ventures[:10]:
            lines.append(
                f"• **{v.get('name', 'Unknown')}** ({v.get('status', 'unknown')})\n"
                f"  Revenue: ${v.get('revenue', 0):,.2f}"
            )
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    async def _cmd_pause(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if self.state:
            from ..core.state import SystemStatus
            await self.state.update(status=SystemStatus.PAUSED)
        
        await update.message.reply_text(
            "⏸️ **System Paused**\n\n"
            "All autonomous operations suspended.\n"
            "Use /resume to continue.",
            parse_mode="Markdown"
        )
    
    async def _cmd_resume(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if self.state:
            from ..core.state import SystemStatus
            await self.state.update(status=SystemStatus.RUNNING)
        
        await update.message.reply_text(
            "▶️ **System Resumed**\n\n"
            "Autonomous operations reactivated.",
            parse_mode="Markdown"
        )
    
    async def _cmd_config(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        from ..config import get_config
        cfg = get_config()
        
        config_text = f"""
⚙️ **QualiaIA Configuration**

**Decision Thresholds:**
• Auto-approve: ${cfg.thresholds.auto_approve_usd:,.0f}
• Council review: ${cfg.thresholds.council_review_usd:,.0f}
• Human required: ${cfg.thresholds.human_required_usd:,.0f}

**Council:**
• Consensus: {cfg.thresholds.consensus_required:.0%}
• Min confidence: {cfg.thresholds.min_confidence:.0%}

**Wallet Limits:**
• Max single tx: ${cfg.wallet.limits.max_single_tx_usd:,.0f}
• Max daily: ${cfg.wallet.limits.max_daily_spend_usd:,.0f}

**Operational Model:**
{cfg.openrouter.operational_model}
"""
        await update.message.reply_text(config_text.strip(), parse_mode="Markdown")
    
    async def _cmd_history(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        if not self.state or not self.state.event_history:
            await update.message.reply_text("📜 No recent activity")
            return
        
        lines = ["📜 **Recent Activity**\n"]
        for event in self.state.event_history[-10:]:
            lines.append(f"• {event['timestamp'][:19]}: {event['type']}")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    async def _cmd_kill(self, update: Update, context) -> None:
        if not self._is_authorized(update.effective_user.id):
            return
        
        keyboard = [
            [
                InlineKeyboardButton("🔴 CONFIRM SHUTDOWN", callback_data="kill_confirm"),
                InlineKeyboardButton("Cancel", callback_data="kill_cancel"),
            ]
        ]
        
        await update.message.reply_text(
            "🚨 **EMERGENCY SHUTDOWN**\n\n"
            "This will immediately stop all QualiaIA operations.\n\n"
            "Are you sure?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
