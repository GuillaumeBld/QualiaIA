"""
QualiaIA Council Deliberation

Multi-model board of directors for critical decisions.
Implements LLM Council pattern with voting and consensus.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import json

import openai

from ..config import get_config

logger = logging.getLogger(__name__)


@dataclass
class CouncilMember:
    """A member of the deliberation council"""
    model: str
    role: str
    weight: float = 1.0


@dataclass
class Opinion:
    """A council member's opinion on a decision"""
    member: CouncilMember
    vote: str  # "approve", "reject", "abstain"
    confidence: float  # 0.0 to 1.0
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.member.model,
            "role": self.member.role,
            "vote": self.vote,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class DeliberationResult:
    """Result of council deliberation"""
    consensus: bool
    vote: str  # "approve", "reject", "no_consensus"
    confidence: float
    reasoning: str
    opinions: List[Opinion]
    duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus": self.consensus,
            "vote": self.vote,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "opinions": [o.to_dict() for o in self.opinions],
            "duration_seconds": self.duration_seconds,
        }


class CouncilDeliberation:
    """
    Multi-model deliberation council for critical QualiaIA decisions.
    
    Implements a 3-phase deliberation process:
    1. Independent opinions from each council member
    2. (Optional) Peer review for high-stakes decisions
    3. Chairman synthesizes final recommendation
    
    Default council:
    - Claude Sonnet 4: Risk Analyst
    - GPT-4o: Strategy Director
    - Gemini 2.5 Pro: Finance Officer
    - Grok 3: Chairman (tie-breaker, 1.5x weight)
    
    Consensus requirement: 66% (2/3 majority)
    """
    
    def __init__(self, config=None):
        if config is None:
            config = get_config().openrouter
        
        self.config = config
        
        # OpenRouter client
        if not config.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not configured. "
                "Get your API key at https://openrouter.ai/keys"
            )
        
        self.client = openai.AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        
        # Council members
        self.members = []
        for member_config in config.council_models:
            if isinstance(member_config, dict):
                self.members.append(CouncilMember(
                    model=member_config.get("id", ""),
                    role=member_config.get("role", "Advisor"),
                    weight=member_config.get("weight", 1.0),
                ))
            else:
                # String model ID
                self.members.append(CouncilMember(model=member_config, role="Advisor"))
        
        # Fallback if no council configured
        if not self.members:
            self.members = [
                CouncilMember("anthropic/claude-sonnet-4", "Risk Analyst", 1.0),
                CouncilMember("openai/gpt-4o", "Strategy Director", 1.0),
                CouncilMember("google/gemini-2.5-pro", "Finance Officer", 1.0),
                CouncilMember("x-ai/grok-3", "Chairman", 1.5),
            ]
        
        self.consensus_threshold = get_config().thresholds.consensus_required
        self.timeout = get_config().thresholds.council_timeout_seconds
    
    async def deliberate(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        require_consensus: bool = True,
    ) -> DeliberationResult:
        """
        Conduct council deliberation on a question.
        
        Args:
            question: The decision question
            context: Additional context (amount, action details, etc.)
            require_consensus: Whether consensus is required
            
        Returns:
            DeliberationResult with vote, confidence, and reasoning
        """
        context = context or {}
        start_time = datetime.now()
        
        logger.info(f"Council deliberation started: {question[:100]}...")
        
        # Phase 1: Gather independent opinions
        opinions = await self._gather_opinions(question, context)
        
        # Filter out failed opinions
        valid_opinions = [o for o in opinions if o.vote != "error"]
        
        if not valid_opinions:
            logger.error("All council members failed to respond")
            return DeliberationResult(
                consensus=False,
                vote="no_consensus",
                confidence=0.0,
                reasoning="All council members failed to respond",
                opinions=[],
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )
        
        # Phase 2: Synthesize result
        result = await self._synthesize(valid_opinions, question, context)
        
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"Council result: {result.vote} "
            f"(confidence: {result.confidence:.0%}, "
            f"consensus: {result.consensus})"
        )
        
        return result
    
    async def _gather_opinions(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> List[Opinion]:
        """Gather independent opinions from all council members"""
        
        system_prompt = """You are a board member of QualiaIA, an autonomous AI business system.

Your role is: {role}

Analyze the following decision and provide your independent assessment.
Consider:
- Risk factors and potential downsides
- Financial implications and ROI
- Legal and compliance concerns
- Strategic alignment with business goals
- Market timing and opportunity cost

You MUST respond with valid JSON in this exact format:
{{
    "vote": "approve" or "reject" or "abstain",
    "confidence": 0.0 to 1.0,
    "reasoning": "Your detailed reasoning (2-3 sentences)"
}}

Do not include any text outside the JSON object."""

        tasks = []
        for member in self.members:
            task = self._get_opinion(member, system_prompt, question, context)
            tasks.append(task)
        
        opinions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error opinions
        result = []
        for i, opinion in enumerate(opinions):
            if isinstance(opinion, Exception):
                logger.error(f"Member {self.members[i].model} failed: {opinion}")
                result.append(Opinion(
                    member=self.members[i],
                    vote="error",
                    confidence=0.0,
                    reasoning=str(opinion),
                ))
            else:
                result.append(opinion)
        
        return result
    
    async def _get_opinion(
        self,
        member: CouncilMember,
        system_prompt: str,
        question: str,
        context: Dict[str, Any],
    ) -> Opinion:
        """Get opinion from a single council member"""
        
        # Format context
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        
        user_message = f"""Decision Question: {question}

Context:
{context_str}

Provide your assessment as JSON."""

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=member.model,
                    messages=[
                        {"role": "system", "content": system_prompt.format(role=member.role)},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.7,
                    max_tokens=500,
                ),
                timeout=self.timeout,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            # Try to extract JSON from the response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError(f"No valid JSON found in response: {content[:200]}")
            
            return Opinion(
                member=member,
                vote=result.get("vote", "abstain").lower(),
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", "No reasoning provided"),
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting opinion from {member.model}")
            return Opinion(
                member=member,
                vote="abstain",
                confidence=0.0,
                reasoning="Timeout - no response",
            )
        except Exception as e:
            logger.error(f"Error getting opinion from {member.model}: {e}")
            return Opinion(
                member=member,
                vote="abstain",
                confidence=0.0,
                reasoning=f"Error: {e}",
            )
    
    async def _synthesize(
        self,
        opinions: List[Opinion],
        question: str,
        context: Dict[str, Any],
    ) -> DeliberationResult:
        """Synthesize final result from opinions"""
        
        # Calculate weighted votes
        approve_weight = sum(
            o.member.weight * o.confidence
            for o in opinions
            if o.vote == "approve"
        )
        reject_weight = sum(
            o.member.weight * o.confidence
            for o in opinions
            if o.vote == "reject"
        )
        total_weight = sum(o.member.weight for o in opinions if o.vote in ("approve", "reject"))
        
        if total_weight == 0:
            # All abstained
            return DeliberationResult(
                consensus=False,
                vote="no_consensus",
                confidence=0.0,
                reasoning="All council members abstained",
                opinions=opinions,
                duration_seconds=0,
            )
        
        approve_ratio = approve_weight / total_weight
        
        # Determine consensus
        if approve_ratio >= self.consensus_threshold:
            consensus = True
            vote = "approve"
            confidence = approve_ratio
        elif (1 - approve_ratio) >= self.consensus_threshold:
            consensus = True
            vote = "reject"
            confidence = 1 - approve_ratio
        else:
            consensus = False
            vote = "no_consensus"
            confidence = max(approve_ratio, 1 - approve_ratio)
        
        # Generate synthesis reasoning
        reasoning = self._generate_synthesis(opinions, vote, approve_ratio)
        
        return DeliberationResult(
            consensus=consensus,
            vote=vote,
            confidence=confidence,
            reasoning=reasoning,
            opinions=opinions,
            duration_seconds=0,
        )
    
    def _generate_synthesis(
        self,
        opinions: List[Opinion],
        vote: str,
        approve_ratio: float,
    ) -> str:
        """Generate human-readable synthesis"""
        
        lines = []
        
        # Vote summary
        approve_count = sum(1 for o in opinions if o.vote == "approve")
        reject_count = sum(1 for o in opinions if o.vote == "reject")
        abstain_count = sum(1 for o in opinions if o.vote == "abstain")
        
        lines.append(f"Council Vote: {approve_count} approve, {reject_count} reject, {abstain_count} abstain")
        lines.append(f"Weighted approval: {approve_ratio:.0%}")
        lines.append(f"Decision: {vote.upper()}")
        lines.append("")
        
        # Key reasons
        lines.append("Key considerations:")
        for o in opinions:
            if o.vote in ("approve", "reject"):
                lines.append(f"- {o.member.role}: {o.reasoning[:100]}...")
        
        return "\n".join(lines)


# Singleton
_council: Optional[CouncilDeliberation] = None


def get_council() -> CouncilDeliberation:
    """Get council singleton"""
    global _council
    if _council is None:
        _council = CouncilDeliberation()
    return _council
