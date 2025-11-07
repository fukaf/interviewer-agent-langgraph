"""
Feedback Agent - Provides comprehensive feedback
"""
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class FeedbackAgentImpl(BaseAgent):
    def __init__(self):
        super().__init__("feedback_agent", "📝 Feedback Agent")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute feedback agent logic"""
        state["current_agent"] = self.display_name
        
        # Get LLM
        model = get_llm()
        
        # Invoke LLM with prompt manager (auto-fills themes_text and conversation_text)
        response = self.invoke_llm(model, state)
        state = self.track_tokens(state, response)
        
        feedback_text = response.content.strip()
        
        # Store feedback
        state["current_question"] = feedback_text
        state["conversation_history"].append({
            "agent": "feedback_agent",
            "feedback": feedback_text,
            "tokens": state["last_message_tokens"]
        })
        
        # Mark complete
        state["interview_complete"] = True
        
        return state


# Create singleton instance
_feedback_agent_instance = FeedbackAgentImpl()


def feedback_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Feedback Agent entry point"""
    return _feedback_agent_instance(state)
