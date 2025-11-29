"""
Tests for QualiaIA State Management
"""

import pytest
from datetime import datetime

from src.core.state import SystemState, SystemStatus, PendingDecision


@pytest.fixture
def state():
    return SystemState()


class TestSystemState:
    def test_initial_status(self, state):
        assert state.status == SystemStatus.INITIALIZING
    
    def test_uptime_format(self, state):
        uptime = state.uptime
        assert isinstance(uptime, str)
        assert ":" in uptime
    
    @pytest.mark.asyncio
    async def test_update_status(self, state):
        await state.update(status=SystemStatus.RUNNING)
        assert state.status == SystemStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_record_decision(self, state):
        await state.record_decision("autonomous")
        assert state.today.decisions_total == 1
        assert state.today.decisions_autonomous == 1
    
    @pytest.mark.asyncio
    async def test_pending_decision(self, state):
        decision = PendingDecision(
            id="test-001",
            decision_type="financial",
            action="Test action",
            amount=500.0,
            reason="Test reason",
        )
        
        await state.add_pending_decision(decision)
        pending = state.get_pending_decisions()
        
        assert len(pending) == 1
        assert pending[0].id == "test-001"
    
    @pytest.mark.asyncio
    async def test_resolve_decision(self, state):
        decision = PendingDecision(
            id="test-002",
            decision_type="operational",
            action="Test action",
            amount=None,
            reason="Test reason",
        )
        
        await state.add_pending_decision(decision)
        resolved = await state.resolve_decision("test-002", "approved", "tester")
        
        assert resolved.status == "approved"
        assert resolved.responded_by == "tester"
    
    def test_to_dict(self, state):
        result = state.to_dict()
        
        assert "status" in result
        assert "uptime" in result
        assert "today" in result
        assert "wallets" in result
