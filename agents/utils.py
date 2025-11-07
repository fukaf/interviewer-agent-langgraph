"""
Utility functions for agents
"""
from typing import Dict, Any


def move_to_next_topic(state: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to advance to the next topic
    
    Args:
        state: Current interview state
        
    Returns:
        Updated state with incremented topic index
    """
    state["current_topic_index"] += 1
    
    # Check if we've reached the end
    if state["current_topic_index"] >= len(state["topics"]):
        state["interview_complete"] = True
    
    return state


def human_input_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Human-in-the-Loop (HITL) node that pauses graph execution for user input.
    
    This node serves as an interrupt point where the graph pauses
    and waits for user input via Streamlit's chat interface.
    
    Args:
        state: Current interview state
        
    Returns:
        Unchanged state (this node just marks an interrupt point)
    """
    return state
