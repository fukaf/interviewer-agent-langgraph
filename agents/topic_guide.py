"""
Topic Guide - Evaluates answer depth and completeness
"""
import json
from typing import Dict, Any
from .base_agent import BaseAgent
from core.utils import get_llm


class TopicGuideImpl(BaseAgent):
    def __init__(self):
        super().__init__("topic_guide", "📊 Topic Guide")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute topic guide logic"""
        state["current_agent"] = self.display_name
        self.log_start(state)
        
        state["topic_iteration_count"] += 1
        
        # Check max iterations
        if state["topic_iteration_count"] >= state["max_iterations_per_topic"]:
            state["topic_depth_sufficient"] = True
            state["topic_feedback"] = "Max iterations reached"
            if self.logger:
                self.logger.log_topic_evaluation(True, "Max iterations reached")
            self.log_end(state, {"depth_sufficient": True, "reason": "max_iterations"})
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
            state["topic_depth_sufficient"] = result.get("depth_sufficient", False)
            state["topic_feedback"] = result.get("feedback", "")
        except json.JSONDecodeError:
            state["topic_depth_sufficient"] = len(state["user_answer"]) > 50
            state["topic_feedback"] = "Good coverage"
            if self.logger:
                self.logger.log_error("json_parse_error", "Failed to parse topic_guide response", {
                    "response": response.content.strip()
                })
        
        if self.logger:
            self.logger.log_topic_evaluation(state["topic_depth_sufficient"], state["topic_feedback"])
        
        # Add to conversation history
        state["conversation_history"].append({
            "agent": "topic_guide",
            "evaluation": state["topic_feedback"],
            "depth_sufficient": state["topic_depth_sufficient"],
            "tokens": state["last_message_tokens"]
        })
        
        self.log_end(state, {
            "depth_sufficient": state["topic_depth_sufficient"],
            "feedback": state["topic_feedback"]
        })
        
        return state


# Create singleton instance
_topic_guide_instance = TopicGuideImpl()


def topic_guide(state: Dict[str, Any]) -> Dict[str, Any]:
    """Topic Guide entry point"""
    return _topic_guide_instance(state)
