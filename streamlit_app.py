import streamlit as st
from datetime import datetime
from agent import start_interview, conduct_interview, generate_feedback

# Streamlit UI
st.set_page_config(page_title="AI Interview Agent", page_icon="💼", layout="wide")

st.title("💼 AI Technical Interview Agent")
st.markdown("Practice your technical interview skills with an AI interviewer")

# Initialize session state
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'interview_ended' not in st.session_state:
    st.session_state.interview_ended = False

# Sidebar for starting interview
with st.sidebar:
    st.header("Interview Setup")
    
    if not st.session_state.interview_started:
        job_title = st.text_input("Job Title", placeholder="e.g., Senior Software Engineer")
        
        if st.button("Start Interview", type="primary", disabled=not job_title):
            with st.spinner("Starting interview..."):
                # Generate unique session ID
                st.session_state.session_id = f"interview_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Start interview
                initial_response = start_interview(job_title, st.session_state.session_id)
                
                # Add to messages
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": initial_response
                })
                
                st.session_state.interview_started = True
                st.session_state.job_title = job_title
                st.rerun()
    
    else:
        st.success(f"Interview in progress")
        st.info(f"Position: {st.session_state.job_title}")
        
        if st.button("End Interview & Get Feedback", type="secondary"):
            st.session_state.interview_ended = True
            st.rerun()
        
        if st.button("Reset Interview", type="primary"):
            st.session_state.interview_started = False
            st.session_state.session_id = None
            st.session_state.messages = []
            st.session_state.interview_ended = False
            st.rerun()

# Main chat interface
if st.session_state.interview_started and not st.session_state.interview_ended:
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Type your answer here..."):
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Get interviewer response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = conduct_interview(st.session_state.session_id, user_input)
                st.markdown(response)
        
        # Add assistant response to messages
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        
        st.rerun()

elif st.session_state.interview_ended:
    st.header("📊 Interview Feedback")
    
    # Only generate feedback once and cache it
    if 'feedback' not in st.session_state:
        with st.spinner("Generating comprehensive feedback..."):
            st.session_state.feedback = generate_feedback(st.session_state.session_id)
    
    st.markdown(st.session_state.feedback)
    
    if st.button("Start New Interview"):
        # Clear ALL session state including feedback
        st.session_state.interview_started = False
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.interview_ended = False
        st.session_state.feedback = None  # Clear cached feedback
        st.rerun()

else:
    # Welcome screen
    st.markdown("""
    ## Welcome to the AI Interview Agent! 👋
    
    This application helps you practice technical interviews with an AI interviewer.
    
    ### How it works:
    1. **Enter the job title** you're interviewing for in the sidebar
    2. **Start the interview** and answer questions naturally
    3. **Have a conversation** - the AI will ask follow-up questions based on your responses
    4. **End the interview** when you're ready to get detailed feedback
    
    ### Tips for a great interview:
    - Be specific and provide examples from your experience
    - Take your time to think through your answers
    - Ask for clarification if you don't understand a question
    - Be honest about your skills and experience
    
    **Ready to begin?** Enter a job title in the sidebar and click "Start Interview"!
    """)
