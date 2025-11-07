"""
Topic Agent - Generates questions based on predefined topics
"""
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class TopicAgentImpl(BaseAgent):
    def __init__(self):
        super().__init__("topic_agent", "🎯 Topic Agent")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute topic agent logic"""
        state["current_agent"] = self.display_name
        self.log_start(state)
        
        # Check if we've exhausted all topics
        if state["current_topic_index"] >= len(state["topics"]):
            state["interview_complete"] = True
            self.log_end(state, {"interview_complete": True})
            return state
        
        # Set current topic
        current_topic = state["topics"][state["current_topic_index"]]
        state["current_topic"] = current_topic
        state["topic_iteration_count"] = 0
        state["judge_retry_count"] = 0
        
        # Get LLM
        model = get_llm()
        
        # Invoke LLM with prompt manager (auto-fills from state)
        response = self.invoke_llm(model, state)
        state["current_question"] = response.content.strip()
        
        # Track tokens
        state = self.track_tokens(state, response)
        
        # Add to conversation history
        state["conversation_history"].append({
            "agent": "topic_agent",
            "topic": current_topic['topic'],
            "question": state["current_question"],
            "tokens": state["last_message_tokens"]
        })
        
        # Set flag to wait for user input
        state["waiting_for_user_input"] = True
        
        self.log_end(state, {
            "question": state["current_question"],
            "waiting_for_user_input": True
        })
        
        return state


# Create singleton instance
_topic_agent_instance = TopicAgentImpl()


def topic_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Topic Agent entry point"""
    return _topic_agent_instance(state)
