"""
Logging utility for Interview Agent system.
Logs all conversations, agent interactions, and LLM responses for debugging and storage.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class InterviewLogger:
    """Logger for interview conversations and agent interactions"""
    
    def __init__(self, session_id: str, log_dir: str = "logs"):
        """
        Initialize logger for a specific session.
        
        Args:
            session_id: Unique identifier for the interview session
            log_dir: Directory to store log files
        """
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create session-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"interview_{session_id}_{timestamp}.json"
        self.text_log_file = self.log_dir / f"interview_{session_id}_{timestamp}.txt"
        
        # Initialize log structure
        self.log_data = {
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_tokens": 0,
            "total_cost_estimate": 0.0,
            "llm_provider": None,
            "events": []
        }
        
        # Setup text logger
        self.text_logger = logging.getLogger(f"interview_{session_id}")
        self.text_logger.setLevel(logging.DEBUG)
        
        # File handler for text logs
        fh = logging.FileHandler(self.text_log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.text_logger.addHandler(fh)
        self.text_logger.addHandler(ch)
        
        self.text_logger.info(f"Interview session started: {session_id}")
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log an event with timestamp.
        
        Args:
            event_type: Type of event (e.g., 'agent_call', 'user_input', 'llm_response')
            data: Event data
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        self.log_data["events"].append(event)
        
        # Log to text file as well
        self.text_logger.debug(f"[{event_type}] {json.dumps(data, ensure_ascii=False)}")
    
    def log_agent_start(self, agent_name: str, state_snapshot: Dict[str, Any]):
        """Log when an agent starts processing"""
        self.log_event("agent_start", {
            "agent": agent_name,
            "state": {
                "current_topic_index": state_snapshot.get("current_topic_index"),
                "current_topic": state_snapshot.get("current_topic", {}),
                "topic_iteration_count": state_snapshot.get("topic_iteration_count"),
                "interview_complete": state_snapshot.get("interview_complete"),
                "waiting_for_user_input": state_snapshot.get("waiting_for_user_input")
            }
        })
        self.text_logger.info(f"Agent started: {agent_name}")
    
    def log_agent_end(self, agent_name: str, output: Dict[str, Any]):
        """Log when an agent completes processing"""
        self.log_event("agent_end", {
            "agent": agent_name,
            "output": output
        })
        self.text_logger.info(f"Agent completed: {agent_name}")
    
    def log_llm_request(self, agent_name: str, prompt: str, model: str):
        """Log LLM request"""
        self.log_event("llm_request", {
            "agent": agent_name,
            "model": model,
            "prompt": prompt,
            "prompt_length": len(prompt)
        })
        self.text_logger.debug(f"LLM Request from {agent_name} (model: {model}, length: {len(prompt)})")
    
    def log_llm_response(self, agent_name: str, response: str, tokens: int, metadata: Optional[Dict] = None):
        """Log LLM response"""
        self.log_event("llm_response", {
            "agent": agent_name,
            "response": response,
            "response_length": len(response),
            "tokens": tokens,
            "metadata": metadata or {}
        })
        
        # Update total tokens
        self.log_data["total_tokens"] += tokens
        
        self.text_logger.debug(f"LLM Response to {agent_name} (tokens: {tokens}, length: {len(response)})")
    
    def log_user_input(self, question: str, answer: str):
        """Log user's answer to a question"""
        self.log_event("user_input", {
            "question": question,
            "answer": answer,
            "answer_length": len(answer)
        })
        self.text_logger.info(f"User answered (length: {len(answer)})")
    
    def log_security_check(self, passed: bool, feedback: str):
        """Log security agent validation result"""
        self.log_event("security_check", {
            "passed": passed,
            "feedback": feedback
        })
        self.text_logger.info(f"Security check: {'PASSED' if passed else 'FAILED'} - {feedback}")
    
    def log_topic_evaluation(self, depth_sufficient: bool, feedback: str):
        """Log topic guide evaluation"""
        self.log_event("topic_evaluation", {
            "depth_sufficient": depth_sufficient,
            "feedback": feedback
        })
        self.text_logger.info(f"Topic evaluation: {'Sufficient' if depth_sufficient else 'Needs more depth'}")
    
    def log_routing_decision(self, from_agent: str, to_agent: str, reason: str):
        """Log routing decision between agents"""
        self.log_event("routing", {
            "from": from_agent,
            "to": to_agent,
            "reason": reason
        })
        self.text_logger.info(f"Routing: {from_agent} -> {to_agent} ({reason})")
    
    def log_error(self, error_type: str, error_message: str, context: Optional[Dict] = None):
        """Log an error"""
        self.log_event("error", {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        })
        self.text_logger.error(f"Error ({error_type}): {error_message}")
    
    def log_interview_complete(self, total_topics: int, total_questions: int):
        """Log interview completion"""
        self.log_data["end_time"] = datetime.now().isoformat()
        self.log_event("interview_complete", {
            "total_topics": total_topics,
            "total_questions": total_questions,
            "total_tokens": self.log_data["total_tokens"]
        })
        self.text_logger.info(f"Interview completed: {total_topics} topics, {total_questions} questions, {self.log_data['total_tokens']} tokens")
    
    def set_llm_provider(self, provider: str):
        """Set the LLM provider being used"""
        self.log_data["llm_provider"] = provider
        self.text_logger.info(f"LLM Provider: {provider}")
    
    def save(self):
        """Save the complete log to JSON file"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.log_data, f, indent=2, ensure_ascii=False)
            self.text_logger.info(f"Log saved to: {self.log_file}")
        except Exception as e:
            self.text_logger.error(f"Failed to save log: {e}")
    
    def get_conversation_history(self) -> list:
        """Extract just the conversation (questions and answers) from logs"""
        conversation = []
        for event in self.log_data["events"]:
            if event["event_type"] == "user_input":
                conversation.append({
                    "timestamp": event["timestamp"],
                    "question": event["data"]["question"],
                    "answer": event["data"]["answer"]
                })
        return conversation
    
    def export_conversation_text(self, output_file: Optional[str] = None) -> str:
        """Export conversation as readable text"""
        if output_file is None:
            output_file = self.log_dir / f"conversation_{self.session_id}.txt"
        
        conversation = self.get_conversation_history()
        lines = [
            f"Interview Session: {self.session_id}",
            f"Date: {self.log_data['start_time']}",
            f"Provider: {self.log_data['llm_provider']}",
            f"Total Tokens: {self.log_data['total_tokens']}",
            "=" * 80,
            ""
        ]
        
        for i, entry in enumerate(conversation, 1):
            lines.append(f"Q{i}: {entry['question']}")
            lines.append(f"A{i}: {entry['answer']}")
            lines.append("")
        
        text_content = "\n".join(lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        self.text_logger.info(f"Conversation exported to: {output_file}")
        return text_content


# Global logger instance (set when session starts)
_current_logger: Optional[InterviewLogger] = None


def get_logger() -> Optional[InterviewLogger]:
    """Get the current session logger"""
    return _current_logger


def set_logger(logger: InterviewLogger):
    """Set the current session logger"""
    global _current_logger
    _current_logger = logger


def clear_logger():
    """Clear the current session logger"""
    global _current_logger
    if _current_logger:
        _current_logger.save()
    _current_logger = None
