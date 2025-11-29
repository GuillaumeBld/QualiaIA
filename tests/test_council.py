"""
Tests for QualiaIA Council Deliberation

NOTE: These tests require mocking OpenRouter API calls.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.council.deliberation import (
    CouncilDeliberation,
    CouncilMember,
    Opinion,
    DeliberationResult,
)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI/OpenRouter response"""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"vote": "approve", "confidence": 0.85, "reasoning": "Test reasoning"}'
            )
        )
    ]
    return mock_response


class TestCouncilMember:
    def test_creation(self):
        member = CouncilMember(
            model="test/model",
            role="Test Role",
            weight=1.5
        )
        
        assert member.model == "test/model"
        assert member.role == "Test Role"
        assert member.weight == 1.5


class TestOpinion:
    def test_to_dict(self):
        member = CouncilMember("test/model", "Tester")
        opinion = Opinion(
            member=member,
            vote="approve",
            confidence=0.9,
            reasoning="Test reason"
        )
        
        result = opinion.to_dict()
        
        assert result["vote"] == "approve"
        assert result["confidence"] == 0.9
        assert result["role"] == "Tester"


class TestDeliberationResult:
    def test_to_dict(self):
        result = DeliberationResult(
            consensus=True,
            vote="approve",
            confidence=0.85,
            reasoning="Test synthesis",
            opinions=[],
            duration_seconds=5.0
        )
        
        d = result.to_dict()
        
        assert d["consensus"] is True
        assert d["vote"] == "approve"
        assert d["confidence"] == 0.85
