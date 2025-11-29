"""
QualiaIA Base Agent

Foundation for all AI agents in the system.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import uuid

import openai

from ..config import get_config

logger = logging.getLogger(__name__)


@dataclass
class AgentTask:
    """A task for an agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class BaseAgent(ABC):
    """
    Base class for QualiaIA agents.
    
    All agents use OpenRouter for LLM access, defaulting to the
    free Grok model for operational tasks.
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        self.name = name
        self.role = role
        self.config = get_config().openrouter
        
        # Default to free operational model
        self.model = model or self.config.operational_model
        
        # System prompt
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # OpenRouter client
        if not self.config.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not configured. "
                "Get your API key at https://openrouter.ai/keys"
            )
        
        self.client = openai.AsyncOpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
        )
        
        # Task history
        self.tasks: List[AgentTask] = []
        self._max_tasks = 100
        
        # Conversation memory (for multi-turn)
        self.memory: List[Dict[str, str]] = []
        self._max_memory = 20
    
    def _default_system_prompt(self) -> str:
        return f"""You are {self.name}, a {self.role} agent in the QualiaIA autonomous business system.

Your responsibilities:
- Execute tasks efficiently and accurately
- Report results in structured JSON format when requested
- Escalate uncertain decisions to the council
- Maintain compliance with spending limits and policies

Always be concise, accurate, and action-oriented."""
    
    async def think(
        self,
        prompt: str,
        use_memory: bool = False,
        json_response: bool = False,
        max_tokens: int = 1000,
    ) -> str:
        """
        Send prompt to LLM and get response.
        
        Args:
            prompt: User prompt
            use_memory: Include conversation history
            json_response: Request JSON formatted response
            max_tokens: Maximum response tokens
            
        Returns:
            LLM response text
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if use_memory:
            messages.extend(self.memory)
        
        if json_response:
            prompt += "\n\nRespond with valid JSON only."
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
            )
            
            content = response.choices[0].message.content
            
            # Update memory
            if use_memory:
                self.memory.append({"role": "user", "content": prompt})
                self.memory.append({"role": "assistant", "content": content})
                
                # Trim memory
                if len(self.memory) > self._max_memory * 2:
                    self.memory = self.memory[-self._max_memory * 2:]
            
            return content
            
        except Exception as e:
            logger.error(f"Agent {self.name} LLM error: {e}")
            raise
    
    @abstractmethod
    async def execute(self, task: AgentTask) -> Any:
        """Execute a task. Must be implemented by subclasses."""
        pass
    
    async def run_task(
        self,
        task_type: str,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentTask:
        """
        Run a task and track it.
        
        Args:
            task_type: Type of task
            description: Task description
            context: Additional context
            
        Returns:
            Completed AgentTask
        """
        task = AgentTask(
            type=task_type,
            description=description,
            context=context or {},
        )
        
        task.status = "running"
        self.tasks.append(task)
        
        try:
            result = await self.execute(task)
            task.result = result
            task.status = "completed"
        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            task.error = str(e)
            task.status = "failed"
        
        task.completed_at = datetime.now()
        
        # Trim task history
        if len(self.tasks) > self._max_tasks:
            self.tasks = self.tasks[-self._max_tasks:]
        
        return task
    
    def clear_memory(self) -> None:
        """Clear conversation memory"""
        self.memory.clear()
    
    def get_task_history(self, limit: int = 10) -> List[AgentTask]:
        """Get recent task history"""
        return self.tasks[-limit:]
