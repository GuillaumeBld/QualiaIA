"""
QualiaIA API

FastAPI application combining dashboard and external APIs.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .config import get_config
from .core.state import get_state
from .main import get_qualiaIA


security = HTTPBearer(auto_error=False)


# Request/Response models
class DecisionRequest(BaseModel):
    action: str
    amount: float = 0
    context: Optional[Dict[str, Any]] = None


class VentureCreateRequest(BaseModel):
    name: str
    type: str = "other"
    market: str
    description: str = ""
    initial_investment: float = 0


class PaymentRequest(BaseModel):
    to_address: str
    amount: float
    currency: str = "USDC"
    reason: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    qualiaIA = get_qualiaIA()
    asyncio.create_task(qualiaIA.start())
    yield
    # Shutdown
    await qualiaIA.stop("API shutdown")


app = FastAPI(
    title="QualiaIA API",
    description="Autonomous Business System API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.communication.dashboard.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key"""
    api_keys = set(config.communication.dashboard.api_keys)
    if not api_keys:
        return  # No auth in dev mode
    if not credentials or credentials.credentials not in api_keys:
        raise HTTPException(401, "Invalid API key")


# Health endpoints
@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/ready")
async def ready():
    """Readiness check"""
    state = get_state()
    from .core.state import SystemStatus
    
    is_ready = state.status in (SystemStatus.RUNNING, SystemStatus.PAUSED)
    return {
        "ready": is_ready,
        "status": state.status.value,
        "timestamp": datetime.now().isoformat()
    }


# System endpoints
@app.get("/api/v1/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    """Get system status"""
    state = get_state()
    return state.to_dict()


@app.post("/api/v1/pause", dependencies=[Depends(verify_api_key)])
async def pause_system():
    """Pause autonomous operations"""
    qualiaIA = get_qualiaIA()
    from .core.state import SystemStatus
    await qualiaIA.state.update(status=SystemStatus.PAUSED)
    return {"status": "paused"}


@app.post("/api/v1/resume", dependencies=[Depends(verify_api_key)])
async def resume_system():
    """Resume autonomous operations"""
    qualiaIA = get_qualiaIA()
    from .core.state import SystemStatus
    await qualiaIA.state.update(status=SystemStatus.RUNNING)
    return {"status": "running"}


@app.post("/api/v1/shutdown", dependencies=[Depends(verify_api_key)])
async def shutdown_system(background_tasks: BackgroundTasks, reason: str = "API request"):
    """Gracefully shutdown system"""
    qualiaIA = get_qualiaIA()
    background_tasks.add_task(qualiaIA.stop, reason)
    return {"status": "shutting_down", "reason": reason}


# Decision endpoints
@app.post("/api/v1/decide", dependencies=[Depends(verify_api_key)])
async def make_decision(request: DecisionRequest):
    """Make a decision through the tier system"""
    qualiaIA = get_qualiaIA()
    approved, reason = await qualiaIA.make_decision(
        action=request.action,
        amount=request.amount,
        context=request.context or {}
    )
    return {
        "approved": approved,
        "reason": reason,
        "action": request.action,
        "amount": request.amount
    }


@app.get("/api/v1/decisions/pending", dependencies=[Depends(verify_api_key)])
async def get_pending_decisions():
    """Get pending decisions"""
    state = get_state()
    return {
        "pending": [d.to_dict() for d in state.get_pending_decisions()]
    }


# Wallet endpoints
@app.get("/api/v1/wallet", dependencies=[Depends(verify_api_key)])
async def get_wallet_info():
    """Get wallet information"""
    from .core.wallet import get_wallet
    wallet = await get_wallet()
    balances = await wallet.get_balances()
    
    return {
        "address": wallet.address or "NOT_CONFIGURED",
        "network": wallet.network,
        "balances": balances,
        "daily_spent": float(wallet.daily_spent),
        "daily_limit": float(wallet.max_daily),
        "approved_addresses": list(wallet.approved_addresses)
    }


@app.post("/api/v1/wallet/send", dependencies=[Depends(verify_api_key)])
async def send_payment(request: PaymentRequest):
    """Send payment (requires approval for large amounts)"""
    from decimal import Decimal
    from .core.wallet import get_wallet
    
    qualiaIA = get_qualiaIA()
    wallet = await get_wallet()
    
    # Decision through tier system
    approved, reason = await qualiaIA.make_decision(
        action=f"Send ${request.amount} {request.currency} to {request.to_address}",
        amount=request.amount,
        context={"reason": request.reason, "recipient": request.to_address}
    )
    
    if not approved:
        return {"success": False, "reason": reason}
    
    # Execute payment
    tx = await wallet.send_payment(
        to_address=request.to_address,
        amount=Decimal(str(request.amount)),
        currency=request.currency,
        metadata={"reason": request.reason}
    )
    
    if tx:
        return {"success": True, "transaction": tx.to_dict()}
    return {"success": False, "reason": "Transaction blocked by spending controls"}


@app.get("/api/v1/wallet/transactions", dependencies=[Depends(verify_api_key)])
async def get_transactions(limit: int = 100):
    """Get transaction history"""
    from .core.wallet import get_wallet
    wallet = await get_wallet()
    return {
        "transactions": [tx.to_dict() for tx in wallet.get_transaction_history(limit)]
    }


# Venture endpoints
@app.get("/api/v1/ventures", dependencies=[Depends(verify_api_key)])
async def get_ventures():
    """Get all ventures"""
    from .core.ventures import get_venture_manager
    manager = get_venture_manager()
    return manager.get_portfolio_summary()


@app.post("/api/v1/ventures", dependencies=[Depends(verify_api_key)])
async def create_venture(request: VentureCreateRequest):
    """Create a new venture"""
    from .core.ventures import get_venture_manager, VentureType
    
    manager = get_venture_manager()
    
    try:
        venture_type = VentureType(request.type)
    except ValueError:
        venture_type = VentureType.OTHER
    
    venture = await manager.create_venture(
        name=request.name,
        venture_type=venture_type,
        market=request.market,
        description=request.description,
        initial_investment=request.initial_investment,
    )
    
    if venture:
        return {"success": True, "venture": venture.to_dict()}
    return {"success": False, "reason": "Venture creation rejected"}


@app.get("/api/v1/ventures/{venture_id}", dependencies=[Depends(verify_api_key)])
async def get_venture(venture_id: str):
    """Get venture details"""
    from .core.ventures import get_venture_manager
    manager = get_venture_manager()
    
    if venture_id not in manager.ventures:
        raise HTTPException(404, "Venture not found")
    
    return manager.ventures[venture_id].to_dict()


@app.delete("/api/v1/ventures/{venture_id}", dependencies=[Depends(verify_api_key)])
async def shutdown_venture(venture_id: str, reason: str = "Manual shutdown"):
    """Shutdown a venture"""
    from .core.ventures import get_venture_manager
    manager = get_venture_manager()
    
    success = await manager.shutdown_venture(venture_id, reason)
    if success:
        return {"success": True, "venture_id": venture_id}
    raise HTTPException(404, "Venture not found")


# Council endpoints
@app.post("/api/v1/council/deliberate", dependencies=[Depends(verify_api_key)])
async def council_deliberate(question: str, context: Optional[Dict[str, Any]] = None):
    """Request council deliberation"""
    from .council.deliberation import get_council
    council = get_council()
    
    result = await council.deliberate(question, context or {})
    return result.to_dict()


# Mount dashboard if enabled
if config.communication.dashboard.enabled:
    from .communication.channels.dashboard import DashboardChannel
    dashboard = DashboardChannel(config.communication.dashboard)
    app.mount("/dashboard", dashboard.get_app())


# Run with: uvicorn src.api:app --host 0.0.0.0 --port 8080
