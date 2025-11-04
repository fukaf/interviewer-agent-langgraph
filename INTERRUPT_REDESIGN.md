# LangGraph Interrupt/Resume Pattern Implementation

## Overview
Redesigned the interview system to use LangGraph's native **interrupt/resume** pattern for Human-in-the-Loop (HITL) interactions, replacing the previous END-restart pattern.

## Key Changes

### 1. Graph Architecture (`multi_agent_system.py`)

#### Added Human Input Node (HITL)
```python
def human_input_node(state: InterviewState) -> InterviewState:
    """
    Human-in-the-Loop (HITL) node that pauses graph execution for user input.
    This node triggers an interrupt - graph pauses here automatically.
    """
    return state
```

#### Updated Graph Flow
**Previous Flow (END-restart pattern):**
```
START → route_start() → {topic_agent, security_agent, feedback_agent}
  ├─> topic_agent → wait_for_user_input → END
  ├─> security_agent → judge → wait_for_user_input → END
  └─> (User submits) → Restart from START with user_answer
```

**New Flow (interrupt pattern):**
```
START → topic_agent → HITL (interrupt)
                        ↓
                 [User provides input]
                        ↓
              security_agent → {judge, topic_guide}
                        ↓
      judge → HITL (interrupt)  OR  topic_guide → {next_topic, probing, feedback}
                        ↓
              probing_agent → HITL (interrupt)
                        ↓
              security_agent → ...
```

#### Removed Obsolete Code
- **Deleted**: `route_start()` function - no longer need conditional entry
- **Simplified**: Always start at `topic_agent`
- **Updated**: `route_after_judge()` now returns `"human_input_node"` instead of `"wait_for_user_input"`

#### Added Checkpoint Support
```python
from langgraph.checkpoint.memory import MemorySaver

return workflow.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["human_input_node"]
)
```

### 2. Streamlit Integration (`streamlit_app.py`)

#### Thread Configuration
All graph operations now use thread config for checkpoint persistence:
```python
config = {"configurable": {"thread_id": st.session_state.session_id}}
```

#### Start Interview
**Before:**
```python
for output in graph.stream(state):
    if state.get("waiting_for_user_input"):
        break
```

**After:**
```python
config = {"configurable": {"thread_id": session_id}}
for chunk in graph.stream(state, config):
    # Graph automatically stops at human_input_node (interrupt)
    for node_name, node_output in chunk.items():
        state.update(node_output)
```

#### Process User Input
**Before:**
```python
# Check waiting_for_user_input flag
state["user_answer"] = user_input
state["waiting_for_user_input"] = False
result = graph.invoke(state)  # Restart from START
```

**After:**
```python
# Update state with answer
state["user_answer"] = user_input

# Resume from interrupt (graph continues from human_input_node)
config = {"configurable": {"thread_id": session_id}}
for chunk in graph.stream(None, config):  # None = resume from checkpoint
    for node_name, node_output in chunk.items():
        state.update(node_output)
```

#### End Interview Button
**Before:**
```python
state["interview_complete"] = True
state["user_answer"] = ""  # Hack to route correctly
state["waiting_for_user_input"] = False
result = graph.invoke(state)
```

**After:**
```python
state["interview_complete"] = True
config = {"configurable": {"thread_id": session_id}}
result = graph.invoke(state, config)  # Graph handles routing naturally
```

## Benefits of This Pattern

### 1. **Proper LangGraph Usage**
- Uses native interrupt mechanism instead of working around it
- Maintains graph context between user interactions
- No need to restart from START each time

### 2. **State Consistency**
- Graph state persists in checkpointer
- No manual flag management (`waiting_for_user_input` is now optional)
- State updates flow naturally through the graph

### 3. **Simplified Logic**
- Removed complex entry-point routing (`route_start`)
- No need to check flags before accepting input
- Graph decides when to pause (at `human_input_node`)

### 4. **Better Performance**
- Avoids reprocessing nodes unnecessarily
- Graph resumes exactly where it paused
- Efficient state management with checkpointer

## How It Works

### Interrupt Mechanism
1. Graph executes normally: `START → topic_agent → human_input_node`
2. **Before** entering `human_input_node`, graph pauses (interrupt)
3. Streamlit detects pause and shows `chat_input`
4. User types answer
5. Streamlit calls `graph.stream(None, config)` to resume
6. Graph continues: `human_input_node → security_agent → ...`
7. Process repeats until reaching `END` (feedback_agent)

### Config Parameter
```python
config = {"configurable": {"thread_id": st.session_state.session_id}}
```
- **thread_id**: Unique identifier for this interview session
- Links all graph operations to the same checkpoint
- Allows multiple concurrent interviews (different thread_ids)

### Resume with None
```python
graph.stream(None, config)
```
- `None` means "don't start from beginning"
- Graph loads checkpoint for this thread_id
- Continues from last interrupt point

## Testing Checklist

- [ ] First question generated correctly on start
- [ ] User input resumes graph from interrupt
- [ ] Security validation works after resume
- [ ] Judge retry flow uses interrupts properly
- [ ] Probing questions trigger interrupts
- [ ] "End Interview" button generates feedback
- [ ] Multiple topics flow correctly
- [ ] Session state persists across interactions
- [ ] No infinite loops or duplicate processing
- [ ] Token counting works correctly

## Migration Notes

### State Field Changes
- `waiting_for_user_input` flag is now **optional** (interrupt replaces it)
- Can keep it for backward compatibility or logging
- No longer used for control flow

### Error Handling
- Graph may raise `GraphInterrupt` exception
- This is normal behavior, not an error
- Streamlit should catch and handle gracefully

### Debugging
- Use `graph.get_state(config)` to inspect current state
- `state.next` shows which node will execute next
- Empty `next` means graph has completed (reached END)

## References

- [LangGraph Interrupts Documentation](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)
- [MemorySaver Checkpointer](https://langchain-ai.github.io/langgraph/reference/checkpoints/#memorysaver)
- [Human-in-the-Loop Patterns](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
