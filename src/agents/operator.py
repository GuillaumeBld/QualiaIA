"""
QualiaIA Operator Agent

Main operational agent using Grok (free tier).
Handles day-to-day autonomous operations.
"""

import json
from typing import Any, Dict, List, Optional
import logging

from .base import BaseAgent, AgentTask

logger = logging.getLogger(__name__)


class OperatorAgent(BaseAgent):
    """
    Primary operational agent for QualiaIA.
    
    Uses Grok 4.1 Fast (free) via OpenRouter for cost-effective operations.
    Handles routine tasks that don't require council deliberation.
    
    Capabilities:
    - Task analysis and planning
    - Content generation
    - Data processing
    - Customer interactions
    - Routine decision making (within limits)
    """
    
    def __init__(self):
        super().__init__(
            name="Operator",
            role="Chief Operating Agent",
            model=None,  # Uses default operational_model (grok-4.1-fast:free)
            system_prompt=self._operator_prompt(),
        )
    
    def _operator_prompt(self) -> str:
        return """You are the Operator, the primary operational agent for QualiaIA autonomous business system.

Your role:
- Execute routine business operations efficiently
- Make autonomous decisions for small amounts (<$100)
- Escalate larger decisions to the Council
- Maintain operational excellence

Guidelines:
- Be concise and action-oriented
- Always consider cost-effectiveness
- Prioritize revenue-generating activities
- Document all decisions for audit

When asked for structured data, respond with valid JSON.
When uncertain, recommend escalation to the Council."""
    
    async def execute(self, task: AgentTask) -> Any:
        """Execute operator task"""
        task_type = task.type.lower()
        
        if task_type == "analyze":
            return await self._analyze(task)
        elif task_type == "generate":
            return await self._generate(task)
        elif task_type == "decide":
            return await self._decide(task)
        elif task_type == "plan":
            return await self._plan(task)
        else:
            return await self._generic(task)
    
    async def _analyze(self, task: AgentTask) -> Dict[str, Any]:
        """Analyze data or situation"""
        prompt = f"""Analyze the following:

{task.description}

Context: {json.dumps(task.context, indent=2)}

Provide analysis as JSON with:
{{
    "summary": "Brief summary",
    "findings": ["key finding 1", "key finding 2"],
    "recommendations": ["recommendation 1"],
    "confidence": 0.0-1.0,
    "escalate": true/false
}}"""
        
        response = await self.think(prompt, json_response=True)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"summary": response, "confidence": 0.5, "escalate": True}
    
    async def _generate(self, task: AgentTask) -> str:
        """Generate content"""
        content_type = task.context.get("type", "general")
        
        prompt = f"""Generate {content_type} content:

Requirements: {task.description}

Context: {json.dumps(task.context, indent=2)}

Generate professional, engaging content."""
        
        return await self.think(prompt, max_tokens=2000)
    
    async def _decide(self, task: AgentTask) -> Dict[str, Any]:
        """Make a decision"""
        amount = task.context.get("amount", 0)
        
        prompt = f"""Make a decision:

Question: {task.description}
Amount involved: ${amount}

Context: {json.dumps(task.context, indent=2)}

Respond with JSON:
{{
    "decision": "approve" or "reject" or "escalate",
    "reasoning": "Your reasoning",
    "confidence": 0.0-1.0,
    "conditions": ["any conditions"]
}}

Note: Escalate if amount > $100 or confidence < 0.7"""
        
        response = await self.think(prompt, json_response=True)
        
        try:
            result = json.loads(response)
            # Force escalation for large amounts
            if amount > 100:
                result["decision"] = "escalate"
                result["reasoning"] = f"Amount ${amount} exceeds autonomous limit"
            return result
        except json.JSONDecodeError:
            return {"decision": "escalate", "reasoning": response, "confidence": 0.5}
    
    async def _plan(self, task: AgentTask) -> Dict[str, Any]:
        """Create action plan"""
        prompt = f"""Create an action plan:

Goal: {task.description}

Context: {json.dumps(task.context, indent=2)}

Respond with JSON:
{{
    "goal": "Restated goal",
    "steps": [
        {{"step": 1, "action": "...", "duration": "...", "resources": []}},
    ],
    "timeline": "Estimated total time",
    "budget": 0.0,
    "risks": ["potential risk 1"],
    "success_metrics": ["metric 1"]
}}"""
        
        response = await self.think(prompt, json_response=True)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"goal": task.description, "steps": [], "error": "Failed to parse plan"}
    
    async def _generic(self, task: AgentTask) -> str:
        """Handle generic task"""
        prompt = f"""Execute task:

Type: {task.type}
Description: {task.description}

Context: {json.dumps(task.context, indent=2)}

Provide helpful response."""
        
        return await self.think(prompt)
    
    async def quick_response(self, query: str) -> str:
        """Quick response without task tracking"""
        return await self.think(query)
    
    async def summarize(self, content: str, max_length: int = 200) -> str:
        """Summarize content"""
        prompt = f"Summarize in {max_length} characters or less:\n\n{content}"
        return await self.think(prompt, max_tokens=500)


# Singleton
_operator: Optional[OperatorAgent] = None


def get_operator() -> OperatorAgent:
    """Get operator singleton"""
    global _operator
    if _operator is None:
        _operator = OperatorAgent()
    return _operator
