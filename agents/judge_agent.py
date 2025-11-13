"""
Judge Agent - Provides feedback on failed answers
"""
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class JudgeAgentImpl(BaseAgent):
    def __init__(self):
        super().__init__("judge_agent", "⚖️ Judge Agent")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute judge agent logic"""
        state["current_agent"] = self.display_name
        self.log_start(state)
        
        # Get current retry count
        current_retry_count = state.get("judge_retry_count", 0)
        
        # Check if max retries reached
        if current_retry_count >= state.get("max_judge_retries", 2):
            judge_feedback = f"""I understand this question might be challenging. Let's move forward - we can revisit this topic later if needed. 

Your answer was: "{state["user_answer"]}"

Let me ask you about something else."""
            
            self.log_end(state, {
                "action": "max_retries_reached",
                "retry_count": current_retry_count,
                "moving_on": True,
                "question": judge_feedback
            })
            
            state["security_passed"] = True
            state["judge_retry_count"] = 0
            state["current_question"] = judge_feedback
            state["conversation_history"].append({
                "agent": "judge",
                "feedback": judge_feedback,
                "action": "max_retries_exceeded",
                "retry_count": current_retry_count
            })
            state["waiting_for_user_input"] = False
            
            return state
        
        # Increment retry counter
        state["judge_retry_count"] = current_retry_count + 1
        
        # Get LLM
        model = get_llm()
        
        # Invoke LLM with prompt manager
        response = self.invoke_llm(model, state)
        judge_feedback = response.content.strip()
        state = self.track_tokens(state, response)
        
        # Add to conversation history
        state["conversation_history"].append({
            "agent": "judge",
            "feedback": judge_feedback,
            "retry_count": state["judge_retry_count"],
            "tokens": state["last_message_tokens"]
        })
        
        # Store feedback as current message
        state["current_question"] = judge_feedback
        state["user_answer"] = ""
        state["waiting_for_user_input"] = True
        
        self.log_end(state, {
            "question": judge_feedback,
            "retry_count": state["judge_retry_count"],
            "waiting_for_user_input": True
        })
        
        return state


# Create singleton instance
_judge_agent_instance = JudgeAgentImpl()


def judge_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Judge Agent entry point"""
    return _judge_agent_instance(state)
