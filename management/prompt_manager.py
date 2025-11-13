"""
Prompt Manager - Loads and manages prompt templates with auto-fill from state
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import re
from langchain_core.messages import HumanMessage, SystemMessage


class PromptManager:
    def __init__(self, config_path: str = "prompts.yaml"):
        self.config_path = Path(config_path)
        self.prompts = self._load_prompts()
        self.memo = self.prompts.pop('memo', '')  # Extract memo if exists
        
        # Define mapping from template variables to state keys
        # This allows flexible naming - template can use {question} and pull from state["current_question"]
        self.variable_mappings = {
            # Common mappings
            "question": ["current_question", "question"],
            "answer": ["user_answer", "answer"],
            "theme": ["current_topic.theme", "theme"],
            "topic": ["current_topic.topic", "topic"],
            "example_questions": ["current_topic.example_questions", "example_questions"],
            "assessment": ["topic_feedback", "assessment"],
            "feedback": ["security_feedback", "feedback"],
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
        self.memo = self.prompts.pop('memo', '')
    
    def load_from_file(self, config_path: str):
        """Load prompts from a different file
        
        Args:
            config_path: Path to the new prompts file
        """
        self.config_path = Path(config_path)
        self.reload()
    
    def get_memo(self) -> str:
        """Get the memo/description for this prompt configuration"""
        return self.memo
    
    @staticmethod
    def list_available_prompts(prompts_dir: str = "prompts") -> list[dict]:
        """List all available prompt files in the prompts directory
        
        Args:
            prompts_dir: Directory containing prompt files
            
        Returns:
            List of dicts with 'path', 'name', and 'memo' for each prompt file
        """
        prompts_path = Path(prompts_dir)
        if not prompts_path.exists():
            return []
        
        prompt_files = []
        for yaml_file in prompts_path.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    memo = data.get('memo', 'No description available')
                    
                prompt_files.append({
                    'path': str(yaml_file),
                    'name': yaml_file.stem,
                    'memo': memo,
                    'file': yaml_file.name
                })
            except Exception as e:
                # Skip files that can't be read
                prompt_files.append({
                    'path': str(yaml_file),
                    'name': yaml_file.stem,
                    'memo': f'Error reading file: {str(e)}',
                    'file': yaml_file.name
                })
        
        return sorted(prompt_files, key=lambda x: x['name'])
    
    def _extract_variables_from_template(self, template: str) -> Set[str]:
        """Extract all {variable} placeholders from template"""
        pattern = r'\{(\w+)\}'
        variables = set(re.findall(pattern, template))
        return variables
    
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
    
    def _build_agent_messages(self, agent_config: Dict[str, Any], state: Optional[Dict[str, Any]] = None, **kwargs) -> List[Any]:
        """Build System and Human messages for the agent
        
        System Message contains:
        - Role (who you are)
        - Task (what to do)
        - Guidelines (how to do it)
        - Additional Guidelines (constraints)
        - Response Format (output format)
        
        Human Message contains:
        - Input (dynamic context with variables filled)
        
        Args:
            agent_config: Agent configuration from prompts
            state: Current state for variable filling
            **kwargs: Additional variables to override
            
        Returns:
            List of [SystemMessage, HumanMessage]
        """
        # -----------------------------------------------------------
        # 1. BUILD SYSTEM MESSAGE (Fixed Instructions & Constraints)
        # -----------------------------------------------------------
        system_sections = []

        # 1.1. Role (Mandatory for System)
        if 'role' in agent_config:
            system_sections.append(f"\n# YOUR ROLE\n{agent_config['role']}\n")

        # 1.2. Task (Fixed instruction)
        if 'task' in agent_config:
            system_sections.append(f"# TASK\n{agent_config['task']}\n")

        # 1.3. Guidelines
        if 'guidelines' in agent_config:
            guidelines = agent_config['guidelines']
            guidelines_text = '\n'.join(f"- {g}" for g in (guidelines if isinstance(guidelines, list) else [guidelines]))
            system_sections.append(f"# GUIDELINES\n{guidelines_text}\n")

        # 1.4. Additional Guidelines
        if 'additional_guidelines' in agent_config:
            add_guidelines = agent_config['additional_guidelines']
            add_guidelines_text = '\n'.join(f"- {g}" for g in (add_guidelines if isinstance(add_guidelines, list) else [add_guidelines]))
            system_sections.append(f"# ADDITIONAL GUIDELINES\n{add_guidelines_text}\n")
        
        # 1.5. Response Format (CRITICAL for System Message)
        if 'response_format' in agent_config:
            system_sections.append(f"# RESPONSE FORMAT\n{agent_config['response_format']}")
            
        system_prompt_content = '\n'.join(system_sections)
        system_message = SystemMessage(content=system_prompt_content)
        
        # -----------------------------------------------------------
        # 2. BUILD HUMAN MESSAGE (Dynamic Data & Context)
        # -----------------------------------------------------------
        human_sections = []
        
        # 2.1. Input (Dynamic context)
        if 'input' in agent_config:
            input_items = agent_config['input']
            input_text = '\n'.join(input_items) if isinstance(input_items, list) else input_items
            
            # Fill variables in input
            input_text = self._fill_variables_in_text(input_text, state, **kwargs)
            
            human_sections.append(f"\n# INPUT CONTEXT\n{input_text}")
            
        human_prompt_content = '\n'.join(human_sections)
        human_message = HumanMessage(content=human_prompt_content)

        # -----------------------------------------------------------
        # 3. RETURN MESSAGES IN ORDER
        # -----------------------------------------------------------
        return [system_message, human_message]
    
    def _fill_variables_in_text(self, text: str, state: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """Fill {variables} in text with values from state"""
        if not state:
            return text
        
        # Extract variables
        variables = self._extract_variables_from_template(text)
        
        # Prepare kwargs for formatting
        formatted_kwargs = kwargs.copy()
        
        # Add special variables
        special_vars = self._prepare_special_variables(state)
        for key, value in special_vars.items():
            if key not in formatted_kwargs:
                formatted_kwargs[key] = value
        
        # Auto-fill from state
        for var_name in variables:
            if var_name not in formatted_kwargs:
                value = self._auto_fill_variable(var_name, state, kwargs)
                if value is not None:
                    formatted_kwargs[var_name] = value
        
        # Format lists
        final_kwargs = {}
        for key, value in formatted_kwargs.items():
            if isinstance(value, list):
                final_kwargs[key] = self._format_list_variable(value, key)
            else:
                final_kwargs[key] = value
        
        try:
            return text.format(**final_kwargs)
        except KeyError:
            # Return as-is if formatting fails
            return text
    
    def get_messages(self, agent_name: str, state: Optional[Dict[str, Any]] = None, **kwargs) -> List[Any]:
        """Get System and Human messages for an agent
        
        Args:
            agent_name: Name of the agent (e.g., 'topic_agent')
            state: State dict to auto-fill variables from (optional)
            **kwargs: Explicit variables to use (override auto-fill)
            
        Returns:
            List of [SystemMessage, HumanMessage]
        """
        agent_config = self.prompts.get(agent_name, {})
        return self._build_agent_messages(agent_config, state, **kwargs)
    
    def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """Get agent metadata including components"""
        agent_config = self.prompts.get(agent_name, {})
        
        # Extract variables from input section
        input_text = ''
        input_items = agent_config.get('input', [])
        if isinstance(input_items, list):
            input_text = '\n'.join(input_items)
        else:
            input_text = str(input_items)
        
        variables = self._extract_variables_from_template(input_text)
        
        return {
            'name': agent_config.get('name', agent_name),
            'description': agent_config.get('description', ''),
            'role': agent_config.get('role', ''),
            'task': agent_config.get('task', ''),
            'variables': sorted(list(variables)),
            'has_guidelines': bool(agent_config.get('guidelines')),
            'has_additional_guidelines': bool(agent_config.get('additional_guidelines')),
            'has_response_format': bool(agent_config.get('response_format'))
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
    
    def validate_agent_output_schema(self, agent_name: str) -> Dict[str, Any]:
        """Validate that agent's output schema matches what the graph expects (unified structure)
        
        Args:
            agent_name: Agent to validate
            
        Returns:
            Validation results for output schema
        """
        agent_config = self.prompts.get(agent_name, {})
        output_schema = agent_config.get('output_schema', {})
        
        issues = []
        warnings = []
        
        if not output_schema:
            return {
                'is_valid': True,
                'has_schema': False,
                'warnings': ["No output_schema defined (optional but recommended)"]
            }
        
        # Get response_format from unified structure
        response_format = agent_config.get('response_format', '')
        
        # Check output type
        output_type = output_schema.get('type', 'unknown')
        valid_types = ['json', 'plain_text', 'markdown']
        
        if output_type not in valid_types:
            issues.append(f"Invalid output type '{output_type}'. Must be one of: {', '.join(valid_types)}")
        
        # Check required fields for JSON output
        if output_type == 'json':
            required_fields = output_schema.get('required_fields', [])
            
            if not required_fields:
                warnings.append("Output type is 'json' but no required_fields defined")
            
            # Check if response_format mentions JSON
            if 'json' not in response_format.lower() and 'JSON' not in response_format:
                warnings.append("Output type is 'json' but response_format doesn't mention JSON format")
            
            # Check if each required field is mentioned in response_format
            for field in required_fields:
                field_name = field.get('name', '')
                if field_name:
                    # Check if field name appears in response_format (case-sensitive for field names in JSON)
                    # Look for the field name in quotes or braces context
                    if f'"{field_name}"' not in response_format and f"'{field_name}'" not in response_format and f'{{{field_name}' not in response_format:
                        warnings.append(f"Required field '{field_name}' not found in response_format (found in schema but not in format instructions)")
            
            # Check if format example is provided
            if not output_schema.get('format'):
                warnings.append("No format example provided in output_schema (recommended for JSON)")
        
        # Check state updates
        state_updates = output_schema.get('state_updates', [])
        required_fields = output_schema.get('required_fields', [])
        
        # For JSON, state_updates should match required_fields
        if output_type == 'json' and required_fields:
            field_state_keys = {f.get('state_key') for f in required_fields if f.get('state_key')}
            update_state_keys = {u.get('state_key') for u in state_updates if u.get('state_key')}
            
            if field_state_keys and update_state_keys and field_state_keys != update_state_keys:
                warnings.append("Mismatch between required_fields and state_updates")
        
        # Check routing dependencies
        routing_deps = output_schema.get('routing_dependencies', [])
        
        if routing_deps:
            for dep in routing_deps:
                state_key = dep.get('state_key')
                if not state_key:
                    issues.append("Routing dependency missing 'state_key'")
                    continue
                
                # Check if this state_key is produced by this agent
                if output_type == 'json':
                    field_produces_key = any(
                        f.get('state_key') == state_key 
                        for f in required_fields
                    )
                    if not field_produces_key:
                        warnings.append(
                            f"Routing depends on '{state_key}' but no required_field produces it"
                        )
        
        return {
            'is_valid': len(issues) == 0,
            'has_schema': True,
            'output_type': output_type,
            'issues': issues,
            'warnings': warnings,
            'required_fields': [f.get('name') for f in required_fields if f.get('name')],
            'state_updates': [u.get('state_key') for u in state_updates if u.get('state_key')],
            'routing_dependencies': routing_deps,
            'format_example': output_schema.get('format', '')
        }
    
    def validate_agent_prompt(self, agent_name: str, sample_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate an agent's prompt configuration (unified structure)
        
        Args:
            agent_name: Agent to validate
            sample_state: Optional sample state to test auto-fill
            
        Returns:
            Validation results with detected variables, issues, and auto-fill status
        """
        agent_config = self.prompts.get(agent_name, {})
        issues = []
        warnings = []
        
        # Check required components for unified structure
        required_components = ['role', 'input', 'task', 'response_format']
        missing_components = [c for c in required_components if c not in agent_config]
        
        if missing_components:
            issues.append(f"Missing required components: {', '.join(missing_components)}")
        
        # Extract variables from input section only
        input_text = ''
        input_items = agent_config.get('input', [])
        if isinstance(input_items, list):
            input_text = '\n'.join(input_items)
        else:
            input_text = str(input_items)
        
        detected_vars = self._extract_variables_from_template(input_text)
        
        # Check for unmatched braces in input
        open_count = input_text.count('{')
        close_count = input_text.count('}')
        if open_count != close_count:
            issues.append(f"Unmatched braces in input: {open_count} opening, {close_count} closing")
        
        # Check if variables have known mappings
        unmapped_vars = []
        mapped_vars = []
        
        for var in detected_vars:
            if var in self.variable_mappings:
                mapped_vars.append(var)
            else:
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
                    not_fillable.append(var)
        
        # Validate output schema
        output_validation = self.validate_agent_output_schema(agent_name)
        
        # Check component lengths
        if len(agent_config.get('role', '')) < 10:
            warnings.append("Role description is very short (< 10 characters)")
        
        if not agent_config.get('guidelines'):
            warnings.append("No guidelines provided (recommended)")
        
        return {
            'agent_name': agent_name,
            'detected_variables': detected_vars,
            'variable_count': len(detected_vars),
            'mapped_variables': mapped_vars,
            'unmapped_variables': unmapped_vars,
            'auto_fillable': auto_fillable,
            'not_fillable': not_fillable,
            'issues': issues,
            'warnings': warnings,
            'is_valid': len(issues) == 0 and output_validation['is_valid'],
            'output_schema': output_validation,
            'components': {
                'role': bool(agent_config.get('role')),
                'input': bool(agent_config.get('input')),
                'task': bool(agent_config.get('task')),
                'guidelines': bool(agent_config.get('guidelines')),
                'additional_guidelines': bool(agent_config.get('additional_guidelines')),
                'response_format': bool(agent_config.get('response_format'))
            }
        }


# Global instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create global prompt manager instance"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
