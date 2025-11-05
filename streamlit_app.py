import streamlit as st
from datetime import datetime
from multi_agent_system import create_interview_graph, load_topics_from_csv
from logger import InterviewLogger, set_logger, clear_logger, get_logger
import os

# Streamlit UI
st.set_page_config(page_title="AI Interview Agent", page_icon="💼", layout="wide")

st.title("💼 Employee Knowledge Assessment Interview")
st.markdown("Multi-agent system to assess employee knowledge on company topics")

# Initialize session state
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'interview_ended' not in st.session_state:
    st.session_state.interview_ended = False
if 'state' not in st.session_state:
    st.session_state.state = None
if 'graph' not in st.session_state:
    st.session_state.graph = None
if 'logger' not in st.session_state:
    st.session_state.logger = None
if 'last_processed_input' not in st.session_state:
    st.session_state.last_processed_input = None
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'feedback' not in st.session_state:
    st.session_state.feedback = None
if 'feedback_tokens' not in st.session_state:
    st.session_state.feedback_tokens = 0
if 'execution_logs' not in st.session_state:
    st.session_state.execution_logs = []  # Store execution logs for each response

# Sidebar
with st.sidebar:
    st.header("Interview Setup")
    
    if not st.session_state.interview_started:
        # Show LLM provider
        llm_provider = os.getenv("LLM_PROVIDER", "openai").upper()
        st.info(f"🤖 LLM Provider: **{llm_provider}**")
        
        # Load topics to show preview
        topics_file = st.text_input("Topics CSV File", value="topics.csv")
        
        if os.path.exists(topics_file):
            topics = load_topics_from_csv(topics_file)
            st.success(f"✅ Loaded {len(topics)} topics")
            
            # Organize topics by theme
            themes_dict = {}
            for topic in topics:
                theme = topic.get('theme', 'General')
                if theme not in themes_dict:
                    themes_dict[theme] = []
                themes_dict[theme].append(topic)
            
            # Show tree view
            with st.expander(f"📋 Topics Structure ({len(themes_dict)} themes)", expanded=False):
                for theme_idx, theme in enumerate(sorted(themes_dict.keys()), 1):
                    # Theme with toggle for collapsible content
                    show_theme = st.checkbox(f"🎯 {theme} ({len(themes_dict[theme])} topics)", key=f"theme_{theme_idx}", value=False)
                    
                    if show_theme:
                        for idx, topic in enumerate(themes_dict[theme], 1):
                            # Topic name with indentation
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**{idx}. {topic.get('topic', 'N/A')}**")
                            
                            # Example questions with more indentation
                            example_questions = topic.get('example_questions', [])
                            if example_questions:
                                for q_idx, question in enumerate(example_questions, 1):
                                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {question}")
                            
                            # Add spacing between topics
                            if idx < len(themes_dict[theme]):
                                st.write("")
                    
                    # Add spacing between themes
                    if theme_idx < len(themes_dict):
                        st.write("")
        else:
            st.warning("⚠️ Topics file not found")
            topics = load_topics_from_csv(topics_file)
        
        max_iterations = st.slider("Max follow-ups per topic", 1, 5, 2)
        max_judge_retries = st.slider("Max judge retry attempts", 0, 5, 2, 
                                       help="How many times the judge can ask to retry an invalid answer. Set to 0 to skip directly to next question.")
        
        if st.button("Start Interview", type="primary"):
            with st.spinner("Initializing multi-agent system..."):
                # Generate unique session ID
                st.session_state.session_id = f"interview_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Initialize logger
                st.session_state.logger = InterviewLogger(st.session_state.session_id)
                set_logger(st.session_state.logger)
                st.session_state.logger.text_logger.info("Interview session initialized")
                
                # Initialize state
                st.session_state.state = {
                    "topics": topics,
                    "current_topic_index": 0,
                    "current_topic": {},
                    "topic_iteration_count": 0,
                    "max_iterations_per_topic": max_iterations,
                    "judge_retry_count": 0,
                    "max_judge_retries": max_judge_retries,
                    "current_question": "",
                    "user_answer": "",
                    "security_passed": False,
                    "security_feedback": "",
                    "topic_depth_sufficient": False,
                    "topic_feedback": "",
                    "interview_complete": False,
                    "conversation_history": [],
                    "current_agent": "",
                    "total_tokens": 0,
                    "last_message_tokens": 0,
                    "waiting_for_user_input": False  # Will be replaced by interrupt mechanism
                }
                
                # Create graph with checkpointer for interrupts
                st.session_state.graph = create_interview_graph()
                
                # Thread config for checkpoint persistence
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                
                # Start graph execution - it will run until hitting HITL (interrupt)
                # The graph will: START → topic_agent → human_input_node (INTERRUPT)
                for chunk in st.session_state.graph.stream(st.session_state.state, config):
                    # Process each node output
                    for node_name, node_output in chunk.items():
                        st.session_state.state.update(node_output)
                
                # At this point, graph is interrupted at human_input_node
                # The first question has been generated
                
                # Add first question to messages
                if st.session_state.state.get("current_question"):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": st.session_state.state["current_question"],
                        "agent": st.session_state.state.get("current_agent", "Topic Agent"),
                        "tokens": st.session_state.state.get("last_message_tokens", 0)
                    })
                
                st.session_state.interview_started = True
                st.rerun()
    
    else:
        st.success("✅ Interview in progress")
        
        # Show progress
        if st.session_state.state:
            current_idx = st.session_state.state["current_topic_index"]
            total_topics = len(st.session_state.state["topics"])
            st.progress((current_idx + 1) / total_topics)
            st.write(f"Topic {current_idx + 1} of {total_topics}")
            
            if st.session_state.state.get("current_topic"):
                st.info(f"**Current Topic:**\n{st.session_state.state['current_topic'].get('topic', 'N/A')}")
            
            # Token usage
            total_tokens = st.session_state.state.get("total_tokens", 0)
            st.metric("Total Tokens Used", total_tokens)
        
        st.divider()
        
        # Only show End Interview button if not already ended and not currently processing
        if not st.session_state.interview_ended and not st.session_state.get('generating_feedback', False):
            if st.button("End Interview & Get Feedback", type="secondary", key="end_interview_btn"):
                # Double-check state before processing (prevent race condition)
                if st.session_state.interview_ended or st.session_state.get('generating_feedback', False) or st.session_state.get('feedback'):
                    st.rerun()
                    
                st.session_state.generating_feedback = True
                
                try:
                    with st.spinner("Generating comprehensive feedback..."):
                        # Log for debugging
                        if st.session_state.logger:
                            st.session_state.logger.text_logger.info("Button clicked: End Interview & Get Feedback")
                        
                        # Thread config for checkpoint
                        config = {"configurable": {"thread_id": st.session_state.session_id}}
                        
                        # Check if graph is at an interruptable state
                        try:
                            snapshot = st.session_state.graph.get_state(config)
                            # If next node list is empty, graph has already completed
                            if not snapshot.next:
                                if st.session_state.logger:
                                    st.session_state.logger.text_logger.warning("Graph already at END state, cannot resume")
                                st.session_state.generating_feedback = False
                                st.rerun()
                        except Exception as e:
                            if st.session_state.logger:
                                st.session_state.logger.text_logger.error(f"Error checking graph state: {e}")
                        
                        # CRITICAL: Set interview_complete flag in graph state
                        # OPTIMIZATION: Instead of going through security → topic_guide,
                        # update state as if we're coming from topic_guide with interview_complete=True
                        # This way topic_guide's routing will immediately see the flag and go to feedback_agent
                        
                        # First, get current state to preserve important fields
                        current_snapshot = st.session_state.graph.get_state(config)
                        current_values = current_snapshot.values
                        
                        # Update state with interview_complete flag, acting as topic_guide node
                        st.session_state.graph.update_state(
                            config,
                            {
                                "interview_complete": True,
                                "topic_depth_sufficient": False,  # Doesn't matter, interview_complete takes priority
                                "user_answer": current_values.get("user_answer", ""),  # Preserve existing answer
                            },
                            as_node="topic_guide"  # Act as if topic_guide just evaluated
                        )
                        
                        # Resume from topic_guide - will route directly to feedback_agent
                        for chunk in st.session_state.graph.stream(None, config):
                            for node_name, node_output in chunk.items():
                                if isinstance(node_output, dict):
                                    st.session_state.state.update(node_output)
                                    
                                    # Check if we reached feedback_agent (current_agent == "Feedback Agent")
                                    if node_output.get("current_agent") == "Feedback Agent" or node_name == "feedback_agent":
                                        # Extract feedback immediately
                                        if node_output.get("current_question"):
                                            st.session_state.feedback = node_output["current_question"]
                                            st.session_state.feedback_tokens = node_output.get("last_message_tokens", 0)
                                            # Break out of loop once feedback is captured
                                            break
                        
                        if st.session_state.logger:
                            st.session_state.logger.text_logger.info("Graph stream completed successfully")
                        
                        # Verify feedback was extracted
                        if not st.session_state.get('feedback'):
                            # Fallback: try to get from final state
                            if st.session_state.state.get("current_question") and st.session_state.state.get("current_agent") in ["Feedback Agent", "📝 Feedback Agent"]:
                                st.session_state.feedback = st.session_state.state["current_question"]
                                st.session_state.feedback_tokens = st.session_state.state.get("last_message_tokens", 0)
                            else:
                                st.session_state.feedback = "Feedback generation failed. Please check the logs."
                                st.session_state.feedback_tokens = 0
                        
                        # Log interview completion
                        if st.session_state.logger and st.session_state.get('feedback'):
                            total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                            st.session_state.logger.log_interview_complete(
                                st.session_state.state["current_topic_index"],
                                total_questions
                            )
                        
                        # Mark as ended ONLY if feedback was successfully generated
                        if st.session_state.get('feedback'):
                            st.session_state.interview_ended = True
                        
                finally:
                    # Always clear the flag even if there's an error
                    st.session_state.generating_feedback = False
                    
                st.rerun()
        elif st.session_state.get('generating_feedback', False):
            st.info("⏳ Generating feedback, please wait...")
        
        if st.button("Reset Interview", type="primary"):
            # Save and clear logger before reset
            if st.session_state.logger:
                st.session_state.logger.save()
                clear_logger()
            
            st.session_state.interview_started = False
            st.session_state.session_id = None
            st.session_state.messages = []
            st.session_state.interview_ended = False
            st.session_state.state = None
            st.session_state.graph = None
            st.session_state.logger = None
            if 'feedback' in st.session_state:
                del st.session_state.feedback
            st.rerun()

# Main chat interface
if st.session_state.interview_started and not st.session_state.interview_ended:
    # Display chat messages
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # Show agent and token info for assistant messages
            if message["role"] == "assistant" and "agent" in message:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"{message['agent']}")
                with col2:
                    st.caption(f"🪙 {message.get('tokens', 0)} tokens")
            
            st.markdown(message["content"])
            
            # Show debug expander for assistant messages with execution logs
            if message["role"] == "assistant" and "execution_log" in message:
                execution_log = message["execution_log"]
                
                with st.expander("🔍 Debug: Agent Flow", expanded=False):
                    for i, log in enumerate(execution_log, 1):
                        node = log["node"]
                        agent = log["agent"]
                        details = log["details"]
                        
                        # Security Agent
                        if node == "security_agent":
                            status = "✅ PASSED" if details.get("passed") else "❌ FAILED"
                            next_step = "→ Topic Guide" if details.get("passed") else "→ Judge"
                            st.markdown(f"**{i}. 🔒 Security** {status} {next_step}")
                            if not details.get("passed"):
                                st.caption(f"   Reason: {details.get('feedback', 'N/A')}")
                        
                        # Judge Agent
                        elif node == "judge":
                            action = "Retry" if details.get('action') == 'requesting retry' else "Give up"
                            next_step = "→ HITL" if details.get('action') == 'requesting retry' else "→ Topic Guide"
                            st.markdown(f"**{i}. ⚖️ Judge** {action} ({details.get('retry_count', 0)}/{details.get('max_retries', 0)}) {next_step}")
                        
                        # Topic Guide
                        elif node == "topic_guide":
                            depth = "✅ Sufficient" if details.get("depth_sufficient") else "❌ Needs More"
                            if details.get("depth_sufficient"):
                                next_step = "→ Next Topic" if details.get('iteration', 0) < details.get('max_iterations', 0) else "→ Feedback"
                            else:
                                next_step = "→ Probing"
                            st.markdown(f"**{i}. 📊 Topic Guide** {depth} {next_step}")
                            if details.get("feedback"):
                                st.caption(f"   {details.get('feedback', '')}")
                        
                        # Probing Agent
                        elif node == "probing_agent":
                            st.markdown(f"**{i}. 🔍 Probing** Follow-up → HITL")
                            st.caption(f"   Topic: {details.get('topic', 'N/A')}")
                        
                        # Topic Agent
                        elif node == "topic_agent":
                            st.markdown(f"**{i}. 🎯 Topic Agent** New question → HITL")
                            st.caption(f"   Topic: {details.get('topic', 'N/A')}")
                        
                        # Next Topic
                        elif node == "next_topic":
                            st.markdown(f"**{i}. ➡️ Next Topic** → Topic Agent")
                        
                        # Human Input Node
                        elif node == "human_input_node":
                            st.markdown(f"**{i}. 👤 HITL** Interrupted → Security")
                    
                    # Compact state summary
                    st.caption(f"State: Topic {message.get('topic_index', 0)} | Iteration {message.get('topic_iteration', 0)} | Judge Retries {message.get('judge_retries', 0)}")
    
    # Chat input
    if user_input := st.chat_input("Type your answer here..."):
        
        # Prevent duplicate processing of the same input
        if st.session_state.last_processed_input == user_input:
            # Already processed this input, skip silently
            st.stop()
        
        # Check if already processing
        if st.session_state.processing:
            # Already processing another input, skip silently
            st.stop()
        
        # Mark as processing FIRST, before doing anything else
        st.session_state.processing = True
        st.session_state.last_processed_input = user_input
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Update state with user answer
        st.session_state.state["user_answer"] = user_input
        
        # Thread config for checkpoint persistence
        config = {"configurable": {"thread_id": st.session_state.session_id}}
        
        st.session_state.graph.update_state(
            config,
            {"user_answer": user_input},
            as_node="human_input_node"  # Update as if human_input_node produced this
        )
        
        # Resume graph from interrupt with user input
        # Graph continues: human_input_node → security_agent → ...
        # Until it hits another interrupt (human_input_node again) or END (feedback_agent)
        
        # Track execution flow for debugging
        execution_log = []
        
        with st.spinner("Agents processing..."):
            # Resume from interrupt by calling invoke with None and config
            # This tells LangGraph: "continue from where you left off"
            for chunk in st.session_state.graph.stream(None, config):
                # Process each node output
                for node_name, node_output in chunk.items():
                    # node_output should be a dict, but handle edge cases
                    if not isinstance(node_output, dict):
                        continue
                    
                    st.session_state.state.update(node_output)
                    
                    # Log execution details
                    log_entry = {
                        "node": node_name,
                        "agent": node_output.get("current_agent", ""),
                        "details": {}
                    }
                    
                    # Security agent details
                    if node_name == "security_agent":
                        log_entry["details"] = {
                            "passed": node_output.get("security_passed"),
                            "feedback": node_output.get("security_feedback", ""),
                            "answer_length": len(st.session_state.state.get("user_answer", "")),
                        }
                    
                    # Judge agent details
                    elif node_name == "judge":
                        log_entry["details"] = {
                            "retry_count": node_output.get("judge_retry_count", 0),
                            "max_retries": st.session_state.state.get("max_judge_retries", 0),
                            "action": "requesting retry" if node_output.get("waiting_for_user_input") else "giving up"
                        }
                    
                    # Topic guide details
                    elif node_name == "topic_guide":
                        log_entry["details"] = {
                            "depth_sufficient": node_output.get("topic_depth_sufficient"),
                            "iteration": st.session_state.state.get("topic_iteration_count", 0),
                            "max_iterations": st.session_state.state.get("max_iterations_per_topic", 0),
                            "feedback": node_output.get("topic_feedback", ""),
                        }
                    
                    # Topic/Probing agent details
                    elif node_name in ["topic_agent", "probing_agent"]:
                        log_entry["details"] = {
                            "question_generated": bool(node_output.get("current_question")),
                            "topic": st.session_state.state.get("current_topic", {}).get("topic", ""),
                            "theme": st.session_state.state.get("current_topic", {}).get("theme", ""),
                        }
                    
                    execution_log.append(log_entry)
            
            # Graph has either:
            # 1. Reached another interrupt (human_input_node) - new question ready
            # 2. Reached END (feedback_agent) - interview complete
            
            # Display the new question/feedback if generated
            if st.session_state.state.get("current_question"):
                agent_name = st.session_state.state.get("current_agent", "Agent")
                tokens = st.session_state.state.get("last_message_tokens", 0)
                
                if st.session_state.state.get("interview_complete"):
                    # Feedback agent - store for display on feedback page
                    st.session_state.feedback = st.session_state.state["current_question"]
                    st.session_state.feedback_tokens = tokens
                    st.session_state.interview_ended = True
                    
                    # Log interview completion
                    if st.session_state.logger:
                        total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                        st.session_state.logger.log_interview_complete(
                            st.session_state.state["current_topic_index"],
                            total_questions
                        )
                else:
                    # Display question in chat (judge/probing/topic agent)
                    agent_message = {
                        "role": "assistant",
                        "content": st.session_state.state["current_question"],
                        "agent": agent_name,
                        "tokens": tokens,
                        "execution_log": execution_log,  # Store execution log with message
                        "topic_index": st.session_state.state.get("current_topic_index", 0),
                        "topic_iteration": st.session_state.state.get("topic_iteration_count", 0),
                        "judge_retries": st.session_state.state.get("judge_retry_count", 0)
                    }
                    st.session_state.messages.append(agent_message)
                    
                    with st.chat_message("assistant"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"{agent_name}")
                        with col2:
                            st.caption(f"🪙 {tokens} tokens")
                        st.markdown(st.session_state.state["current_question"])
        
        # Reset processing flag
        st.session_state.processing = False
        st.rerun()

elif st.session_state.interview_ended:
    st.header("📊 Interview Feedback")
    
    # Display feedback that was generated by feedback_agent in the graph
    if 'feedback' in st.session_state:
        # Show token usage for feedback
        st.caption(f"📝 Feedback Agent | 🪙 {st.session_state.get('feedback_tokens', 0)} tokens")
        st.markdown(st.session_state.feedback)
        
        st.divider()
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Topics Covered", st.session_state.state["current_topic_index"])
        with col2:
            st.metric("Total Tokens", st.session_state.state.get("total_tokens", 0))
        with col3:
            st.metric("Messages", len(st.session_state.messages))
        
        st.divider()
        
        # Log download section
        st.subheader("📥 Download Interview Logs")
    else:
        # Feedback not generated properly
        st.error("⚠️ Feedback was not generated properly. Please check the logs for details.")
        st.info("The interview ended but the feedback agent did not produce output.")
        
        # Try to extract from conversation history as fallback
        if st.session_state.state and "conversation_history" in st.session_state.state:
            for entry in reversed(st.session_state.state["conversation_history"]):
                if entry.get("agent") == "feedback_agent" and "feedback" in entry:
                    st.session_state.feedback = entry["feedback"]
                    st.session_state.feedback_tokens = entry.get("tokens", 0)
                    st.success("✅ Recovered feedback from conversation history!")
                    st.markdown(st.session_state.feedback)
                    break
        
        if st.session_state.logger:
            # Save logs before offering download
            st.session_state.logger.save()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Download conversation text
                conversation_text = st.session_state.logger.export_conversation_text()
                st.download_button(
                    label="📄 Download Conversation",
                    data=conversation_text,
                    file_name=f"conversation_{st.session_state.session_id}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # Download full JSON log
                import json
                json_data = json.dumps(st.session_state.logger.log_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📊 Download Full Log (JSON)",
                    data=json_data,
                    file_name=f"interview_{st.session_state.session_id}.json",
                    mime="application/json"
                )
            
            with col3:
                # Show log file location
                st.info(f"Logs saved to:\n`{st.session_state.logger.log_dir}`")
    
    if st.button("Start New Interview", type="primary"):
        # Save and clear logger
        if st.session_state.logger:
            st.session_state.logger.save()
            clear_logger()
        
        st.session_state.interview_started = False
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.interview_ended = False
        st.session_state.state = None
        st.session_state.graph = None
        st.session_state.logger = None
        if 'feedback' in st.session_state:
            del st.session_state.feedback
        if 'feedback_tokens' in st.session_state:
            del st.session_state.feedback_tokens
        st.rerun()

else:
    # Welcome screen
    st.markdown("""
    ## Welcome to the Employee Knowledge Assessment Interview! 👋
    
    This application uses a **multi-agent system** to conduct in-depth interviews about company knowledge.
    
    ### Multi-Agent System:
    - 🎯 **Topic Agent**: Generates questions from predefined topics
    - 🔒 **Security Agent**: Validates answer quality and relevance
    - ⚖️ **Judge Agent**: Provides feedback on unclear answers
    - 📊 **Topic Guide**: Evaluates knowledge depth
    - 🔍 **Probing Agent**: Asks follow-up questions
    - 📝 **Feedback Agent**: Provides comprehensive assessment
    
    ### How it works:
    1. **Upload topics CSV** (or use default) with themes and example questions
    2. **Start the interview** - agents will guide the conversation
    3. **Answer questions** - see which agent is responding and token usage
    4. **Receive feedback** - comprehensive assessment by theme
    
    ### Features:
    - ✅ Agent identification for each message
    - ✅ Real-time token usage tracking
    - ✅ Progress tracking across topics
    - ✅ Intelligent follow-up questions
    - ✅ Theme-based feedback
    
    **Ready to begin?** Configure the interview in the sidebar and click "Start Interview"!
    """)
