"""
Graph construction and routing logic for the interview system
"""
from typing import Literal
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .state import InterviewState
from agents import (
    topic_agent, security_agent, judge_agent,
    topic_guide, probing_agent, feedback_agent,
    move_to_next_topic, human_input_node
)
from interview_logging.interview_logger import get_logger


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_after_security(state: InterviewState) -> Literal["judge", "topic_guide"]:
    """Route based on security check results"""
    result = "topic_guide" if state["security_passed"] else "judge"
    
    logger = get_logger()
    if logger:
        logger.log_routing_decision(
            "security_agent",
            result,
            f"Security {'passed' if state['security_passed'] else 'failed'}"
        )
    
    return result


def route_after_judge(state: InterviewState) -> Literal["human_input_node", "topic_guide"]:
    """Route from judge based on whether to retry or move on"""
    if state.get("waiting_for_user_input", True):
        return "human_input_node"
    else:
        return "topic_guide"


def route_after_topic_guide(state: InterviewState) -> Literal["next_topic", "probing_agent", "end"]:
    """Route based on topic depth evaluation"""
    logger = get_logger()
    
    # Check if interview manually ended
    if state.get("interview_complete", False):
        if logger:
            logger.log_routing_decision("topic_guide", "end", "Interview manually ended")
        return "end"
    
    # Check max iterations
    if state["topic_iteration_count"] >= state["max_iterations_per_topic"]:
        if state["current_topic_index"] + 1 >= len(state["topics"]):
            if logger:
                logger.log_routing_decision("topic_guide", "end", "Max iterations reached and last topic")
            return "end"
        else:
            if logger:
                logger.log_routing_decision("topic_guide", "next_topic", "Max iterations reached, moving to next topic")
            return "next_topic"
    
    # Check depth
    if state["topic_depth_sufficient"]:
        if state["current_topic_index"] + 1 >= len(state["topics"]):
            if logger:
                logger.log_routing_decision("topic_guide", "end", "Depth sufficient and last topic")
            return "end"
        else:
            if logger:
                logger.log_routing_decision("topic_guide", "next_topic", "Depth sufficient, moving to next topic")
            return "next_topic"
    else:
        if logger:
            logger.log_routing_decision("topic_guide", "probing_agent", "Depth insufficient, asking follow-up")
        return "probing_agent"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_interview_graph():
    """Construct the multi-agent interview workflow graph with HITL interrupts
    
    Graph Flow:
    START 
      └→ topic_agent (generates first question)
           └→ human_input_node (INTERRUPT - waits for user)
                └→ security_agent (validates answer)
                     ├─ Failed → judge_agent (provides feedback)
                     │            └→ human_input_node (INTERRUPT - waits for retry)
                     │                  └→ security_agent (validates retry)
                     │
                     └─ Passed → topic_guide (evaluates depth)
                                  ├─ Not deep → probing_agent (follow-up)
                                  │              └→ human_input_node (INTERRUPT)
                                  │                    └→ security_agent
                                  │
                                  ├─ Deep enough → next_topic → topic_agent → human_input_node
                                  │
                                  └─ All done → feedback_agent → END
    """
    
    # Create workflow with checkpointer for interrupt/resume
    workflow = StateGraph(InterviewState)
    
    # Add all agent nodes
    workflow.add_node("topic_agent", topic_agent)
    workflow.add_node("security_agent", security_agent)
    workflow.add_node("judge", judge_agent)
    workflow.add_node("topic_guide", topic_guide)
    workflow.add_node("probing_agent", probing_agent)
    workflow.add_node("next_topic", move_to_next_topic)
    workflow.add_node("human_input_node", human_input_node)
    workflow.add_node("feedback_agent", feedback_agent)
    
    # Start with topic_agent
    workflow.add_edge(START, "topic_agent")
    
    # Question agents → HITL
    workflow.add_edge("topic_agent", "human_input_node")
    workflow.add_edge("probing_agent", "human_input_node")
    
    # Judge - conditional
    workflow.add_conditional_edges(
        "judge",
        route_after_judge,
        {
            "human_input_node": "human_input_node",
            "topic_guide": "topic_guide"
        }
    )
    
    # HITL → security_agent
    workflow.add_edge("human_input_node", "security_agent")
    
    # Security validates answer
    workflow.add_conditional_edges(
        "security_agent",
        route_after_security,
        {
            "judge": "judge",
            "topic_guide": "topic_guide"
        }
    )
    
    # Topic guide evaluates depth
    workflow.add_conditional_edges(
        "topic_guide",
        route_after_topic_guide,
        {
            "next_topic": "next_topic",
            "probing_agent": "probing_agent",
            "end": "feedback_agent"
        }
    )
    
    # Next topic preparation
    workflow.add_edge("next_topic", "topic_agent")
    
    # Feedback agent ends
    workflow.add_edge("feedback_agent", END)
    
    # Compile with checkpointer and interrupt
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_input_node"]
    )
