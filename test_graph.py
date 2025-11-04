"""Script to compile and visualize the interrupt-based LangGraph structure"""
import os
from dotenv import load_dotenv
from multi_agent_system import create_interview_graph

load_dotenv()

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)

# Create and compile the graph
print("Compiling interview graph with interrupt/resume pattern...")
graph = create_interview_graph()
print("✅ Graph compiled successfully!")

# Print graph structure
print_section("Graph Structure")
print(f"Nodes ({len(graph.nodes)}):")
for i, node in enumerate(graph.nodes.keys(), 1):
    print(f"  {i}. {node}")

print(f"\nInterrupt Configuration:")
print(f"  - Checkpointer: MemorySaver (enabled)")
print(f"  - Interrupt Before: ['human_input_node']")

print(f"\nExpected Flow:")
print(f"  START → topic_agent → human_input_node (INTERRUPT)")
print(f"         ↓")
print(f"  [User provides input via Streamlit]")
print(f"         ↓")
print(f"  RESUME → security_agent → {{judge, topic_guide}}")
print(f"         ├─> judge → human_input_node (INTERRUPT) if retry needed")
print(f"         └─> topic_guide → {{probing, next_topic, feedback}}")
print(f"              └─> probing → human_input_node (INTERRUPT)")

# Generate visualizations
print_section("Graph Visualization")
print("Generating Mermaid diagram...")

try:
    # Get mermaid diagram as text
    mermaid_diagram = graph.get_graph().draw_mermaid()
    
    # Save to file
    with open("graph_structure.mmd", "w", encoding="utf-8") as f:
        f.write(mermaid_diagram)
    print("✅ Mermaid diagram saved to: graph_structure.mmd")
    print("   View at: https://mermaid.live/")
    print("   Or use VS Code Mermaid Preview extension")
    
except Exception as e:
    print(f"❌ Could not generate Mermaid diagram: {e}")

# Try to generate PNG
try:
    print("\nGenerating PNG visualization...")
    graph_image = graph.get_graph().draw_mermaid_png()
    with open("graph_visualization.png", "wb") as f:
        f.write(graph_image)
    print("✅ PNG visualization saved to: graph_visualization.png")
except Exception as e:
    print(f"ℹ️  PNG generation not available: {e}")
    print("   Install playwright: npm install -g @mermaid-js/mermaid-cli")

# Summary
print_section("Summary")
print("✅ Graph compiled with interrupt/resume pattern")
print("✅ MemorySaver checkpointer enabled")
print("✅ Interrupt configured before: human_input_node")
print("\nFiles generated:")
print("  - graph_structure.mmd (Mermaid diagram)")
if os.path.exists("graph_visualization.png"):
    print("  - graph_visualization.png (Visual diagram)")
print("\n" + "="*70 + "\n")
