"""
QualiaIA Twilio Channel

SMS and voice calls for critical/emergency communication.
"""

import asyncio
from typing import Any, Dict, Optional
import logging

from ..hub import Message

logger = logging.getLogger(__name__)

# Twilio is optional - only import if available
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("Twilio not installed. Run: pip install twilio")


class TwilioChannel:
    """
    Twilio integration for SMS and voice calls.
    Used for CRITICAL priority messages.
    
    Configuration required:
    - TWILIO_ACCOUNT_SID: Your Twilio account SID
    - TWILIO_AUTH_TOKEN: Your Twilio auth token
    - TWILIO_FROM_NUMBER: Your Twilio phone number
    - TWILIO_TO_NUMBERS: Comma-separated list of recipient numbers
    
    Get credentials at: https://www.twilio.com/console
    """
    
    def __init__(self, config, mode: str = "sms"):
        """
        Initialize Twilio channel.
        
        Args:
            config: Twilio configuration
            mode: "sms" or "voice"
        """
        if not TWILIO_AVAILABLE:
            raise ImportError("Twilio not installed. Run: pip install twilio")
        
        self.config = config
        self.mode = mode
        self.client: Optional[TwilioClient] = None
        
        # Validate configuration
        if not config.account_sid or config.account_sid.startswith("AC" + "x" * 30):
            raise ValueError(
                "TWILIO_ACCOUNT_SID not configured. "
                "Get your credentials at https://www.twilio.com/console"
            )
        if not config.auth_token:
            raise ValueError("TWILIO_AUTH_TOKEN not configured")
        if not config.from_number:
            raise ValueError("TWILIO_FROM_NUMBER not configured")
        if not config.to_numbers:
            raise ValueError("TWILIO_TO_NUMBERS not configured")
    
    def set_state(self, state) -> None:
        """Inject state reference"""
        self.state = state
    
    def set_hub(self, hub) -> None:
        """Inject hub reference"""
        self.hub = hub
    
    async def start(self) -> None:
        """Initialize Twilio client"""
        self.client = TwilioClient(
            self.config.account_sid,
            self.config.auth_token
        )
        logger.info(f"Twilio {self.mode} channel initialized")
    
    async def stop(self) -> None:
        """Cleanup"""
        pass
    
    async def send(self, message: Message) -> None:
        """Send SMS or make voice call based on mode"""
        if not self.client:
            logger.error("Twilio client not initialized")
            return
        
        if self.mode == "sms":
            await self._send_sms(message)
        else:
            await self._make_call(message)
    
    async def send_and_wait(self, message: Message) -> Optional[str]:
        """
        Send and return None - SMS/voice responses come through webhooks.
        For real-time responses, use Telegram.
        """
        await self.send(message)
        return None
    
    async def _send_sms(self, message: Message) -> None:
        """Send SMS to all configured numbers"""
        sms_body = self._format_sms(message)
        
        loop = asyncio.get_event_loop()
        
        for to_number in self.config.to_numbers:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        body=sms_body,
                        from_=self.config.from_number,
                        to=to_number
                    )
                )
                logger.info(f"SMS sent to {to_number}")
            except Exception as e:
                logger.error(f"Failed to send SMS to {to_number}: {e}")
    
    async def _make_call(self, message: Message) -> None:
        """Make voice call with TTS message"""
        twiml = self._format_voice_twiml(message)
        
        loop = asyncio.get_event_loop()
        
        for to_number in self.config.to_numbers:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self.client.calls.create(
                        twiml=twiml,
                        from_=self.config.from_number,
                        to=to_number
                    )
                )
                logger.info(f"Voice call initiated to {to_number}")
            except Exception as e:
                logger.error(f"Failed to call {to_number}: {e}")
    
    def _format_sms(self, message: Message) -> str:
        """Format message for SMS (160 char limit for single SMS)"""
        prefix = "🚨 QUALIAIS: " if message.priority.value <= 2 else "⚠️ QualiaIA: "
        
        # Leave room for prefix and truncation indicator
        max_body_len = 140 - len(prefix)
        body = message.body[:max_body_len]
        if len(message.body) > max_body_len:
            body = body[:max_body_len - 20] + "...[CHECK TELEGRAM]"
        
        return f"{prefix}{body}"
    
    def _format_voice_twiml(self, message: Message) -> str:
        """Generate TwiML for voice call"""
        response = VoiceResponse()
        
        response.say(
            "Alert from Qualia I A autonomous system.",
            voice=self.config.voice,
            language=self.config.language
        )
        
        response.pause(length=1)
        
        if message.priority.value <= 1:
            response.say("This is a critical emergency alert.", voice=self.config.voice)
        else:
            response.say("This is an urgent notification.", voice=self.config.voice)
        
        response.pause(length=1)
        
        # Main message (truncated for voice)
        voice_body = message.body[:300]
        response.say(voice_body, voice=self.config.voice, language=self.config.language)
        
        response.pause(length=1)
        response.say(
            "Press 1 to acknowledge. Press 9 to repeat.",
            voice=self.config.voice
        )
        
        response.hangup()
        
        return str(response)
