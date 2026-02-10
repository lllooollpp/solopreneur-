"""
Agent Definition Data Model

Defines the structure for configurable agents.
"""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent type classification."""
    SUBAGENT = "subagent"      # Can be spawned as sub-agent
    MASTER = "master"          # Main coordinator agent
    STANDALONE = "standalone"  # Independent agent


class AgentDefinition(BaseModel):
    """
    Complete definition of an Agent.
    
    All fields are configurable via YAML/JSON.
    """
    # Identity
    name: str = Field(..., description="Unique identifier for the agent")
    type: AgentType = Field(default=AgentType.SUBAGENT, description="Agent type")
    title: str = Field(..., description="Display name")
    emoji: str = Field(default="🤖", description="Visual identifier")
    description: str = Field(default="", description="Brief description of agent's purpose")
    
    # Core behavior
    system_prompt: str = Field(..., description="System prompt defining agent's behavior")
    
    # Capabilities
    tools: list[str] | None = Field(
        default=None, 
        description="Allowed tools (None = all tools available)"
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Skills to load for this agent"
    )
    
    # Execution parameters
    max_iterations: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Maximum tool call iterations per request"
    )
    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
        description="Temperature override (None = use global default)"
    )
    max_tokens: int | None = Field(
        default=None,
        description="Max tokens override (None = use global default)"
    )
    
    # Output format guidance
    output_format: str = Field(
        default="",
        description="Expected output format guidance"
    )
    
    # Metadata for organization
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (domain, version, tags, etc.)"
    )
    
    # Inheritance
    extends: str | None = Field(
        default=None,
        description="Name of parent agent to inherit from"
    )
    
    class Config:
        extra = "allow"  # Allow additional custom fields


class AgentPreset(BaseModel):
    """
    A collection of agent definitions (a domain/field).
    
    Example: "software", "medical", "legal"
    """
    name: str
    description: str
    agents: list[AgentDefinition]
