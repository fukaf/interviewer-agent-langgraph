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
if 'waiting_for_user' not in st.session_state:
    st.session_state.waiting_for_user = False
if 'logger' not in st.session_state:
    st.session_state.logger = None
if 'last_processed_input' not in st.session_state:
    st.session_state.last_processed_input = None
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'input_key_counter' not in st.session_state:
    st.session_state.input_key_counter = 0
if 'feedback' not in st.session_state:
    st.session_state.feedback = None
if 'feedback_tokens' not in st.session_state:
    st.session_state.feedback_tokens = 0

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
            
            # Show themes
            themes = set([t.get('theme', 'General') for t in topics])
            with st.expander(f"📋 Themes ({len(themes)})"):
                for theme in sorted(themes):
                    st.write(f"• {theme}")
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
                    "last_message_tokens": 0
                }
                
                # Create graph
                st.session_state.graph = create_interview_graph()
                
                # Initialize state values that aren't in TypedDict
                st.session_state.state["waiting_for_user_input"] = False
                
                # Generate first question only (topic_agent)
                # The graph will stop after topic_agent sets waiting_for_user_input=True
                for output in st.session_state.graph.stream(st.session_state.state):
                    # Update state with output
                    for node_name, node_output in output.items():
                        st.session_state.state.update(node_output)
                        # Stop if we're waiting for user input
                        if st.session_state.state.get("waiting_for_user_input"):
                            break
                    if st.session_state.state.get("waiting_for_user_input"):
                        break
                
                # Add first question to messages
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": st.session_state.state["current_question"],
                    "agent": st.session_state.state["current_agent"],
                    "tokens": st.session_state.state["last_message_tokens"]
                })
                
                st.session_state.interview_started = True
                st.session_state.waiting_for_user = True
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
        
        if st.button("End Interview & Get Feedback", type="secondary"):
            # Prevent multiple invocations
            if st.session_state.get('generating_feedback', False):
                st.warning("Already generating feedback, please wait...")
                st.stop()
            
            st.session_state.generating_feedback = True
            
            try:
                with st.spinner("Generating comprehensive feedback..."):
                    # Mark interview as complete to trigger feedback agent  
                    st.session_state.state["interview_complete"] = True
                    st.session_state.state["user_answer"] = ""  # Clear to ensure route_start goes to feedback
                    st.session_state.state["waiting_for_user_input"] = False  # Not waiting anymore
                    
                    # Log for debugging
                    if st.session_state.logger:
                        st.session_state.logger.text_logger.info("Button clicked: End Interview & Get Feedback")
                        st.session_state.logger.text_logger.info(f"State before invoke: interview_complete={st.session_state.state.get('interview_complete')}")
                    
                    # Invoke graph ONCE to run feedback_agent
                    result = st.session_state.graph.invoke(st.session_state.state)
                    
                    if st.session_state.logger:
                        st.session_state.logger.text_logger.info("Graph invoke completed successfully")
                    
                    # Update state with result
                    st.session_state.state = result
                    
                    # Extract feedback from result
                    if result.get("current_question"):
                        st.session_state.feedback = result["current_question"]
                        st.session_state.feedback_tokens = result.get("last_message_tokens", 0)
                        
                        # Log interview completion
                        if st.session_state.logger:
                            total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                            st.session_state.logger.log_interview_complete(
                                result["current_topic_index"],
                                total_questions
                            )
                    else:
                        # Fallback if no feedback generated
                        st.session_state.feedback = "Feedback generation failed. Please check the logs."
                        st.session_state.feedback_tokens = 0
                    
                    # Mark as ended
                    st.session_state.interview_ended = True
                    
            finally:
                # Always clear the flag even if there's an error
                st.session_state.generating_feedback = False
                
            st.rerun()
        
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
            st.session_state.waiting_for_user = False
            st.session_state.logger = None
            if 'feedback' in st.session_state:
                del st.session_state.feedback
            st.rerun()

# Main chat interface
if st.session_state.interview_started and not st.session_state.interview_ended:
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Show agent and token info for assistant messages
            if message["role"] == "assistant" and "agent" in message:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"{message['agent']}")
                with col2:
                    st.caption(f"🪙 {message.get('tokens', 0)} tokens")
            
            st.markdown(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Type your answer here...", key=st.session_state.input_key_counter):
        
        # Prevent duplicate processing of the same input
        if st.session_state.last_processed_input == user_input:
            # Already processed this input, skip silently
            st.stop()
        
        # Check if we're actually waiting for user input
        if not st.session_state.state.get("waiting_for_user_input", False):
            # System not ready for input yet, skip silently
            st.stop()
        
        # Check if already processing
        if st.session_state.processing:
            # Already processing another input, skip silently
            st.stop()
        
        # Mark as processing FIRST, before doing anything else
        st.session_state.processing = True
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Update state with user answer and clear waiting flag
        st.session_state.state["user_answer"] = user_input
        st.session_state.state["waiting_for_user_input"] = False
        
        # Let LangGraph engine run until it hits END (needs more gas/input)
        with st.spinner("Agents processing..."):
            # Start the engine with invoke() - it will run until END
            result = st.session_state.graph.invoke(st.session_state.state)
            
            # Update state with final result from the graph
            st.session_state.state = result
            
            # Display the question/feedback that was generated
            if result.get("current_question"):
                agent_name = result.get("current_agent", "Agent")
                tokens = result.get("last_message_tokens", 0)
                
                if result.get("interview_complete"):
                    # Feedback agent - store for display on feedback page
                    st.session_state.feedback = result["current_question"]
                    st.session_state.feedback_tokens = tokens
                    st.session_state.interview_ended = True
                    
                    # Log interview completion
                    if st.session_state.logger:
                        total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                        st.session_state.logger.log_interview_complete(
                            result["current_topic_index"],
                            total_questions
                        )
                else:
                    # Display question in chat (judge/probing/topic agent)
                    agent_message = {
                        "role": "assistant",
                        "content": result["current_question"],
                        "agent": agent_name,
                        "tokens": tokens
                    }
                    st.session_state.messages.append(agent_message)
                    
                    with st.chat_message("assistant"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"{agent_name}")
                        with col2:
                            st.caption(f"🪙 {tokens} tokens")
                        st.markdown(result["current_question"])
        
        # Reset processing flag
        st.session_state.processing = False
        st.session_state.input_key_counter += 1
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
        st.session_state.waiting_for_user = False
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
