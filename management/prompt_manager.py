"""
Prompt Manager - Loads and manages prompt templates with auto-fill from state
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import re


class PromptManager:
    def __init__(self, config_path: str = "prompts.yaml"):
        self.config_path = Path(config_path)
        self.prompts = self._load_prompts()
        
        # Define mapping from template variables to state keys
        # This allows flexible naming - template can use {question} and pull from state["current_question"]
        self.variable_mappings = {
            # Common mappings
            "question": ["current_question", "question"],
            "answer": ["user_answer", "answer"],
            "theme": ["current_topic.theme", "theme"],
            "topic": ["current_topic.topic", "topic"],
            "example_questions": ["current_topic.example_questions", "example_questions"],
            "prev_question": ["current_question", "previous_question"],
            "assessment": ["topic_feedback", "assessment"],
            "feedback": ["security_feedback", "feedback"],
            "retry_msg": ["judge_retry_msg", "retry_msg"],
            "themes_text": ["themes_summary", "themes_text"],
            "conversation_text": ["conversation_summary", "conversation_text"],
        }
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Prompts file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def reload(self):
        """Reload prompts from file (useful after editing)"""
        self.prompts = self._load_prompts()
    
    def _extract_variables_from_template(self, template: str) -> Set[str]:
        """Extract all {variable} placeholders from template"""
        pattern = r'\{(\w+)\}'
        variables = set(re.findall(pattern, template))
        return variables
    
    def get_template_variables(self, agent_name: str) -> List[str]:
        """Get list of variables required by this agent's template"""
        agent_config = self.prompts.get(agent_name, {})
        template = agent_config.get('template', '')
        variables = self._extract_variables_from_template(template)
        return sorted(list(variables))
    
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """Get value from nested dict/object using dot notation
        
        Examples:
            _get_nested_value(state, "current_topic.theme") 
            _get_nested_value(state, "user_answer")
        """
        keys = path.split('.')
        value = obj
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = getattr(value, key, None)
            
            if value is None:
                return None
        
        return value
    
    def _auto_fill_variable(self, var_name: str, state: Dict[str, Any], 
                           explicit_kwargs: Dict[str, Any]) -> Optional[Any]:
        """Automatically find and fill a variable from state
        
        Priority:
        1. Check explicit_kwargs (manually provided)
        2. Check variable_mappings for known aliases
        3. Try direct state key match
        4. Return None if not found
        """
        # Priority 1: Explicit kwargs
        if var_name in explicit_kwargs:
            return explicit_kwargs[var_name]
        
        # Priority 2: Check mappings
        if var_name in self.variable_mappings:
            for state_key in self.variable_mappings[var_name]:
                value = self._get_nested_value(state, state_key)
                if value is not None:
                    return value
        
        # Priority 3: Direct state key match
        if var_name in state:
            return state[var_name]
        
        # Priority 4: Try nested path
        value = self._get_nested_value(state, var_name)
        if value is not None:
            return value
        
        return None
    
    def _format_list_variable(self, value: list, var_name: str) -> str:
        """Format a list variable based on common patterns"""
        if var_name in ['example_questions', 'questions']:
            return '\n'.join([f"- {item}" for item in value])
        elif var_name in ['guidelines', 'criteria', 'rules']:
            return '\n'.join([f"{i+1}. {item}" for i, item in enumerate(value)])
        elif var_name in ['fail_criteria', 'issues']:
            return '\n'.join([f"- {item}" for item in value])
        else:
            return '\n'.join(str(item) for item in value)
    
    def _prepare_special_variables(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare special computed variables that might be needed
        
        These are variables that need to be computed from state but aren't
        directly stored (e.g., retry_msg, themes_text, conversation_text)
        """
        special_vars = {}
        
        # retry_msg for judge agent
        if "judge_retry_count" in state and "max_judge_retries" in state:
            retry_count = state["judge_retry_count"]
            max_retries = state["max_judge_retries"]
            if retry_count > 1:
                special_vars["retry_msg"] = f" (Attempt {retry_count}/{max_retries})"
            else:
                special_vars["retry_msg"] = ""
        
        # themes_text for feedback agent
        if "topics" in state:
            themes = {}
            for topic in state["topics"]:
                theme = topic.get('theme', 'General')
                if theme not in themes:
                    themes[theme] = []
                themes[theme].append(topic['topic'])
            special_vars["themes_text"] = '\n'.join([
                f"**{theme}**: {', '.join(topics)}" 
                for theme, topics in themes.items()
            ])
        
        # conversation_text for feedback agent
        if "conversation_history" in state:
            conversation_summary = []
            for entry in state["conversation_history"][:20]:  # Limit length
                if "question" in entry:
                    conversation_summary.append(f"Q: {entry['question']}")
                if "answer" in entry:
                    conversation_summary.append(f"A: {entry['answer']}")
            special_vars["conversation_text"] = '\n'.join(conversation_summary)
        
        return special_vars
    
    def get_prompt(self, agent_name: str, state: Optional[Dict[str, Any]] = None, 
                   auto_fill: bool = True, **kwargs) -> str:
        """Get formatted prompt for an agent with optional auto-fill
        
        Args:
            agent_name: Name of the agent (e.g., 'topic_agent')
            state: State dict to auto-fill variables from (optional)
            auto_fill: Whether to auto-fill missing variables from state
            **kwargs: Explicit variables to use (override auto-fill)
            
        Returns:
            Formatted prompt string
            
        Raises:
            ValueError: If required variables are missing and can't be auto-filled
        """
        agent_config = self.prompts.get(agent_name, {})
        template = agent_config.get('template', '')
        
        # Auto-detect what variables the template needs
        template_vars = self._extract_variables_from_template(template)
        
        # Prepare variables
        formatted_kwargs = kwargs.copy()
        
        # Add special computed variables if state provided
        if state and auto_fill:
            special_vars = self._prepare_special_variables(state)
            # Add special vars if not already in kwargs
            for key, value in special_vars.items():
                if key not in formatted_kwargs:
                    formatted_kwargs[key] = value
        
        # Auto-fill missing variables from state
        if state and auto_fill:
            for var_name in template_vars:
                if var_name not in formatted_kwargs:
                    value = self._auto_fill_variable(var_name, state, kwargs)
                    if value is not None:
                        formatted_kwargs[var_name] = value
        
        # Check which variables are still missing
        missing_vars = template_vars - set(formatted_kwargs.keys())
        
        if missing_vars:
            # Try to get from config (guidelines, fail_criteria, etc.)
            for var_name in list(missing_vars):
                if var_name in agent_config:
                    config_value = agent_config[var_name]
                    if isinstance(config_value, list):
                        formatted_kwargs[var_name] = self._format_list_variable(
                            config_value, var_name
                        )
                        missing_vars.remove(var_name)
                    else:
                        formatted_kwargs[var_name] = config_value
                        missing_vars.remove(var_name)
        
        # If still missing, raise error
        if missing_vars:
            available_in_state = []
            if state:
                available_in_state = list(state.keys())
            
            raise ValueError(
                f"Missing required variables for {agent_name}: {', '.join(sorted(missing_vars))}\n"
                f"Template needs: {', '.join(sorted(template_vars))}\n"
                f"Provided explicitly: {', '.join(sorted(kwargs.keys()))}\n"
                f"Available in state: {', '.join(available_in_state[:10])}..."
            )
        
        # Format lists
        final_kwargs = {}
        for key, value in formatted_kwargs.items():
            if isinstance(value, list):
                final_kwargs[key] = self._format_list_variable(value, key)
            else:
                final_kwargs[key] = value
        
        try:
            return template.format(**final_kwargs)
        except KeyError as e:
            raise ValueError(
                f"Template formatting error for {agent_name}: missing variable {e}"
            )
    
    def get_system_message(self, agent_name: str) -> str:
        """Get system message for an agent"""
        return self.prompts.get(agent_name, {}).get('system', '')
    
    def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """Get agent metadata including auto-detected variables"""
        agent_config = self.prompts.get(agent_name, {})
        template = agent_config.get('template', '')
        variables = self.get_template_variables(agent_name)
        
        return {
            'name': agent_config.get('name', agent_name),
            'description': agent_config.get('description', ''),
            'system': agent_config.get('system', ''),
            'variables': variables,
            'template': template
        }
    
    def list_agents(self) -> list[str]:
        """List all available agent names"""
        return list(self.prompts.keys())
    
    def save_prompts(self, prompts: Dict[str, Any]):
        """Save prompts back to YAML file"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(prompts, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        self.prompts = prompts
    
    def add_variable_mapping(self, template_var: str, state_keys: List[str]):
        """Add custom variable mapping
        
        Args:
            template_var: Variable name in template (e.g., "question")
            state_keys: List of state keys to try (e.g., ["current_question", "question"])
        """
        self.variable_mappings[template_var] = state_keys
    
    def check_variable_availability(self, var_name: str) -> Dict[str, Any]:
        """Check how a variable can be resolved
        
        Args:
            var_name: Variable name to check
            
        Returns:
            Dict with information about variable availability
        """
        result = {
            'variable': var_name,
            'has_mapping': var_name in self.variable_mappings,
            'mapping_keys': self.variable_mappings.get(var_name, []),
            'requires_explicit': False,
            'suggestion': ''
        }
        
        if var_name in self.variable_mappings:
            result['suggestion'] = f"Will auto-fill from: {' or '.join(self.variable_mappings[var_name])}"
        else:
            result['requires_explicit'] = True
            result['suggestion'] = f"Must exist in state['{var_name}'] or be provided explicitly"
        
        return result
    
    def validate_agent_prompt(self, agent_name: str, sample_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate an agent's prompt configuration
        
        Args:
            agent_name: Agent to validate
            sample_state: Optional sample state to test auto-fill
            
        Returns:
            Validation results with detected variables, issues, and auto-fill status
        """
        agent_config = self.prompts.get(agent_name, {})
        template = agent_config.get('template', '')
        
        detected_vars = self.get_template_variables(agent_name)
        issues = []
        warnings = []
        
        if not template:
            issues.append("Template is empty")
        
        if not agent_config.get('system'):
            warnings.append("System message is missing (recommended but optional)")
        
        # Check for unmatched braces
        open_count = template.count('{')
        close_count = template.count('}')
        if open_count != close_count:
            issues.append(f"Unmatched braces: {open_count} opening, {close_count} closing")
        
        # Check if variables have known mappings or are in config
        unmapped_vars = []
        mapped_vars = []
        config_vars = []
        
        for var in detected_vars:
            if var in agent_config:
                # Variable is defined in config (like guidelines, fail_criteria)
                config_vars.append(var)
            elif var in self.variable_mappings:
                # Variable has a known mapping to state keys
                mapped_vars.append(var)
            else:
                # Variable has no mapping - might be problematic
                unmapped_vars.append(var)
        
        if unmapped_vars:
            warnings.append(
                f"Variables without mappings: {', '.join(unmapped_vars)}. "
                f"These must exist directly in state or be provided explicitly."
            )
        
        # Test auto-fill if sample state provided
        auto_fillable = []
        not_fillable = []
        
        if sample_state:
            for var in detected_vars:
                value = self._auto_fill_variable(var, sample_state, {})
                if value is not None:
                    auto_fillable.append(var)
                else:
                    # Check if it's in config
                    if var not in agent_config:
                        not_fillable.append(var)
        
        return {
            'agent_name': agent_name,
            'template_length': len(template),
            'detected_variables': detected_vars,
            'variable_count': len(detected_vars),
            'mapped_variables': mapped_vars,  # Variables with known state mappings
            'config_variables': config_vars,  # Variables defined in agent config
            'unmapped_variables': unmapped_vars,  # Variables without mappings
            'auto_fillable': auto_fillable,  # Variables that can be filled from sample state
            'not_fillable': not_fillable,  # Variables that cannot be filled
            'issues': issues,  # Critical issues that prevent usage
            'warnings': warnings,  # Non-critical warnings
            'is_valid': len(issues) == 0
        }


# Global instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create global prompt manager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
