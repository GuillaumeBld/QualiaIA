"""
QualiaIA Dashboard Channel

FastAPI-based web dashboard for monitoring and control.
Real-time WebSocket updates.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import logging
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..hub import Message

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class DecisionRequest(BaseModel):
    decision_id: str
    action: str  # approve, reject
    comment: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any


class DashboardChannel:
    """
    Web dashboard for QualiaIA monitoring and control.
    
    Features:
    - Real-time WebSocket feed
    - REST API for queries and actions
    - Decision approval/rejection
    - System control (pause/resume/shutdown)
    - Configuration management
    
    Configuration:
    - DASHBOARD_API_KEY: API key for authentication
    - DASHBOARD_HOST: Host to bind (default: 0.0.0.0)
    - DASHBOARD_PORT: Port to bind (default: 8080)
    - DASHBOARD_CORS_ORIGINS: Allowed CORS origins
    """
    
    def __init__(self, config):
        self.config = config
        self.api_keys = set(config.api_keys) if config.api_keys else set()
        self.active_connections: Set[WebSocket] = set()
        
        # Event buffer
        self.event_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 100
        
        # State and hub references
        self.state = None
        self.hub = None
        
        # FastAPI app
        self.app = self._create_app()
    
    def set_state(self, state) -> None:
        """Inject state reference"""
        self.state = state
    
    def set_hub(self, hub) -> None:
        """Inject hub reference"""
        self.hub = hub
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application"""
        app = FastAPI(
            title="QualiaIA Dashboard API",
            description="Control and monitoring API for QualiaIA autonomous business system",
            version="1.0.0",
        )
        
        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Routes
        @app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @app.get("/api/status")
        async def get_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            return self._get_status()
        
        @app.get("/api/wallets")
        async def get_wallets(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            return {"wallets": self.state.wallets if self.state else {}}
        
        @app.get("/api/ventures")
        async def get_ventures(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            return {"ventures": self.state.ventures if self.state else []}
        
        @app.get("/api/pending")
        async def get_pending(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            if not self.state:
                return {"pending": []}
            return {
                "pending": [d.to_dict() for d in self.state.get_pending_decisions()]
            }
        
        @app.post("/api/decide")
        async def submit_decision(
            request: DecisionRequest,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            self._verify_auth(credentials)
            
            if not self.state:
                raise HTTPException(500, "System state not available")
            
            decision = await self.state.resolve_decision(
                request.decision_id,
                request.action,
                "dashboard"
            )
            
            if not decision:
                raise HTTPException(404, "Decision not found")
            
            await self._broadcast({
                "type": "decision_resolved",
                "decision_id": request.decision_id,
                "action": request.action,
                "timestamp": datetime.now().isoformat()
            })
            
            return {"status": "recorded", "decision_id": request.decision_id}
        
        @app.post("/api/pause")
        async def pause_system(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            if self.state:
                from ..core.state import SystemStatus
                await self.state.update(status=SystemStatus.PAUSED)
                await self._broadcast({"type": "system_paused", "timestamp": datetime.now().isoformat()})
                return {"status": "paused"}
            raise HTTPException(500, "System state not available")
        
        @app.post("/api/resume")
        async def resume_system(credentials: HTTPAuthorizationCredentials = Depends(security)):
            self._verify_auth(credentials)
            if self.state:
                from ..core.state import SystemStatus
                await self.state.update(status=SystemStatus.RUNNING)
                await self._broadcast({"type": "system_resumed", "timestamp": datetime.now().isoformat()})
                return {"status": "running"}
            raise HTTPException(500, "System state not available")
        
        @app.get("/api/history")
        async def get_history(
            limit: int = Query(default=100, le=1000),
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            self._verify_auth(credentials)
            if not self.state:
                return {"events": []}
            return {"events": self.state.event_history[-limit:]}
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, api_key: Optional[str] = Query(default=None)):
            await self._handle_websocket(websocket, api_key)
        
        return app
    
    def _verify_auth(self, credentials: Optional[HTTPAuthorizationCredentials]) -> None:
        """Verify API key authentication"""
        if not self.api_keys:
            # No API keys configured - allow access (development mode)
            logger.warning("Dashboard API keys not configured - running in open mode")
            return
        
        if not credentials or credentials.credentials not in self.api_keys:
            raise HTTPException(401, "Invalid API key")
    
    def _get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        if not self.state:
            return {"status": "unknown"}
        
        return {
            "status": self.state.status.value,
            "uptime": self.state.uptime,
            "uptime_seconds": self.state.uptime_seconds,
            "start_time": self.state.start_time.isoformat(),
            "ventures_count": len(self.state.ventures),
            "pending_decisions_count": len(self.state.get_pending_decisions()),
            "wallet_total": sum(self.state.wallets.values()) if self.state.wallets else 0,
            "today": {
                "date": self.state.today.date,
                "revenue": self.state.today.revenue,
                "expenses": self.state.today.expenses,
                "profit": self.state.today.profit,
                "decisions_total": self.state.today.decisions_total,
            },
            "updated_at": datetime.now().isoformat()
        }
    
    async def _handle_websocket(self, websocket: WebSocket, api_key: Optional[str]) -> None:
        """Handle WebSocket connection"""
        # Auth check
        if self.api_keys and api_key not in self.api_keys:
            await websocket.close(code=4001, reason="Invalid API key")
            return
        
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Send buffer
        await websocket.send_json({
            "type": "buffer",
            "events": self.event_buffer[-50:]
        })
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data.get("type") == "decide" and self.state:
                    decision_id = data.get("decision_id")
                    action = data.get("action")
                    await self.state.resolve_decision(decision_id, action, "websocket")
                    await self._broadcast({
                        "type": "decision_resolved",
                        "decision_id": decision_id,
                        "action": action,
                        "timestamp": datetime.now().isoformat()
                    })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.active_connections.discard(websocket)
    
    async def _broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all WebSocket clients"""
        self.event_buffer.append(event)
        if len(self.event_buffer) > self._buffer_size:
            self.event_buffer = self.event_buffer[-self._buffer_size:]
        
        disconnected = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(event)
            except Exception:
                disconnected.add(ws)
        
        self.active_connections -= disconnected
    
    async def start(self) -> None:
        """Initialize dashboard"""
        logger.info(f"Dashboard initialized (port {self.config.port})")
    
    async def stop(self) -> None:
        """Close WebSocket connections"""
        for ws in list(self.active_connections):
            try:
                await ws.close()
            except Exception:
                pass
        self.active_connections.clear()
    
    async def send(self, message: Message) -> None:
        """Broadcast message to dashboard"""
        event = {
            "type": "message",
            "id": message.id,
            "priority": message.priority.name,
            "subject": message.subject,
            "body": message.body,
            "context": message.context,
            "timestamp": message.created_at.isoformat()
        }
        await self._broadcast(event)
    
    async def send_and_wait(self, message: Message) -> Optional[str]:
        """Dashboard responses come through API/WebSocket"""
        await self.send(message)
        return None
    
    def get_app(self) -> FastAPI:
        """Get FastAPI app for external mounting"""
        return self.app
