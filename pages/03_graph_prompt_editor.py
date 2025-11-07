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
from management.prompt_manager import get_prompt_manager

st.set_page_config(page_title="Graph Prompt Editor", page_icon="🎯", layout="wide")

st.title("🎯 Graph-based Prompt Editor")
st.markdown("Click on a node in the graph to edit its prompt configuration")

# Initialize
@st.cache_resource
def get_graph():
    return create_interview_graph()

graph = get_graph()

try:
    pm = get_prompt_manager()
except FileNotFoundError:
    st.error("❌ `prompts.yaml` file not found.")
    st.stop()

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
        
        # Get agent info
        agent_config = pm.prompts.get(agent_name, {})
        
        # Editor tabs
        editor_tab1, editor_tab2, editor_tab3 = st.tabs(["✏️ Edit", "🔍 Validate", "👁️ Preview"])
        
        with editor_tab1:
            # System message
            st.markdown("**System Message:**")
            system_message = st.text_area(
                "System message (role definition)",
                value=agent_config.get('system', ''),
                height=100,
                key=f"system_{agent_name}",
                label_visibility="collapsed"
            )
            
            # Template
            st.markdown("**Prompt Template:**")
            template = st.text_area(
                "Template with {variables}",
                value=agent_config.get('template', ''),
                height=250,
                key=f"template_{agent_name}",
                label_visibility="collapsed"
            )
            
            # Optional fields
            if 'guidelines' in agent_config:
                st.markdown("**Guidelines:**")
                guidelines = st.text_area(
                    "Guidelines (list)",
                    value='\n'.join(agent_config.get('guidelines', [])),
                    height=100,
                    key=f"guidelines_{agent_name}",
                    label_visibility="collapsed"
                )
            
            if 'fail_criteria' in agent_config:
                st.markdown("**Fail Criteria:**")
                fail_criteria = st.text_area(
                    "Fail criteria (list)",
                    value='\n'.join(agent_config.get('fail_criteria', [])),
                    height=100,
                    key=f"fail_criteria_{agent_name}",
                    label_visibility="collapsed"
                )
            
            # Save button
            st.divider()
            col_save, col_reset = st.columns(2)
            
            with col_save:
                if st.button("💾 Save Changes", use_container_width=True):
                    # Update the config
                    updated_config = agent_config.copy()
                    updated_config['system'] = system_message
                    updated_config['template'] = template
                    
                    if 'guidelines' in agent_config:
                        updated_config['guidelines'] = [g.strip() for g in guidelines.split('\n') if g.strip()]
                    if 'fail_criteria' in agent_config:
                        updated_config['fail_criteria'] = [f.strip() for f in fail_criteria.split('\n') if f.strip()]
                    
                    # Save to prompts
                    pm.prompts[agent_name] = updated_config
                    pm.save_prompts(pm.prompts)
                    
                    st.success("✅ Saved successfully!")
                    st.rerun()
            
            with col_reset:
                if st.button("🔄 Reset", use_container_width=True):
                    st.rerun()
        
        with editor_tab2:
            # Validation
            validation = pm.validate_agent_prompt(agent_name)
            
            if validation['is_valid']:
                st.success("✅ Prompt is valid")
            else:
                st.error("❌ Issues found:")
                for issue in validation['issues']:
                    st.write(f"  • {issue}")
            
            if validation.get('warnings'):
                st.warning("⚠️ Warnings:")
                for warning in validation['warnings']:
                    st.write(f"  • {warning}")
            
            st.divider()
            
            # Variable analysis
            st.markdown("**📊 Variable Analysis:**")
            
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.metric("Total Variables", validation['variable_count'])
            with col_v2:
                st.metric("✅ Mapped", len(validation.get('mapped_variables', [])))
            with col_v3:
                st.metric("⚠️ Unmapped", len(validation.get('unmapped_variables', [])))
            
            # Show variables
            if validation['detected_variables']:
                st.markdown("**Variables:**")
                for var in sorted(validation['detected_variables']):
                    availability = pm.check_variable_availability(var)
                    
                    if availability['has_mapping']:
                        st.write(f"✅ `{{{var}}}` - Auto-fills from state")
                        with st.expander(f"Mapping details", expanded=False):
                            for key in availability['mapping_keys']:
                                parts = key.split('.')
                                if len(parts) == 1:
                                    st.code(f"state['{key}']", language=None)
                                else:
                                    state_path = "state['" + "']['".join(parts) + "']"
                                    st.code(state_path, language=None)
                    elif var in agent_config:
                        st.write(f"📋 `{{{var}}}` - Defined in config")
                    else:
                        st.write(f"⚠️ `{{{var}}}` - Manual required")
                        with st.expander(f"Suggestions", expanded=False):
                            st.caption(availability['suggestion'])
        
        with editor_tab3:
            # Preview
            st.markdown("**🎬 Prompt Preview:**")
            st.code(system_message, language="text")
            st.divider()
            st.code(template, language="text")
            
            # Show what it would look like with sample data
            st.divider()
            st.markdown("**📝 Sample Format:**")
            sample_vars = {}
            for var in validation['detected_variables']:
                sample_vars[var] = f"[{var}_value]"
            
            try:
                sample_prompt = template.format(**sample_vars)
                st.text_area("Formatted preview", sample_prompt, height=200, disabled=True)
            except KeyError as e:
                st.warning(f"Cannot preview: missing variable {e}")
    
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
