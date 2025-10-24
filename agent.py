from langchain.schema.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

load_dotenv()

# Initialize memory and OpenAI model
memory = MemorySaver()
model = ChatOpenAI(temperature=0.7, model="gpt-4")
agent_executor = create_react_agent(
    model,
    tools=[],
    checkpointer=memory
)

# Define interview system prompts
INITIAL_ANALYSIS_PROMPT = """You are an expert technical interviewer. Start directly with a warm, professional greeting and your first question for the {job_title} position.
Keep your responses conversational and natural, like a real human interviewer would.
Ask only ONE question at a time and wait for the response.
"""

INTERVIEW_PROMPT = """You are conducting a technical interview. Remember:
1. Keep the conversation natural and friendly
2. Ask only ONE question at a time
3. Listen to the response and ask relevant follow-up questions
4. Stay focused on both technical skills and real-world application
5. Don't reveal that you're an AI - maintain a professional human interviewer persona
6. Base your next question on the candidate's previous response
7. If the candidate's answer is vague or incomplete, ask for specific examples or clarification"""

FEEDBACK_PROMPT = """Based on the entire interview, provide constructive feedback as a professional interviewer would.
Format your response in markdown with the following sections:

## Overall Assessment
Provide a brief summary of the candidate's performance.

## Key Strengths
- List key strengths demonstrated during the interview
- Include specific examples from the conversation
- Highlight both technical and soft skills

## Areas for Improvement
- List areas where the candidate could improve
- Provide specific examples from the interview
- Include constructive suggestions for each point

## Technical Skills Assessment
| Skill Area | Rating | Comments |
|------------|--------|----------|
| Technical Knowledge | ⭐⭐⭐⭐⭐ | Brief comment |
| Problem Solving | ⭐⭐⭐⭐⭐ | Brief comment |
| Communication | ⭐⭐⭐⭐⭐ | Brief comment |
(Add relevant skill areas based on the interview)

## Recommendations
1. Specific action item for improvement
2. Suggested resources or learning paths
3. Career development suggestions

## Final Notes
Concluding thoughts and any additional observations.

Keep the tone professional and encouraging throughout the feedback."""

def start_interview(job_title, session_id):
    """Start the interview with the given job title"""
    config = {"configurable": {"thread_id": session_id}}
    
    analysis_response = agent_executor.invoke({
        "messages": [
            SystemMessage(content=INITIAL_ANALYSIS_PROMPT.format(job_title=job_title)),
            HumanMessage(content=f"Start the interview for the position of {job_title}")
        ]
    }, config=config)
    
    response_text = analysis_response["messages"][-1].content
    return response_text

def conduct_interview(session_id, user_response):
    """Continue the interview with user's response"""
    config = {"configurable": {"thread_id": session_id}}
    
    interview_response = agent_executor.invoke({
        "messages": [
            SystemMessage(content=INTERVIEW_PROMPT),
            HumanMessage(content=user_response)
        ]
    }, config=config)
    
    response_text = interview_response["messages"][-1].content
    return response_text

def generate_feedback(session_id):
    """Generate final feedback for the interview"""
    config = {"configurable": {"thread_id": session_id}}
    
    feedback_response = agent_executor.invoke({
        "messages": [
            SystemMessage(content=FEEDBACK_PROMPT),
            HumanMessage(content="Generate final feedback for the candidate")
        ]
    }, config=config)
    
    return feedback_response["messages"][-1].content
