"""
Graph-based Prompt Editor - Click nodes to edit their prompts
"""
import streamlit as st
import streamlit.components.v2 as components_v2
import yaml
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import create_interview_graph
from management.prompt_manager import PromptManager, get_prompt_manager

st.set_page_config(page_title="Graph Prompt Editor", page_icon="🎯", layout="wide")

st.title("🎯 Graph-based Prompt Editor")
st.markdown("Click on a node in the graph to edit its prompt configuration")

# Sidebar for prompt file selection
with st.sidebar:
    st.header("📝 Prompt File Selection")
    
    pm = get_prompt_manager()
    available_prompts = PromptManager.list_available_prompts()
    
    if available_prompts:
        # Get current file
        current_file = str(pm.config_path)
        current_filename = Path(current_file).name
        
        # Create file options
        prompt_options = {p['file']: p for p in available_prompts}
        prompt_files = list(prompt_options.keys())
        
        # Get current index
        try:
            current_index = prompt_files.index(current_filename)
        except ValueError:
            current_index = 0
        
        # Initialize session state for current file tracking
        if 'last_loaded_file' not in st.session_state:
            st.session_state.last_loaded_file = current_filename
        
        # File selector with on_change callback
        def on_file_change():
            selected = st.session_state.prompt_file_selector
            if selected != st.session_state.last_loaded_file:
                selected_info = prompt_options[selected]
                try:
                    pm.load_from_file(selected_info['path'])
                    # Update session state
                    st.session_state.last_loaded_file = selected
                    st.session_state.current_file_name = Path(selected_info['path']).stem
                    st.session_state.current_memo = pm.get_memo()
                    # Clear agent selection
                    st.session_state.clicked_node = None
                    st.session_state.editing_agent = None
                    st.session_state.file_name_input = st.session_state.current_file_name
                    st.session_state.config_memo = st.session_state.current_memo
                except Exception as e:
                    st.error(f"❌ Failed to load: {str(e)}")
        
        selected_file = st.selectbox(
            "Select prompt file to edit",
            options=prompt_files,
            index=current_index,
            key="prompt_file_selector",
            on_change=on_file_change
        )
        
        # Show success message if file just changed
        if selected_file != st.session_state.last_loaded_file:
            st.success(f"✅ Loaded **{selected_file}**")
        
        # Show current file info
        selected_info = prompt_options[selected_file]
        
        # Display memo in sidebar (read-only preview)
        if selected_info['memo']:
            st.markdown("**📌 File Description:**")
            st.caption(selected_info['memo'])
        
        # Reload button
        if st.button("� Reload Current File", use_container_width=True, 
                     help="Reload the currently selected file from disk"):
            try:
                pm.load_from_file(selected_info['path'])
                st.session_state.last_loaded_file = selected_file
                st.session_state.current_file_name = Path(selected_info['path']).stem
                st.session_state.current_memo = pm.get_memo()
                st.session_state.clicked_node = None
                st.session_state.editing_agent = None
                st.session_state.file_name_input = st.session_state.current_file_name
                st.session_state.config_memo = st.session_state.current_memo
                st.success(f"✅ Reloaded **{selected_file}** from disk")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to reload: {str(e)}")
    else:
        st.warning("⚠️ No YAML files found in prompts/ folder")
        st.stop()
    
    st.divider()
    
    # Memo and file name editor in sidebar
    st.subheader("📝 File Configuration")
    
    # Current file path info
    current_path = Path(pm.config_path)
    st.caption(f"📄 Editing: `{pm.config_path}`")
    
    # Initialize session state for editable fields
    if 'current_file_name' not in st.session_state:
        st.session_state.current_file_name = current_path.stem
    if 'current_memo' not in st.session_state:
        st.session_state.current_memo = pm.get_memo()
    
    # File name editor (using session state)
    new_name = st.text_input(
        "File name (without .yaml)",
        value=st.session_state.current_file_name,
        key="file_name_input",
        help="Change the file name. Creates a copy with the new name.",
        on_change=on_file_change
    )
    
    # Memo editor (using session state)
    memo_text = st.text_area(
        "Description / Memo",
        value=st.session_state.current_memo,
        height=100,
        key="config_memo",
        help="Describe the purpose of this prompt configuration",
        on_change=on_file_change
    )
    
    # Save buttons
    col_save_memo, col_rename = st.columns(2)
    
    with col_save_memo:
        if st.button("💾 Save Memo", use_container_width=True, help="Save description to current file"):
            pm.prompts['memo'] = memo_text
            pm.memo = memo_text
            pm.save_prompts(pm.prompts)
            st.session_state.current_memo = memo_text
            st.success("✅ Memo saved!")
    
    with col_rename:
        # Show rename button only if name changed
        if new_name != current_path.stem and new_name.strip():
            if st.button("📝 Rename/Copy", use_container_width=True, type="primary"):
                try:
                    # Create new file path
                    new_file_path = current_path.parent / f"{new_name}.yaml"
                    
                    # Check if file already exists
                    if new_file_path.exists():
                        st.error(f"❌ File `{new_name}.yaml` already exists!")
                    else:
                        # Copy the file with current memo
                        import shutil
                        shutil.copy(str(current_path), str(new_file_path))
                        
                        # Load the new file and update memo if it was changed
                        pm.load_from_file(str(new_file_path))
                        if memo_text != pm.get_memo():
                            pm.prompts['memo'] = memo_text
                            pm.memo = memo_text
                            pm.save_prompts(pm.prompts)
                        
                        # Update session state
                        st.session_state.last_loaded_file = f"{new_name}.yaml"
                        st.session_state.current_file_name = new_name
                        st.session_state.current_memo = memo_text
                        
                        st.success(f"✅ Created copy as `{new_name}.yaml`")
                        st.info("💡 Original file unchanged. Now editing the new copy with current memo.")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to rename: {str(e)}")
        else:
            st.button("📝 Rename/Copy", use_container_width=True, disabled=True, help="Enter a different name to enable")

# Initialize
@st.cache_resource
def get_graph():
    return create_interview_graph()

graph = get_graph()

# Map node names to agent names in prompts.yaml
NODE_TO_AGENT_MAP = {
    "topic_agent": "topic_agent",
    "security_agent": "security_agent",
    "judge": "judge_agent",
    "topic_guide": "topic_guide",
    "probing_agent": "probing_agent",
    "feedback_agent": "feedback_agent"
}

# Initialize session state
if 'clicked_node' not in st.session_state:
    st.session_state.clicked_node = None
if 'editing_agent' not in st.session_state:
    st.session_state.editing_agent = None

# Layout: Graph on left, Editor on right
col_graph, col_editor = st.columns([1, 1])

with col_graph:
    st.subheader("🕸️ Agent Graph")
    st.caption("Click on an agent node to edit its prompt")
    
    # Get all node names
    all_node_names = ["__start__", "__end__"] + list(graph.nodes.keys())
    
    # Build Mermaid diagram
    from pyvis.network import Network
    import os
    
    # Create pyvis network
    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#000000", directed=True)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=200, spring_strength=0.001)
    
    # Get graph structure
    graph_structure = graph.get_graph()
    
    # Define node colors and shapes
    node_styles = {
        "__start__": {"color": "#CACACA", "shape": "box", "label": "START"},
        "__end__": {"color": "#CACACA", "shape": "box", "label": "END"},
        "topic_agent": {"color": "#87CEEB", "shape": "ellipse", "label": "🎯 Topic Agent"},
        "security_agent": {"color": "#DDA0DD", "shape": "ellipse", "label": "🔒 Security Agent"},
        "judge": {"color": "#F0E68C", "shape": "ellipse", "label": "⚖️ Judge Agent"},
        "topic_guide": {"color": "#98FB98", "shape": "ellipse", "label": "📊 Topic Guide"},
        "probing_agent": {"color": "#FFB6C1", "shape": "ellipse", "label": "🔍 Probing Agent"},
        "next_topic": {"color": "#B0E0E6", "shape": "box", "label": "➡️ Next Topic"},
        "human_input_node": {"color": "#FFD700", "shape": "star", "label": "👤 HITL", "size": 30},
        "feedback_agent": {"color": "#FFA07A", "shape": "ellipse", "label": "📝 Feedback Agent"}
    }
    
    # Add nodes
    all_nodes = set(graph.nodes.keys())
    all_nodes.add("__start__")
    all_nodes.add("__end__")
    
    for node in all_nodes:
        style = node_styles.get(node, {"color": "#CCCCCC", "shape": "ellipse", "label": node})
        # Highlight if editable
        if node in NODE_TO_AGENT_MAP:
            style["color"] = style["color"] if st.session_state.clicked_node != node else "#FF6B6BD8"
            font_color = "#000000" if st.session_state.clicked_node != node else "#FFFFFF"
            style["borderWidth"] = 3 if node in NODE_TO_AGENT_MAP else 1
        
        net.add_node(
            node, 
            label=style["label"],
            color=style["color"],
            shape=style["shape"],
            size=style.get("size", 25),
            title=f"Click to edit {style['label']}" if node in NODE_TO_AGENT_MAP else style["label"],
            borderWidth=style.get("borderWidth", 1)
        )
    
    # Add edges
    edges_added = set()
    if hasattr(graph_structure, 'edges'):
        for edge in graph_structure.edges:
            if isinstance(edge, tuple) and len(edge) >= 2:
                source, target = edge[0], edge[1]
            elif hasattr(edge, 'source') and hasattr(edge, 'target'):
                source, target = edge.source, edge.target
            else:
                continue
            
            if source and target:
                edge_key = (source, target)
                if edge_key not in edges_added:
                    net.add_edge(source, target, arrows="to")
                    edges_added.add(edge_key)
    
    # Configure
    net.set_options("""
    {
        "edges": {
            "smooth": {
            "type": "continuous",
            "forceDirection": "none"
            }
        },
        "physics": {
            "enabled": false,
            "avoidOverlap": 1
        },
        "interaction": {
            "hover": true,
            "navigationButtons": true
        },
        "layout": {
            "randomSeed": 42,
            "improvedLayout": true
        }
    }
    """)
    
    # Generate HTML
    base_html = net.generate_html()
    
    # Create v2 component for clickability
    HTML = '<iframe src="about:blank" id="pyvis-frame" style="width:100%; height:600px; border:1px solid #ddd;"></iframe>'
    
    escaped_html = base_html.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
    
    JS = f"""
    export default function(component) {{
        const {{ setTriggerValue, parentElement }} = component;
        const iframe = parentElement.querySelector('#pyvis-frame');
        
        const html = `{escaped_html}`;
        
        iframe.onload = function() {{
            const doc = iframe.contentDocument || iframe.contentWindow.document;
            doc.open();
            doc.write(html);
            doc.close();
            
            setTimeout(() => {{
                const networkObj = iframe.contentWindow.network;
                if (networkObj) {{
                    networkObj.on('click', function(params) {{
                        if (params.nodes.length > 0) {{
                            setTriggerValue('node_clicked', params.nodes[0]);
                        }}
                    }});
                }}
            }}, 1000);
        }};
        
        iframe.src = 'about:blank';
    }}
    """
    
    CSS = ""
    
    try:
        network_component = components_v2.component(
            "graph_editor_network",
            html=HTML,
            css=CSS,
            js=JS,
        )
        
        result = network_component(on_node_clicked_change=lambda: None)
        
        # Handle node click
        if result and result.get('node_clicked'):
            clicked_node = result['node_clicked']
            st.session_state.clicked_node = clicked_node
            
            # Check if this node has an editable agent
            if clicked_node in NODE_TO_AGENT_MAP:
                st.session_state.editing_agent = NODE_TO_AGENT_MAP[clicked_node]
                st.rerun()
            else:
                st.session_state.editing_agent = None
                
    except Exception as e:
        st.error(f"Error rendering graph: {e}")

with col_editor:
    st.subheader("✏️ Prompt Editor")
    
    # Check if an editable agent is selected
    if st.session_state.editing_agent:
        agent_name = st.session_state.editing_agent
        
        st.info(f"📝 Editing: **{agent_name}** (node: {st.session_state.clicked_node})")
        
        # Show all available state variables
        if pm.variable_mappings:
            state_vars = sorted(pm.variable_mappings.keys())
            st.caption(f"💡 Available variables: {', '.join([f'`{{{v}}}`' for v in state_vars])}")
        
        # Get agent info
        agent_config = pm.prompts.get(agent_name, {})
        
        # Editor tabs
        editor_tab1, editor_tab2, editor_tab3 = st.tabs(["✏️ Edit", "🔍 Validate", "👁️ Preview"])
        
        with editor_tab1:
            # === Unified Structure Editing ===
            st.info("📋 Editing agent with **unified prompt structure**")
            
            # 1. Role
            st.markdown("**1️⃣ Role** (Who you are)")
            role = st.text_area(
                "Define the agent's persona and expertise",
                value=agent_config.get('role', ''),
                height=80,
                key=f"role_{agent_name}",
                help="The agent's role or persona"
            )
            
            # 2. Input
            st.markdown("**2️⃣ Input** (Context/Information)")
            input_items = agent_config.get('input', [])
            if isinstance(input_items, list):
                input_text = '\n'.join(input_items)
            else:
                input_text = input_items
            
            input_value = st.text_area(
                "Information provided to the agent (one per line for lists)",
                value=input_text,
                height=100,
                key=f"input_{agent_name}",
                help="Context and input data. Use {variables} for dynamic content"
            )
            
            # 3. Task
            st.markdown("**3️⃣ Task** (What to do)")
            task = st.text_area(
                "Clear objective and what the agent needs to accomplish",
                value=agent_config.get('task', ''),
                height=100,
                key=f"task_{agent_name}",
                help="The main task or objective"
            )
            
            # 4. Guidelines
            st.markdown("**4️⃣ Guidelines** (How to do it)")
            guidelines_items = agent_config.get('guidelines', [])
            if isinstance(guidelines_items, list):
                guidelines_text = '\n'.join(guidelines_items)
            else:
                guidelines_text = guidelines_items
            
            guidelines = st.text_area(
                "Evaluation criteria and approach (one per line for lists)",
                value=guidelines_text,
                height=100,
                key=f"guidelines_{agent_name}",
                help="How to approach the task"
            )
            
            # 5. Additional Guidelines
            st.markdown("**5️⃣ Additional Guidelines** (Constraints/boundaries)")
            add_guidelines_items = agent_config.get('additional_guidelines', [])
            if isinstance(add_guidelines_items, list):
                add_guidelines_text = '\n'.join(add_guidelines_items)
            else:
                add_guidelines_text = add_guidelines_items
            
            additional_guidelines = st.text_area(
                "Constraints, what NOT to do (one per line for lists)",
                value=add_guidelines_text,
                height=80,
                key=f"additional_guidelines_{agent_name}",
                help="Boundaries and constraints"
            )
            
            # 6. Response Format
            st.markdown("**6️⃣ Response Format** (Output format)")
            response_format = st.text_area(
                "Exact format the agent should respond in",
                value=agent_config.get('response_format', ''),
                height=100,
                key=f"response_format_{agent_name}",
                help="Format instructions for the output"
            )
            
            # Save button
            st.divider()
            st.caption(f"💾 Changes will be saved to: `{pm.config_path}`")
            
            col_save, col_reset = st.columns(2)
            
            with col_save:
                if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                    # Update config with unified structure
                    updated_config = agent_config.copy()
                    updated_config['role'] = role
                    
                    # Parse input as list if multi-line
                    input_lines = [line.strip() for line in input_value.split('\n') if line.strip()]
                    updated_config['input'] = input_lines if len(input_lines) > 1 else input_value
                    
                    updated_config['task'] = task
                    
                    # Parse guidelines as list if multi-line
                    guidelines_lines = [line.strip() for line in guidelines.split('\n') if line.strip()]
                    updated_config['guidelines'] = guidelines_lines if len(guidelines_lines) > 1 else guidelines
                    
                    # Parse additional guidelines as list if multi-line
                    add_guidelines_lines = [line.strip() for line in additional_guidelines.split('\n') if line.strip()]
                    updated_config['additional_guidelines'] = add_guidelines_lines if len(add_guidelines_lines) > 1 else additional_guidelines
                    
                    updated_config['response_format'] = response_format
                    
                    # Save
                    pm.prompts[agent_name] = updated_config
                    pm.save_prompts(pm.prompts)
                    
                    st.success(f"✅ Saved to `{pm.config_path}`!")
                    st.rerun()
            
            with col_reset:
                if st.button("🔄 Reset", use_container_width=True):
                    st.rerun()
        
        with editor_tab2:
            # Validation for unified structure
            validation = pm.validate_agent_prompt(agent_name)
            
            # Check if there are any issues or warnings
            has_issues = bool(validation.get('issues'))
            has_warnings = bool(validation.get('warnings'))
            has_unmapped_vars = len(validation.get('unmapped_variables', [])) > 0
            
            # Output schema checks
            output_schema_val = validation.get('output_schema', {})
            has_output_issues = bool(output_schema_val.get('issues'))
            has_output_warnings = bool(output_schema_val.get('warnings'))
            
            # Overall validation is problematic if there are any issues
            is_problematic = has_issues or has_output_issues or has_unmapped_vars
            
            # Overall status - compact
            st.markdown("**🎯 Validation Status:**")
            
            col_status, col_comp = st.columns([2, 1])
            
            with col_status:
                if validation['is_valid'] and not is_problematic:
                    st.success("✅ All checks passed!")
                elif has_issues or has_output_issues:
                    st.error(f"❌ {len(validation.get('issues', [])) + len(output_schema_val.get('issues', []))} critical issues found")
                else:
                    st.warning(f"⚠️ {len(validation.get('warnings', [])) + len(output_schema_val.get('warnings', []))} warnings found")
            
            with col_comp:
                components = validation.get('components', {})
                present = sum(1 for v in components.values() if v)
                total = len(components)
                st.metric("Components", f"{present}/{total}")
            
            # Show issues (always visible if present)
            if validation.get('issues'):
                st.error("**Critical Issues:**")
                for issue in validation['issues']:
                    st.write(f"  🚫 {issue}")
            
            # Show warnings (always visible if present)
            if validation.get('warnings'):
                st.warning(f"**⚠️ {len(validation['warnings'])} Warnings:**")
                for warning in validation['warnings']:
                    st.caption(f"• {warning}")
            
            # Component checklist - collapse if all valid
            missing_required = not (components.get('role') and components.get('input') 
                                   and components.get('task') and components.get('response_format'))
            
            with st.expander(f"📋 Component Checklist ({present}/{total})", expanded=missing_required):
                col_comp1, col_comp2 = st.columns(2)
                with col_comp1:
                    st.write("✅ Role" if components.get('role') else "❌ Role")
                    st.write("✅ Input" if components.get('input') else "❌ Input")
                    st.write("✅ Task" if components.get('task') else "❌ Task")
                
                with col_comp2:
                    st.write("✅ Guidelines" if components.get('guidelines') else "⚠️ Guidelines (optional)")
                    st.write("✅ Additional Guidelines" if components.get('additional_guidelines') else "⚠️ Additional Guidelines (optional)")
                    st.write("✅ Response Format" if components.get('response_format') else "❌ Response Format")
            
            # Variable analysis - collapse if all mapped
            with st.expander(f"📊 Variable Analysis ({validation['variable_count']} variables)", 
                           expanded=has_unmapped_vars):
                if validation['variable_count'] == 0:
                    st.info("No variables detected in input section")
                else:
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        st.metric("Total", validation['variable_count'])
                    with col_v2:
                        st.metric("✅ Mapped", len(validation.get('mapped_variables', [])))
                    with col_v3:
                        unmapped_count = len(validation.get('unmapped_variables', []))
                        st.metric("⚠️ Unmapped", unmapped_count)
                    
                    # Show variable details
                    if validation['detected_variables']:
                        st.caption("**Variable Mappings:**")
                        for var in sorted(validation['detected_variables']):
                            availability = pm.check_variable_availability(var)
                            
                            if availability['has_mapping']:
                                # Build inline mapping display
                                mappings = []
                                for key in availability['mapping_keys']:
                                    parts = key.split('.')
                                    if len(parts) == 1:
                                        mappings.append(f"`state['{key}']`")
                                    else:
                                        state_path = "state['" + "']['".join(parts) + "']"
                                        mappings.append(f"`{state_path}`")
                                mapping_str = ", ".join(mappings)
                                st.markdown(f"✅ `{{{var}}}` → {mapping_str}")
                            else:
                                st.markdown(f"⚠️ `{{{var}}}` - {availability['suggestion']}")
            
            # Output Schema Validation - collapse if valid
            st.divider()
            
            if output_schema_val.get('has_schema'):
                output_type = output_schema_val.get('output_type', 'unknown')
                type_emoji = {'json': '📋', 'plain_text': '📝', 'markdown': '📄'}.get(output_type, '❓')
                field_count = len(output_schema_val.get('required_fields', []))
                
                # Inline status display
                if output_schema_val['is_valid']:
                    if output_schema_val.get('warnings'):
                        st.warning(f"⚠️ Valid {type_emoji} {output_type} with {len(output_schema_val['warnings'])} warnings")
                    else:
                        st.success(f"✅ Valid {type_emoji} {output_type} ({field_count} fields)")
                else:
                    st.error(f"❌ Invalid {type_emoji} {output_type} - {len(output_schema_val.get('issues', []))} issues")
                
                # Show issues (if any) - always visible
                if output_schema_val.get('issues'):
                    st.error("**Critical Issues:**")
                    for issue in output_schema_val['issues']:
                        st.caption(f"🚫 {issue}")
                
                # Show warnings (if any) - always visible
                if output_schema_val.get('warnings'):
                    st.warning(f"**⚠️ {len(output_schema_val['warnings'])} Warnings:**")
                    for warning in output_schema_val['warnings']:
                        st.caption(f"• {warning}")
                
                # Collapse details if no issues
                expand_details = bool(output_schema_val.get('issues')) or bool(output_schema_val.get('warnings'))
                
                with st.expander(f"📋 Schema Details ({output_type}, {field_count} fields)", 
                               expanded=expand_details):
                    # Compact format display (inline)
                    if output_schema_val.get('format_example'):
                        st.caption(f"**Format:** `{output_schema_val['format_example']}`")
                    
                    # Compact fields and state display (2 columns)
                    if output_schema_val.get('required_fields') or output_schema_val.get('state_updates'):
                        col_fields_list, col_state = st.columns(2)
                        
                        with col_fields_list:
                            if output_schema_val.get('required_fields'):
                                st.caption("**Required Fields:**")
                                for field in output_schema_val['required_fields']:
                                    st.caption(f"• `{field}`")
                        
                        with col_state:
                            if output_schema_val.get('state_updates'):
                                st.caption("**State Updates:**")
                                for state_key in output_schema_val['state_updates']:
                                    st.caption(f"• `{state_key}`")
                    
                    # Routing dependencies (always important - show if exists)
                    if output_schema_val.get('routing_dependencies'):
                        st.caption("**🔀 Routing Dependencies:**")
                        for dep in output_schema_val['routing_dependencies']:
                            state_key = dep.get('state_key', '')
                            condition = dep.get('condition', '')
                            description = dep.get('description', '')
                            
                            # Compact single-line format
                            if condition:
                                st.caption(f"• `{state_key}` → {condition}")
                            else:
                                st.caption(f"• `{state_key}`")
                            if description and len(description) < 60:
                                st.caption(f"  _{description}_")
            else:
                st.info("💡 **Tip:** Add `output_schema` to enable output validation")
        
        with editor_tab3:
            # Preview for unified structure
            st.markdown("**🎬 Prompt Preview:**")
            
            try:
                # Build preview from components
                preview_parts = []
                
                if agent_config.get('role'):
                    preview_parts.append("# Your Role")
                    preview_parts.append(agent_config['role'])
                    preview_parts.append("")
                
                if agent_config.get('input'):
                    preview_parts.append("# Input")
                    input_items = agent_config['input']
                    if isinstance(input_items, list):
                        preview_parts.append('\n'.join(input_items))
                    else:
                        preview_parts.append(str(input_items))
                    preview_parts.append("")
                
                if agent_config.get('task'):
                    preview_parts.append("# Task")
                    preview_parts.append(agent_config['task'])
                    preview_parts.append("")
                
                if agent_config.get('guidelines'):
                    preview_parts.append("# Guidelines")
                    guidelines = agent_config['guidelines']
                    if isinstance(guidelines, list):
                        preview_parts.append('\n'.join(f"- {g}" for g in guidelines))
                    else:
                        preview_parts.append(guidelines)
                    preview_parts.append("")
                
                if agent_config.get('additional_guidelines'):
                    preview_parts.append("# Additional Guidelines")
                    add_guidelines = agent_config['additional_guidelines']
                    if isinstance(add_guidelines, list):
                        preview_parts.append('\n'.join(f"- {g}" for g in add_guidelines))
                    else:
                        preview_parts.append(add_guidelines)
                    preview_parts.append("")
                
                if agent_config.get('response_format'):
                    preview_parts.append("# Response Format")
                    preview_parts.append(agent_config['response_format'])
                
                preview_text = '\n'.join(preview_parts)
                st.code(preview_text, language="markdown")
                
            except Exception as e:
                st.error(f"Error generating preview: {e}")
    
    else:
        # No node selected or node not editable
        if st.session_state.clicked_node:
            node = st.session_state.clicked_node
            if node in ["__start__", "__end__", "next_topic", "human_input_node"]:
                st.info(f"ℹ️ Node **{node}** is a control flow node and doesn't have an editable prompt.")
            else:
                st.info(f"ℹ️ Node **{node}** clicked, but no prompt mapping found.")
        else:
            st.info("👈 Click on an agent node in the graph to edit its prompt")
            
            # Show available agents
            st.markdown("**Available agents:**")
            for node, agent in NODE_TO_AGENT_MAP.items():
                st.write(f"• **{node}** → `{agent}`")
