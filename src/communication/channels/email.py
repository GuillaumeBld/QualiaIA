"""
QualiaIA Email Channel

SMTP email for formal asynchronous communications.
Reports, legal documents, summaries.
"""

import asyncio
from typing import Any, Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from pathlib import Path
import re

import aiosmtplib

from ..hub import Message

logger = logging.getLogger(__name__)


class EmailChannel:
    """
    Email integration for formal communications.
    
    Configuration required:
    - SMTP_HOST: SMTP server (e.g., smtp.gmail.com)
    - SMTP_PORT: SMTP port (e.g., 587)
    - SMTP_USERNAME: Email username
    - SMTP_PASSWORD: Email password (use App Password for Gmail)
    - EMAIL_FROM: From address
    - EMAIL_TO: Comma-separated recipient addresses
    
    For Gmail: Enable 2FA, then create App Password at
    https://myaccount.google.com/apppasswords
    """
    
    def __init__(self, config):
        self.config = config
        
        # Validate configuration
        if not config.smtp.username:
            raise ValueError(
                "SMTP_USERNAME not configured. "
                "Set your email address in the configuration."
            )
        if not config.smtp.password:
            raise ValueError(
                "SMTP_PASSWORD not configured. "
                "For Gmail, create an App Password at https://myaccount.google.com/apppasswords"
            )
        if not config.to_addresses:
            raise ValueError("EMAIL_TO not configured")
    
    def set_state(self, state) -> None:
        """Inject state reference"""
        self.state = state
    
    def set_hub(self, hub) -> None:
        """Inject hub reference"""
        self.hub = hub
    
    async def start(self) -> None:
        """Validate email configuration"""
        logger.info("Email channel initialized")
    
    async def stop(self) -> None:
        """Cleanup"""
        pass
    
    async def send(self, message: Message) -> None:
        """Send email to all configured recipients"""
        html_body = self._format_html(message)
        
        for to_email in self.config.to_addresses:
            await self._send_email(
                to=to_email,
                subject=f"[QualiaIA] {message.subject}",
                html_body=html_body,
            )
    
    async def send_and_wait(self, message: Message) -> Optional[str]:
        """Email doesn't support real-time responses"""
        await self.send(message)
        return None
    
    async def _send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
    ) -> None:
        """Send single email"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.from_address or self.config.smtp.username
        msg["To"] = to
        
        # Plain text fallback
        plain_text = re.sub(r'<[^>]+>', '', html_body)
        plain_text = plain_text.replace("&nbsp;", " ")
        
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp.host,
                port=self.config.smtp.port,
                start_tls=self.config.smtp.use_tls,
                username=self.config.smtp.username,
                password=self.config.smtp.password,
            )
            logger.info(f"Email sent to {to}: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
    
    def _format_html(self, message: Message) -> str:
        """Format message as HTML email"""
        priority_colors = {
            1: "#dc3545",  # CRITICAL - Red
            2: "#ffc107",  # URGENT - Orange/Yellow
            3: "#28a745",  # STANDARD - Green
            4: "#007bff",  # ASYNC - Blue
            5: "#6c757d",  # PASSIVE - Gray
        }
        
        color = priority_colors.get(message.priority.value, "#28a745")
        
        # Build context section if available
        context_html = ""
        if message.context:
            context_items = "".join(
                f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'><strong>{k.replace('_', ' ').title()}</strong></td>"
                f"<td style='padding:8px;border-bottom:1px solid #eee;'>{v}</td></tr>"
                for k, v in message.context.items()
            )
            context_html = f"""
            <h3 style="color:#333;margin-top:20px;">Details</h3>
            <table style="width:100%;border-collapse:collapse;">
                {context_items}
            </table>
            """
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:0;background:#f5f5f5;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:24px;">QualiaIA</h1>
            <p style="margin:5px 0 0 0;opacity:0.9;font-size:14px;">Autonomous Business System</p>
        </div>
        
        <div style="background:white;padding:20px;border-radius:0 0 8px 8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
            <span style="display:inline-block;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:bold;background:{color};color:white;">
                {message.priority.name}
            </span>
            
            <h2 style="color:#333;margin:15px 0 10px 0;">{message.subject}</h2>
            
            <div style="color:#555;line-height:1.6;white-space:pre-wrap;">{message.body}</div>
            
            {context_html}
            
            <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
            
            <p style="color:#999;font-size:12px;margin:0;">
                Message ID: {message.id}<br>
                Time: {message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
            </p>
        </div>
        
        <div style="text-align:center;padding:20px;color:#999;font-size:12px;">
            <p>QualiaIA Autonomous Business System<br>
            This is an automated message.</p>
        </div>
    </div>
</body>
</html>
"""
