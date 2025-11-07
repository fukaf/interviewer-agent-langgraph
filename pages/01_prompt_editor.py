"""
Prompt Editor - Edit agent prompts with auto-detected variables
"""
import streamlit as st
import yaml
import sys
from pathlib import Path

# Add parent directory to path to import prompt_manager
sys.path.insert(0, str(Path(__file__).parent.parent))

from management.prompt_manager import get_prompt_manager

st.set_page_config(page_title="Prompt Editor", page_icon="✏️", layout="wide")

st.title("✏️ Prompt Editor")
st.caption("Edit agent prompts - variables are auto-detected from {placeholders}")

# Initialize prompt manager
try:
    pm = get_prompt_manager()
except FileNotFoundError:
    st.error("❌ `prompts.yaml` file not found. Please create it in the project root directory.")
    st.stop()

# Sidebar - Agent selection
with st.sidebar:
    st.header("Select Agent")
    
    agent_names = pm.list_agents()
    if not agent_names:
        st.error("No agents found in prompts.yaml")
        st.stop()
    
    selected_agent = st.selectbox(
        "Choose agent to edit:",
        agent_names,
        format_func=lambda x: pm.get_agent_info(x)['name']
    )
    
    st.divider()
    
    # Validation
    with st.expander("🔍 Validation", expanded=False):
        validation = pm.validate_agent_prompt(selected_agent)
        
        if validation['is_valid']:
            st.success("✅ Prompt is valid")
        else:
            st.error("❌ Issues found:")
            for issue in validation['issues']:
                st.write(f"- {issue}")
        
        if validation['warnings']:
            st.warning("⚠️ Warnings:")
            for warning in validation['warnings']:
                st.write(f"- {warning}")
        
        st.metric("Detected Variables", validation['variable_count'])
        st.metric("Template Length", validation['template_length'])
        
        # Show variable breakdown
        if validation['mapped_variables']:
            st.caption(f"✅ Mapped: {', '.join(validation['mapped_variables'])}")
        if validation['config_variables']:
            st.caption(f"📋 In Config: {', '.join(validation['config_variables'])}")
        if validation['unmapped_variables']:
            st.caption(f"⚠️ Unmapped: {', '.join(validation['unmapped_variables'])}")
    
    st.divider()
    
    # Actions
    if st.button("💾 Save All Changes", type="primary", use_container_width=True):
        try:
            pm.save_prompts(st.session_state.get('edited_prompts', pm.prompts))
            pm.reload()  # Reload to pick up changes
            st.success("✅ Prompts saved!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error saving: {e}")
    
    if st.button("🔄 Reload from File", use_container_width=True):
        pm.reload()
        if 'edited_prompts' in st.session_state:
            del st.session_state.edited_prompts
        st.success("✅ Prompts reloaded!")
        st.rerun()
    
    if st.button("↩️ Reset to Original", use_container_width=True):
        if 'edited_prompts' in st.session_state:
            del st.session_state.edited_prompts
        st.success("✅ Reset to saved version!")
        st.rerun()

# Initialize edited prompts in session state
if 'edited_prompts' not in st.session_state:
    st.session_state.edited_prompts = pm.prompts.copy()

# Get current agent config
agent_config = st.session_state.edited_prompts.get(selected_agent, {})

# Main editor area
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader(f"{agent_config.get('name', selected_agent)}")
    st.caption(agent_config.get('description', ''))
    
    # Edit fields
    with st.expander("📝 System Message", expanded=True):
        system = st.text_area(
            "System prompt (sets agent behavior):",
            value=agent_config.get('system', ''),
            height=100,
            key=f"{selected_agent}_system"
        )
        agent_config['system'] = system
    
    with st.expander("📋 Prompt Template", expanded=True):
        st.caption("💡 Use `{variable_name}` for dynamic values - they're auto-detected!")
        template = st.text_area(
            "Main prompt template:",
            value=agent_config.get('template', ''),
            height=300,
            key=f"{selected_agent}_template",
            help="Variables in {curly_braces} will be automatically detected and used"
        )
        agent_config['template'] = template
    
    # Special fields for agents with lists
    if 'guidelines' in agent_config:
        with st.expander("📌 Guidelines (Optional)", expanded=False):
            guidelines = agent_config.get('guidelines', [])
            st.caption("Edit guidelines (one per line). Use {guidelines} in template to include them.")
            guidelines_text = st.text_area(
                "Guidelines:",
                value='\n'.join(guidelines),
                height=150,
                key=f"{selected_agent}_guidelines"
            )
            agent_config['guidelines'] = [g.strip() for g in guidelines_text.split('\n') if g.strip()]
    
    if 'fail_criteria' in agent_config:
        with st.expander("❌ Fail Criteria (Optional)", expanded=False):
            fail_criteria = agent_config.get('fail_criteria', [])
            st.caption("Edit fail criteria (one per line). Use {fail_criteria} in template.")
            fail_text = st.text_area(
                "Fail Criteria:",
                value='\n'.join(fail_criteria),
                height=100,
                key=f"{selected_agent}_fail_criteria"
            )
            agent_config['fail_criteria'] = [f.strip() for f in fail_text.split('\n') if f.strip()]
    
    # Update session state
    st.session_state.edited_prompts[selected_agent] = agent_config

with col2:
    st.subheader("🔍 Live Analysis")
    
    # Auto-detect and show variables
    st.caption("**Auto-detected variables:**")
    detected_vars = pm._extract_variables_from_template(template)
    
    if detected_vars:
        for var in sorted(detected_vars):
            # Check availability
            availability = pm.check_variable_availability(var)
            
            col_var, col_status = st.columns([2, 1])
            with col_var:
                st.code(f"{{{var}}}", language=None)
            with col_status:
                if availability['has_mapping']:
                    st.caption("✅ Auto")
                elif var in agent_config:
                    st.caption("📋 Config")
                else:
                    st.caption("⚠️ Manual")
            
            # Show mapping info on hover/expand
            if availability['has_mapping']:
                with st.expander(f"ℹ️ {var} mapping", expanded=False):
                    st.caption(f"**Auto-fills from:**")
                    for key in availability['mapping_keys']:
                        # Format state key path (avoid backslash in f-string)
                        if '.' not in key:
                            state_path = f"state['{key}']"
                        else:
                            # Convert dot notation to bracket notation
                            parts = key.split('.')
                            state_path = "state['" + "']['".join(parts) + "']"
                        st.code(state_path, language=None)
            elif not availability['has_mapping'] and var not in agent_config:
                with st.expander(f"⚠️ {var} needs attention", expanded=False):
                    st.warning(availability['suggestion'])
                    st.caption("**Options:**")
                    st.write(f"1. Add to state as `state['{var}']`")
                    st.write(f"2. Provide explicitly in code")
                    st.write(f"3. Add to variable_mappings in prompt_manager.py")
    else:
        st.info("ℹ️ No variables found. Add {variable_name} to your template.")
    
    # Validation status
    st.divider()
    validation = pm.validate_agent_prompt(selected_agent)
    
    if validation['is_valid']:
        st.success("✅ Template is valid")
    else:
        st.warning("⚠️ **Issues:**")
        for issue in validation['issues']:
            st.write(f"- {issue}")
    
    st.divider()
    
    # Test with sample data
    with st.expander("🧪 Test Preview", expanded=True):
        st.caption("Provide values to preview the final prompt")
        
        test_values = {}
        
        # Generate inputs based on detected variables
        for var in sorted(detected_vars):
            if 'question' in var.lower():
                test_values[var] = st.text_input(
                    f"{var}:",
                    value="What is your experience with our product?",
                    key=f"test_{var}"
                )
            elif 'answer' in var.lower():
                test_values[var] = st.text_area(
                    f"{var}:",
                    value="I have 3 years of experience working with it.",
                    height=60,
                    key=f"test_{var}"
                )
            elif var in ['example_questions', 'questions']:
                test_values[var] = st.text_area(
                    f"{var} (one per line):",
                    "Example question 1?\nExample question 2?",
                    height=80,
                    key=f"test_{var}"
                ).split('\n')
            elif var in ['theme', 'topic']:
                test_values[var] = st.text_input(
                    f"{var}:",
                    value=f"Sample {var.title()}",
                    key=f"test_{var}"
                )
            elif var in ['feedback', 'assessment']:
                test_values[var] = st.text_input(
                    f"{var}:",
                    value=f"Sample feedback or assessment",
                    key=f"test_{var}"
                )
            elif var == 'retry_msg':
                test_values[var] = st.text_input(
                    f"{var}:",
                    value=" (Attempt 2/3)",
                    key=f"test_{var}"
                )
            elif var in ['themes_text', 'conversation_text']:
                test_values[var] = st.text_area(
                    f"{var}:",
                    value=f"Sample {var} content",
                    height=60,
                    key=f"test_{var}"
                )
            else:
                test_values[var] = st.text_input(
                    f"{var}:",
                    value=f"Sample {var}",
                    key=f"test_{var}"
                )
        
        if st.button("🔄 Generate Preview", type="secondary"):
            try:
                # Create temporary PromptManager with edited prompts
                temp_pm = get_prompt_manager()
                temp_pm.prompts = st.session_state.edited_prompts
                
                preview = temp_pm.get_prompt(selected_agent, auto_fill=False, **test_values)
                st.success("✅ Preview generated!")
                st.code(preview, language="markdown")
            except ValueError as e:
                st.error(f"❌ {str(e)}")
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Changes indicator
if st.session_state.edited_prompts != pm.prompts:
    st.warning("⚠️ You have unsaved changes! Use the sidebar to save or reset.")

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("💡 **Tip:** Variables in `{curly_braces}` are auto-detected")
with col2:
    st.caption("🔄 Edit → Save → Test in main interview")
with col3:
    st.caption("📖 Changes are saved to `prompts.yaml`")
