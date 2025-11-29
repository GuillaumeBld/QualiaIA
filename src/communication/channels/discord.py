"""
QualiaIA Discord Channel

Discord webhooks for team notifications.
Uses webhooks for simplicity - no bot token required.
"""

import asyncio
from typing import Any, Dict, Optional
import logging

import aiohttp

from ..hub import Message

logger = logging.getLogger(__name__)


class DiscordChannel:
    """
    Discord webhook integration for team/community updates.
    
    Configuration required:
    - DISCORD_ALERTS_WEBHOOK: Webhook URL for alerts channel
    - DISCORD_STATUS_WEBHOOK: Webhook URL for status updates
    - DISCORD_VENTURES_WEBHOOK: Webhook URL for venture updates
    
    Create webhooks: Server Settings -> Integrations -> Webhooks
    """
    
    def __init__(self, config):
        self.config = config
        self.webhooks = config.webhooks or {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Validate at least one webhook
        if not any(self.webhooks.values()):
            raise ValueError(
                "No Discord webhooks configured. "
                "Create webhooks in your Discord server and set DISCORD_*_WEBHOOK env vars."
            )
    
    def set_state(self, state) -> None:
        """Inject state reference"""
        self.state = state
    
    def set_hub(self, hub) -> None:
        """Inject hub reference"""
        self.hub = hub
    
    async def start(self) -> None:
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("Discord channel initialized")
    
    async def stop(self) -> None:
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    async def send(self, message: Message) -> None:
        """Send message via Discord webhook"""
        if not self.session:
            logger.error("Discord session not initialized")
            return
        
        webhook_url = self._get_webhook_for_message(message)
        if not webhook_url:
            logger.warning("No Discord webhook for this message type")
            return
        
        embed = self._format_embed(message)
        
        try:
            async with self.session.post(
                webhook_url,
                json={"embeds": [embed]}
            ) as response:
                if response.status not in (200, 204):
                    text = await response.text()
                    logger.error(f"Discord webhook failed: {response.status} - {text}")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
    
    async def send_and_wait(self, message: Message) -> Optional[str]:
        """Discord webhooks don't support responses"""
        await self.send(message)
        return None
    
    def _get_webhook_for_message(self, message: Message) -> Optional[str]:
        """Determine which webhook to use"""
        subject_lower = message.subject.lower()
        
        if any(word in subject_lower for word in ["alert", "error", "critical", "urgent", "emergency"]):
            return self.webhooks.get("alerts")
        elif any(word in subject_lower for word in ["status", "report", "summary", "metrics"]):
            return self.webhooks.get("status")
        elif any(word in subject_lower for word in ["venture", "business", "launch", "shutdown"]):
            return self.webhooks.get("ventures")
        
        # Default to alerts or first available
        return (
            self.webhooks.get("alerts") or 
            self.webhooks.get("status") or 
            next(iter(self.webhooks.values()), None)
        )
    
    def _format_embed(self, message: Message) -> Dict[str, Any]:
        """Format message as Discord embed"""
        color_map = {
            1: 0xFF0000,  # CRITICAL - Red
            2: 0xFFA500,  # URGENT - Orange
            3: 0x00FF00,  # STANDARD - Green
            4: 0x0000FF,  # ASYNC - Blue
            5: 0x808080,  # PASSIVE - Gray
        }
        
        embed = {
            "title": f"📢 {message.subject}",
            "description": message.body[:4096],
            "color": color_map.get(message.priority.value, 0x00FF00),
            "timestamp": message.created_at.isoformat(),
            "footer": {
                "text": f"QualiaIA • Priority: {message.priority.name}"
            }
        }
        
        # Add fields from context
        if message.context:
            fields = []
            for key, value in list(message.context.items())[:25]:
                fields.append({
                    "name": key.replace("_", " ").title(),
                    "value": str(value)[:1024],
                    "inline": True
                })
            if fields:
                embed["fields"] = fields
        
        return embed
