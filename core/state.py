"""
State definition for the interview system
"""
from typing import TypedDict


class InterviewState(TypedDict):
    """State shared across all agents in the interview workflow"""
    
    # Topic management
    topics: list[dict]
    current_topic_index: int
    current_topic: dict
    topic_iteration_count: int
    max_iterations_per_topic: int
    
    # Question and answer tracking
    current_question: str
    user_answer: str
    
    # Agent decisions
    security_passed: bool
    security_feedback: str
    topic_depth_sufficient: bool
    topic_feedback: str
    
    # Judge retry tracking
    judge_retry_count: int  # How many times judge has asked to retry
    max_judge_retries: int  # Maximum retries allowed before moving on
    
    # Interview flow
    interview_complete: bool
    conversation_history: list[dict]
    final_feedback: str  # Comprehensive feedback from feedback_agent
    
    # Agent and token tracking
    current_agent: str
    total_tokens: int
    last_message_tokens: int
    
    # Control flags
    waiting_for_user_input: bool  # Flag to pause execution
