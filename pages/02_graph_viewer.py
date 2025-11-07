import streamlit as st
import streamlit.components.v1 as components
import streamlit.components.v2 as components_v2
from pyvis.network import Network
from core import create_interview_graph
import os

st.set_page_config(page_title="Graph Viewer", page_icon="🕸️", layout="wide")

st.title("🕸️ Interview Agent Graph Viewer")
st.markdown("Interactive visualization of the multi-agent interview system")

# Create graph
@st.cache_resource
def get_graph():
    return create_interview_graph()

graph = get_graph()

# Tabs for different visualizations
tab1, tab2, tab3 = st.tabs(["📊 Mermaid Diagram", "🌐 Interactive Network", "📋 Graph Info"])

# Tab 1: Mermaid Diagram
with tab1:
    st.subheader("Mermaid Flow Diagram")
    
    try:
        mermaid_code = graph.get_graph().draw_mermaid()
        
        # Display using mermaid
        st.code(mermaid_code, language="mermaid")
        
        # Also render it
        st.markdown("### Rendered Diagram")
        components.html(f"""
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
            </script>
        </head>
        <body>
            <div class="mermaid">
                {mermaid_code}
            </div>
        </body>
        </html>
        """, height=800, scrolling=True)
        
    except Exception as e:
        st.error(f"Could not generate Mermaid diagram: {e}")

# Tab 2: Interactive Network with Pyvis
with tab2:
    st.subheader("Interactive Network Graph")
    st.markdown("Use the dropdown to select a node and view its details")
    
    # Initialize session state for clicked node
    if 'clicked_node' not in st.session_state:
        st.session_state.clicked_node = None
    
    # Node selector - primary interaction method
    all_node_names = ["__start__", "__end__"] + list(graph.nodes.keys())
    selected_node = st.selectbox(
        "Select a node to view details:",
        options=[""] + all_node_names,
        key="manual_node_select",
        index=0
    )
    if selected_node:
        st.session_state.clicked_node = selected_node
    
    st.caption("Interactive visualization - zoom, pan, and hover for tooltips")
    
    # Create pyvis network
    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#000000", directed=True)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=200, spring_strength=0.001)
    
    # Get graph structure
    graph_structure = graph.get_graph()
    
    # Define node colors and shapes by type
    node_styles = {
        "__start__": {"color": "#90EE90", "shape": "box", "label": "START"},
        "__end__": {"color": "#FFB6C1", "shape": "box", "label": "END"},
        "topic_agent": {"color": "#87CEEB", "shape": "ellipse", "label": "🎯 Topic Agent"},
        "security_agent": {"color": "#DDA0DD", "shape": "ellipse", "label": "🔒 Security Agent"},
        "judge": {"color": "#F0E68C", "shape": "ellipse", "label": "⚖️ Judge Agent"},
        "topic_guide": {"color": "#98FB98", "shape": "ellipse", "label": "📊 Topic Guide"},
        "probing_agent": {"color": "#FFB6C1", "shape": "ellipse", "label": "🔍 Probing Agent"},
        "next_topic": {"color": "#B0E0E6", "shape": "box", "label": "➡️ Next Topic"},
        "human_input_node": {"color": "#FFD700", "shape": "star", "label": "👤 HITL (Interrupt)", "size": 30},
        "feedback_agent": {"color": "#FFA07A", "shape": "ellipse", "label": "📝 Feedback Agent"}
    }
    
    # Add nodes (including __start__ and __end__)
    all_nodes = set(graph.nodes.keys())
    all_nodes.add("__start__")
    all_nodes.add("__end__")
    
    for node in all_nodes:
        style = node_styles.get(node, {"color": "#CCCCCC", "shape": "ellipse", "label": node})
        net.add_node(
            node, 
            label=style["label"],
            color=style["color"],
            shape=style["shape"],
            size=style.get("size", 25),
            title=f"Click to see details of {style['label']}"
        )
    
    # Add edges from graph structure
    edges_added = set()  # Track added edges to avoid duplicates
    
    try:
        # Try to get edges from the compiled graph
        graph_structure = graph.get_graph()
        
        # The graph structure has edges as a list of tuples
        if hasattr(graph_structure, 'edges'):
            for edge in graph_structure.edges:
                # Edges are tuples of (source, target)
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
        else:
            raise AttributeError("No edges attribute found")
    except Exception as e:
        st.warning(f"Could not extract edges automatically: {e}")
        # Fallback: manually define known edges based on graph structure
        known_edges = [
            ("__start__", "topic_agent"),
            ("topic_agent", "human_input_node"),
            ("probing_agent", "human_input_node"),
            ("human_input_node", "security_agent"),
            ("security_agent", "judge"),
            ("security_agent", "topic_guide"),
            ("judge", "human_input_node"),
            ("judge", "topic_guide"),
            ("topic_guide", "probing_agent"),
            ("topic_guide", "next_topic"),
            ("topic_guide", "feedback_agent"),
            ("next_topic", "topic_agent"),
            ("feedback_agent", "__end__")
        ]
        for source, target in known_edges:
            if (source, target) not in edges_added:
                net.add_edge(source, target, arrows="to")
                edges_added.add((source, target))
    
    # Configure physics
    net.set_options("""
    {
        "physics": {
            "enabled": true,
            "stabilization": {
                "enabled": true,
                "iterations": 200
            }
        },
        "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
        }
    }
    """)
    
    # Save the HTML to project folder
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'graph_network.html')
    
    # Generate the pyvis HTML
    base_html = net.generate_html()
    
    # Save it
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(base_html)
    

    # For v2, we need to provide HTML, CSS, and JS separately
    # Since pyvis generates everything together, we'll use iframe approach with messaging
    
    HTML = '<iframe src="about:blank" id="pyvis-frame" style="width:100%; height:600px; border:1px solid #ddd;"></iframe>'
    
    # Escape the HTML for JavaScript string - do this outside f-string
    escaped_html = base_html.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
    
    JS = f"""
    export default function(component) {{
        const {{ setTriggerValue, parentElement }} = component;
        const iframe = parentElement.querySelector('#pyvis-frame');
        
        // Inject the pyvis HTML into iframe
        const html = `{escaped_html}`;
        
        iframe.onload = function() {{
            const doc = iframe.contentDocument || iframe.contentWindow.document;
            doc.open();
            doc.write(html);
            doc.close();
            
            // Wait for network to be ready and add click listener
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
        
        // Trigger load
        iframe.src = 'about:blank';
    }}
    """
    
    CSS = ""
    
    try:
        network_component = components_v2.component(
            "pyvis_network_clickable",
            html=HTML,
            css=CSS,
            js=JS,
        )
        
        result = network_component(on_node_clicked_change=lambda: None)
        
        # Update session state when a node is clicked
        if result and result.get('node_clicked'):
            st.session_state.clicked_node = result['node_clicked']
            st.rerun()
    except Exception as e:
        st.error(f"Error with v2 component: {e}")
        # Fallback
        # components.html(base_html, height=650, scrolling=True)

    
    # Display clicked node information
    st.divider()
    
    if st.session_state.clicked_node:
        st.subheader(f"🔍 Selected Node: {st.session_state.clicked_node}")
        
        # Get node details
        node_name = st.session_state.clicked_node
        
        # Node descriptions
        node_descriptions = {
            "__start__": {
                "type": "Entry Point",
                "description": "The starting point of the interview graph",
                "function": "Initiates the interview flow by triggering the Topic Agent"
            },
            "__end__": {
                "type": "Exit Point",
                "description": "The ending point of the interview graph",
                "function": "Marks the completion of the interview after feedback is provided"
            },
            "topic_agent": {
                "type": "Question Generator",
                "description": "Generates interview questions based on predefined topics",
                "function": "Creates initial questions for each topic from the topic list",
                "interrupts": "Yes - after generating question, waits at HITL for user response"
            },
            "security_agent": {
                "type": "Answer Validator",
                "description": "Validates the quality and relevance of user answers",
                "function": "Checks if answers are substantive and related to the question",
                "routes_to": ["Judge Agent (if failed)", "Topic Guide (if passed)"]
            },
            "judge": {
                "type": "Feedback Provider",
                "description": "Provides constructive feedback on unclear answers",
                "function": "Gives users another chance to answer or gives up after max retries",
                "routes_to": ["HITL (if retry)", "Topic Guide (if giving up)"]
            },
            "topic_guide": {
                "type": "Depth Evaluator",
                "description": "Evaluates whether the topic has been explored sufficiently",
                "function": "Decides if more probing is needed or if we should move on",
                "routes_to": ["Probing Agent (needs more depth)", "Next Topic (sufficient)", "Feedback Agent (interview complete)"]
            },
            "probing_agent": {
                "type": "Follow-up Generator",
                "description": "Generates follow-up questions to probe deeper",
                "function": "Creates targeted follow-up questions to explore topic depth",
                "interrupts": "Yes - after generating follow-up, waits at HITL for user response"
            },
            "next_topic": {
                "type": "Topic Advancer",
                "description": "Advances to the next topic in the list",
                "function": "Increments topic index and prepares for next topic",
                "routes_to": ["Topic Agent"]
            },
            "human_input_node": {
                "type": "HITL Interrupt Point",
                "description": "⚠️ Human-in-the-Loop interrupt - graph pauses here",
                "function": "Graph execution stops here, waiting for user input via Streamlit",
                "interrupt": "This is where LangGraph pauses execution using interrupt_before configuration",
                "resume": "After user provides input, graph resumes to Security Agent"
            },
            "feedback_agent": {
                "type": "Final Assessment Provider",
                "description": "Provides comprehensive feedback on interview performance",
                "function": "Generates detailed feedback based on all topics covered",
                "routes_to": ["END"]
            }
        }
        
        details = node_descriptions.get(node_name, {
            "type": "Unknown",
            "description": "No description available",
            "function": "N/A"
        })
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric("Node Type", details.get("type", "N/A"))
            if "interrupts" in details:
                st.warning(f"⚠️ Interrupt: {details['interrupts']}")
            if "interrupt" in details:
                st.error(f"🛑 {details['interrupt']}")
        
        with col2:
            st.write("**Description:**")
            st.write(details.get("description", "N/A"))
            
            st.write("**Function:**")
            st.write(details.get("function", "N/A"))
            
            if "routes_to" in details:
                st.write("**Routes To:**")
                for route in details["routes_to"]:
                    st.write(f"  • {route}")
            
            if "resume" in details:
                st.info(f"▶️ Resume: {details['resume']}")
        
        # Show connections
        st.write("**Connections:**")
        
        # Get edges from graph dictionary
        try:
            graph_structure = graph.get_graph()
            
            # Outgoing edges
            outgoing = []
            incoming = []
            
            if hasattr(graph_structure, 'edges'):
                for edge in graph_structure.edges:
                    # Edges are tuples of (source, target)
                    if isinstance(edge, tuple) and len(edge) >= 2:
                        source, target = edge[0], edge[1]
                    elif hasattr(edge, 'source') and hasattr(edge, 'target'):
                        source, target = edge.source, edge.target
                    else:
                        continue
                    
                    if source == node_name:
                        outgoing.append(target)
                    if target == node_name:
                        incoming.append(source)
            
            if outgoing:
                st.write(f"→ Outgoing: {', '.join(set(outgoing))}")
            else:
                st.write("→ Outgoing: None")
            
            if incoming:
                st.write(f"← Incoming: {', '.join(set(incoming))}")
            else:
                st.write("← Incoming: None")
                
        except Exception as e:
            st.warning(f"Could not extract connections: {e}")
    
    else:
        st.info("👆 Use the dropdown above to select a node and view its details")

# Tab 3: Graph Information
with tab3:
    st.subheader("Graph Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Nodes:**")
        for i, node in enumerate(graph.nodes.keys(), 1):
            st.write(f"{i}. `{node}`")
    
    with col2:
        st.write("**Configuration:**")
        st.write("• Checkpointer: MemorySaver")
        st.write("• Interrupt Before: `human_input_node`")
        st.write("• Pattern: Interrupt/Resume")
    
    st.divider()
    
    st.subheader("Expected Flow")
    st.code("""
START 
  └→ topic_agent (generates first question)
       └→ human_input_node (INTERRUPT - waits for user)
            └→ security_agent (validates answer)
                 ├─ Failed → judge_agent (provides feedback)
                 │            └→ human_input_node (INTERRUPT - waits for retry)
                 │                  └→ security_agent (validates retry)
                 │
                 └─ Passed → topic_guide (evaluates depth)
                              ├─ Not deep → probing_agent (follow-up)
                              │              └→ human_input_node (INTERRUPT)
                              │                    └→ security_agent
                              │
                              ├─ Deep enough → next_topic → topic_agent → human_input_node
                              │
                              └─ All done → feedback_agent → END
    """, language="text")
    
    st.divider()
    
    st.subheader("Legend")
    
    legend_col1, legend_col2 = st.columns(2)
    
    with legend_col1:
        st.markdown("**Node Colors:**")
        st.markdown("🟢 START - Entry point")
        st.markdown("🔵 Question Generators - Topic & Probing Agents")
        st.markdown("🟣 Validators - Security & Judge Agents")
        st.markdown("🟡 **HITL Interrupt** - Human input required")
    
    with legend_col2:
        st.markdown("**Node Shapes:**")
        st.markdown("□ Control Flow - START, END, Next Topic")
        st.markdown("○ Agent Nodes - Processing agents")
        st.markdown("⭐ **Interrupt Point** - HITL node")
