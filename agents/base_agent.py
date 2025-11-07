"""
Base agent with common functionality
"""
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from management.prompt_manager import get_prompt_manager
from interview_logging.interview_logger import get_logger


class BaseAgent:
    """Base class for all agents with common functionality"""
    
    def __init__(self, agent_name: str, display_name: str):
        self.agent_name = agent_name
        self.display_name = display_name
        self.pm = get_prompt_manager()
        # Don't store logger at init - get it dynamically each time
    
    @property
    def logger(self):
        """Get logger dynamically to handle late initialization"""
        return get_logger()
    
    def invoke_llm(self, model: BaseChatModel, state: Dict[str, Any], **extra_vars) -> Any:
        """Invoke LLM with system message and prompt from prompt manager
        
        Args:
            model: LLM model to use
            state: Current state dict
            **extra_vars: Additional variables to override/add
            
        Returns:
            LLM response
        """
        # Get system message from prompt manager
        system_message = self.pm.get_system_message(self.agent_name)
        
        # Get prompt with auto-fill from state
        prompt = self.pm.get_prompt(self.agent_name, state=state, **extra_vars)
        
        # Build messages list
        messages = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.append(HumanMessage(content=prompt))
        
        # Log request
        if self.logger:
            full_prompt = f"System: {system_message}\n\nHuman: {prompt}" if system_message else prompt
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
