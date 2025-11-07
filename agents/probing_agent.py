"""
Probing Agent - Generates follow-up questions
"""
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class ProbingAgentImpl(BaseAgent):
    def __init__(self):
        super().__init__("probing_agent", "🔍 Probing Agent")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute probing agent logic"""
        state["current_agent"] = self.display_name
        self.log_start(state)
        
        # Increment iteration count
        state["topic_iteration_count"] = state.get("topic_iteration_count", 0) + 1
        
        # Get LLM
        model = get_llm()
        
        # Invoke LLM with prompt manager
        response = self.invoke_llm(model, state)
        state["current_question"] = response.content.strip()
        state = self.track_tokens(state, response)
        
        # Add to conversation history
        state["conversation_history"].append({
            "agent": "probing_agent",
            "question": state["current_question"],
            "tokens": state["last_message_tokens"]
        })
        
        # Clear user answer and wait for input
        state["user_answer"] = ""
        state["waiting_for_user_input"] = True
        
        self.log_end(state, {
            "question": state["current_question"],
            "waiting_for_user_input": True
        })
        
        return state


# Create singleton instance
_probing_agent_instance = ProbingAgentImpl()


def probing_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Probing Agent entry point"""
    return _probing_agent_instance(state)
