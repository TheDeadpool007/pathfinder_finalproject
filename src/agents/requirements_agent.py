"""
RequirementsAgent - Converts raw user input into structured TripRequirements.

Responsibilities:
- Parse user input from UI form
- Validate and structure data using Pydantic
- Optionally use LLM to enhance parsing (future improvement)
"""

import logging
from typing import Dict, Any
from src.core.models import TripRequirements

logger = logging.getLogger(__name__)


class RequirementsAgent:
    """Agent 1: Parses and structures user requirements."""
    
    def __init__(self):
        """Initialize the requirements parser."""
        logger.info("RequirementsAgent initialized")
    
    def execute(self, user_input: Dict[str, Any]) -> TripRequirements:
        """
        Convert raw user input into validated TripRequirements.
        
        Args:
            user_input: Dictionary with keys:
                - destination (str)
                - num_days (int)
                - budget_per_day (float)
                - interests (str or List[str])
                - constraints (str or List[str])
        
        Returns:
            TripRequirements: Validated structured requirements
        """
        logger.info(f"Parsing requirements for: {user_input.get('destination', 'Unknown')}")
        
        # Deterministic parsing using Pydantic validation
        # Pydantic handles type conversion and validation automatically
        requirements = TripRequirements(
            destination=user_input.get('destination', ''),
            num_days=int(user_input.get('num_days', 3)),
            budget_per_day=float(user_input.get('budget_per_day', 100)),
            interests=user_input.get('interests', []),
            constraints=user_input.get('constraints', [])
        )
        
        logger.info(f"Requirements validated: {requirements.num_days} days, ${requirements.budget_per_day}/day")
        return requirements
