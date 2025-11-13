"""
Base agent with common functionality for System + Human message structure
"""
from typing import Any, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from management.prompt_manager import get_prompt_manager
from interview_logging.interview_logger import get_logger


class BaseAgent:
    """Base class for all agents with common functionality"""
    
    def __init__(self, agent_name: str, display_name: str):
        self.agent_name = agent_name
        self.display_name = display_name
        # self.pm = get_prompt_manager()
        # Don't store logger at init - get it dynamically each time
    
    @property
    def logger(self):
        """Get logger dynamically to handle late initialization"""
        return get_logger()
    
    @property
    def pm(self):
        """Get prompt manager dynamically to handle late initialization"""
        return get_prompt_manager()
    
    def get_messages(self, state: Dict[str, Any], **extra_vars) -> list:
        """Get System and Human messages from prompt manager
        
        Returns:
            List of [SystemMessage, HumanMessage]
        """
        return self.pm.get_messages(self.agent_name, state=state, **extra_vars)

    def invoke_llm(self, model: BaseChatModel, state: Dict[str, Any], **extra_vars) -> Any:
        """Invoke LLM with System and Human messages
        
        Args:
            model: LLM model to use
            state: Current state dict
            **extra_vars: Additional variables to override/add
            
        Returns:
            LLM response
        """
        # Get messages (System + Human)
        messages = self.get_messages(state, **extra_vars)
        
        # Log request
        if self.logger:
            # Combine messages for logging
            log_parts = []
            for msg in messages:
                msg_type = msg.__class__.__name__.replace('Message', '')
                log_parts.append(f"{msg_type}: {msg.content}")
            full_prompt = '\n\n'.join(log_parts)
            self.logger.log_llm_request(self.agent_name, full_prompt, str(model))
        
        # Invoke LLM
        response = model.invoke(messages)
        
        # Log response
        if self.logger:
            self.logger.log_llm_response(
                self.agent_name,
                response.content.strip(),
                self._get_token_count(response),
                response.response_metadata if hasattr(response, 'response_metadata') else None
            )
        
        return response
    
    def _get_token_count(self, response: Any) -> int:
        """Extract token count from response"""
        tokens = 0
        
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            
            # Try OpenAI/Azure format
            usage = metadata.get('token_usage', {})
            tokens = usage.get('total_tokens', 0)
            
            # Try Gemini format
            if tokens == 0 and 'usage_metadata' in metadata:
                usage_meta = metadata['usage_metadata']
                prompt_tokens = usage_meta.get('prompt_token_count', 0)
                completion_tokens = usage_meta.get('candidates_token_count', 0)
                tokens = prompt_tokens + completion_tokens
            
            # Fallback: estimate from content
            if tokens == 0 and hasattr(response, 'content'):
                tokens = len(response.content) // 4
        
        return tokens
    
    def track_tokens(self, state: Dict[str, Any], response: Any) -> Dict[str, Any]:
        """Track token usage"""
        tokens = self._get_token_count(response)
        state["last_message_tokens"] = tokens
        state["total_tokens"] = state.get("total_tokens", 0) + tokens
        return state
    
    def log_start(self, state: Dict[str, Any]):
        """Log agent start"""
        if self.logger:
            self.logger.log_agent_start(self.agent_name, state)
    
    def log_end(self, state: Dict[str, Any], extra_info: Dict[str, Any] = None):
        """Log agent end"""
        if self.logger:
            self.logger.log_agent_end(self.agent_name, extra_info or {})
