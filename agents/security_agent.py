"""
Security Agent - Validates answer relevance and quality
"""
import json
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class SecurityAgentImpl(BaseAgent):
    def __init__(self):
        super().__init__("security_agent", "🔒 Security Agent")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security agent logic"""
        state["current_agent"] = self.display_name
        self.log_start(state)
        
        # Log user input
        if self.logger:
            self.logger.log_user_input(
                state.get("current_question", ""),
                state.get("user_answer", "")
            )
        
        # Reset waiting flag
        state["waiting_for_user_input"] = False
        
        # Check for empty answer
        if not state.get("user_answer") or state["user_answer"].strip() == "":
            state["security_passed"] = False
            state["security_feedback"] = "No answer provided"
            if self.logger:
                self.logger.log_security_check(False, "No answer provided")
            self.log_end(state, {"passed": False, "reason": "empty_answer"})
            return state
        
        # Get LLM
        model = get_llm()
        
        # Invoke LLM with prompt manager
        response = self.invoke_llm(model, state)
        state = self.track_tokens(state, response)
        
        # Parse response
        try:
            # Strip markdown code blocks
            response_text = response.content.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
            state["security_passed"] = result.get("passed", False)
            state["security_feedback"] = result.get("feedback", "")
            
            # Reset judge retry counter if passed
            if state["security_passed"]:
                state["judge_retry_count"] = 0
                
        except json.JSONDecodeError:
            # Fallback - be lenient
            state["security_passed"] = len(state["user_answer"]) > 10
            state["security_feedback"] = "" if state["security_passed"] else "Please provide a more detailed answer"
            
            if state["security_passed"]:
                state["judge_retry_count"] = 0
            
            if self.logger:
                self.logger.log_error("json_parse_error", "Failed to parse security agent response", {
                    "response": response.content.strip()
                })
        
        if self.logger:
            self.logger.log_security_check(state["security_passed"], state["security_feedback"])
        
        # Store in conversation history
        state["conversation_history"].append({
            "type": "user_answer",
            "question": state["current_question"],
            "answer": state["user_answer"],
            "passed": state["security_passed"]
        })
        
        self.log_end(state, {
            "passed": state["security_passed"],
            "feedback": state["security_feedback"]
        })
        
        return state


# Create singleton instance
_security_agent_instance = SecurityAgentImpl()


def security_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Security Agent entry point"""
    return _security_agent_instance(state)
