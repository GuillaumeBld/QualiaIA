"""
QualiaIA x402 Server

Server component for offering QualiaIA services to other AI agents.
Implements x402 HTTP 402 Payment Required protocol.

This allows QualiaIA to monetize its capabilities by offering them
as paid API endpoints to other autonomous agents.
"""

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
import logging
import uuid

from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel

from ..config import get_config

logger = logging.getLogger(__name__)

# Try to import web3 for signature verification
try:
    from eth_account.messages import encode_typed_data
    from eth_account import Account
    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False
    logger.warning("eth_account not available for payment verification")


# USDC on Base
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


@dataclass
class ServiceDefinition:
    """Definition of an x402-enabled service"""
    name: str
    endpoint: str
    description: str
    price_usd: Decimal
    handler: Callable
    requires_auth: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "description": self.description,
            "price_usd": float(self.price_usd),
        }


@dataclass
class PaymentRecord:
    """Record of received payment"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    service: str = ""
    payer: str = ""
    amount_usd: Decimal = Decimal("0")
    signature: str = ""
    status: str = "pending"  # pending, verified, executed, failed
    task: Optional[str] = None
    result: Optional[Any] = None
    created_at: datetime = field(default_factory=datetime.now)


class PaymentRequest(BaseModel):
    """Incoming service request"""
    task: str
    parameters: Optional[Dict[str, Any]] = None


class X402Server:
    """
    x402 Payment Server for QualiaIA services.
    
    Allows QualiaIA to offer paid services to other AI agents:
    - Market analysis
    - Content generation
    - Code review
    - Data processing
    - etc.
    
    Usage:
        server = X402Server()
        server.register_service(
            name="market_analysis",
            endpoint="/x402/market-analysis",
            price_usd=Decimal("5.00"),
            handler=my_analysis_function,
        )
        
        # Mount on FastAPI app
        app.include_router(server.get_router())
    """
    
    def __init__(self, config=None):
        if config is None:
            cfg = get_config().x402
            config = cfg.server if hasattr(cfg, 'server') else {}
        
        self.config = config
        self.enabled = config.get("enabled", False) if isinstance(config, dict) else getattr(config, "enabled", False)
        
        # Receiving wallet address
        self.recipient_address = os.environ.get("WALLET_ADDRESS", "")
        if not self.recipient_address:
            # Try to derive from private key
            private_key = os.environ.get("WALLET_PRIVATE_KEY")
            if private_key and VERIFICATION_AVAILABLE:
                if not private_key.startswith("0x"):
                    private_key = f"0x{private_key}"
                self.recipient_address = Account.from_key(private_key).address
        
        # Service registry
        self.services: Dict[str, ServiceDefinition] = {}
        
        # Payment records
        self.payments: List[PaymentRecord] = []
        
        # Revenue tracking
        self.total_revenue = Decimal("0")
        self.daily_revenue = Decimal("0")
        self.daily_reset = datetime.now()
    
    def register_service(
        self,
        name: str,
        endpoint: str,
        price_usd: Decimal,
        handler: Callable,
        description: str = "",
        requires_auth: bool = True,
    ) -> None:
        """Register a paid service"""
        service = ServiceDefinition(
            name=name,
            endpoint=endpoint,
            description=description or f"QualiaIA {name} service",
            price_usd=price_usd,
            handler=handler,
            requires_auth=requires_auth,
        )
        self.services[endpoint] = service
        logger.info(f"Registered x402 service: {name} at {endpoint} (${price_usd})")
    
    def get_router(self) -> FastAPI:
        """Get FastAPI router with x402 endpoints"""
        from fastapi import APIRouter
        router = APIRouter(prefix="/x402", tags=["x402"])
        
        @router.get("/services")
        async def list_services():
            """List available paid services"""
            return {
                "services": [s.to_dict() for s in self.services.values()],
                "recipient": self.recipient_address,
                "network": "base",
                "token": USDC_BASE,
            }
        
        @router.get("/stats")
        async def get_stats():
            """Get revenue statistics"""
            self._check_daily_reset()
            return {
                "total_revenue_usd": float(self.total_revenue),
                "daily_revenue_usd": float(self.daily_revenue),
                "total_payments": len(self.payments),
                "services_count": len(self.services),
            }
        
        # Register service endpoints
        for endpoint, service in self.services.items():
            self._create_service_endpoint(router, service)
        
        return router
    
    def _create_service_endpoint(self, router, service: ServiceDefinition):
        """Create endpoint for a service"""
        from fastapi import APIRouter
        
        @router.post(service.endpoint.replace("/x402", ""))
        async def service_endpoint(request: Request, body: PaymentRequest):
            return await self._handle_service_request(request, body, service)
    
    async def _handle_service_request(
        self,
        request: Request,
        body: PaymentRequest,
        service: ServiceDefinition,
    ) -> Response:
        """Handle incoming service request with x402 flow"""
        
        # Check for payment header
        payment_header = request.headers.get("X-Payment")
        
        if not payment_header:
            # Return 402 with payment requirements
            return self._create_402_response(service)
        
        # Verify payment
        payment = self._verify_payment(payment_header, service)
        
        if not payment:
            raise HTTPException(
                status_code=402,
                detail="Invalid payment signature"
            )
        
        # Execute service
        try:
            if asyncio.iscoroutinefunction(service.handler):
                result = await service.handler(body.task, body.parameters or {})
            else:
                result = service.handler(body.task, body.parameters or {})
            
            # Record payment
            payment.status = "executed"
            payment.result = result
            self._record_payment(payment)
            
            return {"status": "success", "result": result}
            
        except Exception as e:
            payment.status = "failed"
            self._record_payment(payment)
            raise HTTPException(status_code=500, detail=str(e))
    
    def _create_402_response(self, service: ServiceDefinition) -> Response:
        """Create HTTP 402 response with payment requirements"""
        # Amount in USDC smallest unit (6 decimals)
        amount = int(service.price_usd * 10**6)
        
        payment_info = {
            "recipient": self.recipient_address,
            "amount": amount,
            "token": USDC_BASE,
            "network": "base",
            "validUntil": int(time.time()) + 300,  # 5 minutes
            "nonce": os.urandom(32).hex(),
            "description": service.description,
            "service": service.name,
        }
        
        # Base64 encode for header
        header_value = base64.b64encode(
            json.dumps(payment_info).encode()
        ).decode()
        
        return Response(
            status_code=402,
            content=json.dumps({
                "error": "Payment Required",
                "payment": payment_info,
            }),
            headers={
                "X-Payment-Required": header_value,
                "Content-Type": "application/json",
            },
        )
    
    def _verify_payment(
        self,
        payment_header: str,
        service: ServiceDefinition,
    ) -> Optional[PaymentRecord]:
        """
        Verify EIP-712 signed payment.
        
        In production, this would:
        1. Decode the payment header
        2. Recover the signer from the signature
        3. Verify the payment details match requirements
        4. Check the payer has sufficient balance (via RPC)
        5. Submit the transfer transaction
        
        For now, we do signature verification only.
        """
        try:
            # Decode header
            payload = json.loads(base64.b64decode(payment_header))
            
            signature = payload.get("payload", {}).get("signature")
            authorization = payload.get("payload", {}).get("authorization", {})
            
            if not signature or not authorization:
                logger.warning("Invalid payment structure")
                return None
            
            # Verify recipient matches
            if authorization.get("to", "").lower() != self.recipient_address.lower():
                logger.warning("Payment recipient mismatch")
                return None
            
            # Verify amount is sufficient
            required_amount = int(service.price_usd * 10**6)
            paid_amount = int(authorization.get("value", 0))
            
            if paid_amount < required_amount:
                logger.warning(f"Insufficient payment: {paid_amount} < {required_amount}")
                return None
            
            # Verify timing
            now = int(time.time())
            valid_after = int(authorization.get("validAfter", 0))
            valid_before = int(authorization.get("validBefore", 0))
            
            if now < valid_after or now > valid_before:
                logger.warning("Payment outside validity window")
                return None
            
            # TODO: In production, also:
            # 1. Recover signer address from signature
            # 2. Check signer's USDC balance via RPC
            # 3. Submit the actual transfer transaction
            # 4. Wait for confirmation
            
            # Create payment record
            payment = PaymentRecord(
                service=service.name,
                payer=authorization.get("from", "unknown"),
                amount_usd=Decimal(paid_amount) / Decimal(10**6),
                signature=signature,
                status="verified",
            )
            
            logger.info(f"Payment verified: ${payment.amount_usd} from {payment.payer}")
            return payment
            
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return None
    
    def _record_payment(self, payment: PaymentRecord) -> None:
        """Record payment and update revenue"""
        self.payments.append(payment)
        
        if payment.status == "executed":
            self._check_daily_reset()
            self.total_revenue += payment.amount_usd
            self.daily_revenue += payment.amount_usd
        
        # Keep last 10000 records
        if len(self.payments) > 10000:
            self.payments = self.payments[-10000:]
    
    def _check_daily_reset(self) -> None:
        """Reset daily counters"""
        from datetime import timedelta
        now = datetime.now()
        if now - self.daily_reset > timedelta(hours=24):
            self.daily_revenue = Decimal("0")
            self.daily_reset = now
    
    def get_payment_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent payment history"""
        return [
            {
                "id": p.id,
                "service": p.service,
                "payer": p.payer,
                "amount_usd": float(p.amount_usd),
                "status": p.status,
                "created_at": p.created_at.isoformat(),
            }
            for p in sorted(
                self.payments,
                key=lambda x: x.created_at,
                reverse=True
            )[:limit]
        ]


# =============================================================================
# Example Service Handlers
# =============================================================================

async def market_analysis_handler(task: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example handler for market analysis service.
    
    TODO: Implement actual market analysis logic.
    This would typically call the MarketScanner agent.
    """
    return {
        "task": task,
        "analysis": "Market analysis results would go here",
        "params_received": params,
        "note": "TODO: Implement actual analysis via MarketScanner agent"
    }


async def code_review_handler(task: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example handler for code review service.
    
    TODO: Implement actual code review logic.
    """
    return {
        "task": task,
        "review": "Code review results would go here",
        "params_received": params,
        "note": "TODO: Implement actual code review via OperatorAgent"
    }


# =============================================================================
# Factory
# =============================================================================

def create_x402_server() -> X402Server:
    """Create and configure x402 server with default services"""
    server = X402Server()
    
    # Register example services
    # TODO: Add real QualiaIA service handlers
    
    server.register_service(
        name="market_analysis",
        endpoint="/x402/market-analysis",
        price_usd=Decimal("5.00"),
        handler=market_analysis_handler,
        description="AI-powered market opportunity analysis",
    )
    
    server.register_service(
        name="code_review",
        endpoint="/x402/code-review",
        price_usd=Decimal("2.50"),
        handler=code_review_handler,
        description="Automated code review and suggestions",
    )
    
    return server
