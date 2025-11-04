"""
Multi-Agent Interview System with LangGraph Interrupts
======================================================
Uses LangGraph interrupt/resume for Human-in-the-Loop interactions
"""

from typing import TypedDict, Literal, Dict, Any
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
import pandas as pd
from dotenv import load_dotenv
import json
import os
from logger import get_logger

load_dotenv()

# ============================================================================
# STATE DEFINITION
# ============================================================================

class InterviewState(TypedDict):
    """State shared across all agents in the interview workflow"""
    
    # Topic management
    topics: list[dict]
    current_topic_index: int
    current_topic: dict
    topic_iteration_count: int
    max_iterations_per_topic: int
    
    # Question and answer tracking
    current_question: str
    user_answer: str
    
    # Agent decisions
    security_passed: bool
    security_feedback: str
    topic_depth_sufficient: bool
    topic_feedback: str
    
    # Judge retry tracking
    judge_retry_count: int  # How many times judge has asked to retry
    max_judge_retries: int  # Maximum retries allowed before moving on
    
    # Interview flow
    interview_complete: bool
    conversation_history: list[dict]
    
    # Agent and token tracking
    current_agent: str
    total_tokens: int
    last_message_tokens: int
    
    # Control flags
    waiting_for_user_input: bool  # Flag to pause execution


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_topics_from_csv(csv_path: str) -> list[dict]:
    """Load interview topics from CSV file"""
    try:
        df = pd.read_csv(csv_path)
        topics = df.to_dict('records')
        
        for topic in topics:
            if 'example_questions' in topic and isinstance(topic['example_questions'], str):
                topic['example_questions'] = [q.strip() for q in topic['example_questions'].split(';')]
        
        return topics
    except FileNotFoundError:
        print(f"Warning: {csv_path} not found. Using placeholder topics.")
        return [
            {
                "theme": "Company Culture & Values",
                "topic": "Mission and Vision",
                "example_questions": [
                    "Can you describe our company's mission in your own words?",
                    "How does it align with your personal values?"
                ]
            },
            {
                "theme": "Products & Services",
                "topic": "Product Knowledge",
                "example_questions": [
                    "Can you explain our main product/service offerings?",
                    "What are the key differentiators of our products?"
                ]
            },
        ]


def get_llm() -> BaseChatModel:
    """Get configured LLM instance based on environment variables
    
    Environment Variables:
    - LLM_PROVIDER: "openai" (default), "azure", or "gemini"
    
    For OpenAI:
    - OPENAI_API_KEY
    
    For Azure OpenAI:
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_DEPLOYMENT_NAME
    - AZURE_OPENAI_API_VERSION (optional, defaults to "2024-02-15-preview")
    
    For Google Gemini:
    - GOOGLE_API_KEY
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    # Log the provider being used
    logger = get_logger()
    if logger:
        logger.set_llm_provider(provider)
    
    if provider == "azure":
        return AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.7
        )
    
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.7
        )
    
    else:  # default to openai
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.7
        )


def track_tokens(state: InterviewState, response: Any) -> InterviewState:
    """Track token usage from LLM response"""
    tokens = 0
    
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        
        # Try OpenAI/Azure format first
        usage = metadata.get('token_usage', {})
        tokens = usage.get('total_tokens', 0)
        
        # If no tokens found, try Gemini format
        if tokens == 0 and 'usage_metadata' in metadata:
            usage_meta = metadata['usage_metadata']
            # Gemini uses prompt_token_count and candidates_token_count
            prompt_tokens = usage_meta.get('prompt_token_count', 0)
            completion_tokens = usage_meta.get('candidates_token_count', 0)
            tokens = prompt_tokens + completion_tokens
        
        # Fallback: estimate from content length if no token info available
        if tokens == 0 and hasattr(response, 'content'):
            # Rough estimate: 1 token ≈ 4 characters
            tokens = len(response.content) // 4
    
    state["last_message_tokens"] = tokens
    state["total_tokens"] = state.get("total_tokens", 0) + tokens
    return state


# ============================================================================
# AGENT IMPLEMENTATIONS WITH LLM
# ============================================================================

def topic_agent(state: InterviewState) -> InterviewState:
    """Topic Agent: Generates questions based on predefined topics"""
    state["current_agent"] = "🎯 Topic Agent"
    
    logger = get_logger()
    if logger:
        logger.log_agent_start("topic_agent", state)
    
    # Check if we've exhausted all topics
    if state["current_topic_index"] >= len(state["topics"]):
        state["interview_complete"] = True
        if logger:
            logger.log_agent_end("topic_agent", {"interview_complete": True})
        return state
    
    current_topic = state["topics"][state["current_topic_index"]]
    state["current_topic"] = current_topic
    state["topic_iteration_count"] = 0
    
    # Reset judge retry counter for new topic
    state["judge_retry_count"] = 0
    
    model = get_llm()
    
    example_qs = current_topic.get('example_questions', [])
    examples_text = '\n'.join([f"- {q}" for q in example_qs])
    
    prompt = f"""You are interviewing an experienced employee about their knowledge and experience.

Theme: {current_topic['theme']}
Topic: {current_topic['topic']}

Example questions for this topic:
{examples_text}

Generate ONE engaging interview question based on this topic. You can use the example questions directly or create a natural variation. Make it conversational and appropriate for an experienced employee.

Respond with ONLY the question, nothing else."""
    
    if logger:
        logger.log_llm_request("topic_agent", prompt, str(model))
    
    response = model.invoke([HumanMessage(content=prompt)])
    state["current_question"] = response.content.strip()
    
    # Track tokens
    state = track_tokens(state, response)
    
    if logger:
        logger.log_llm_response(
            "topic_agent", 
            state["current_question"], 
            state["last_message_tokens"],
            response.response_metadata if hasattr(response, 'response_metadata') else None
        )
    
    # Add to conversation history
    state["conversation_history"].append({
        "agent": "topic_agent",
        "topic": current_topic['topic'],
        "question": state["current_question"],
        "tokens": state["last_message_tokens"]
    })
    
    # Set flag to wait for user input
    state["waiting_for_user_input"] = True
    
    if logger:
        logger.log_agent_end("topic_agent", {
            "question": state["current_question"],
            "waiting_for_user_input": True
        })
    
    return state


def security_agent(state: InterviewState) -> InterviewState:
    """Security Agent: Validates answer relevance and quality"""
    state["current_agent"] = "🔒 Security Agent"
    
    logger = get_logger()
    if logger:
        logger.log_agent_start("security_agent", state)
        logger.log_user_input(state.get("current_question", ""), state.get("user_answer", ""))
    
    # Reset waiting flag since we're processing
    state["waiting_for_user_input"] = False
    
    # Skip if no user answer (shouldn't happen, but safety check)
    if not state.get("user_answer") or state["user_answer"].strip() == "":
        state["security_passed"] = False
        state["security_feedback"] = "No answer provided"
        if logger:
            logger.log_security_check(False, "No answer provided")
            logger.log_agent_end("security_agent", {"passed": False, "reason": "empty_answer"})
        return state
    
    model = get_llm()
    
    prompt = f"""You are a friendly security agent checking answer quality in an interview. Be lenient and supportive.

Question: {state["current_question"]}
Employee Answer: {state["user_answer"]}

Guidelines for evaluation:
1. Is the answer related to the question? (Be flexible - partial relevance is OK)
2. Is there any substance to the answer? (Even short answers can be meaningful)
3. Does it show the employee is trying to engage? (Good faith effort counts)

Be LENIENT - only fail answers that are:
- Completely off-topic or nonsensical
- Single word answers like "yes", "no", "ok"
- Clearly evasive or refusing to answer

Respond ONLY with a JSON object:
{{"passed": true/false, "feedback": "brief, friendly explanation if failed, empty string if passed"}}"""
    
    if logger:
        logger.log_llm_request("security_agent", prompt, str(model))
    
    response = model.invoke([HumanMessage(content=prompt)])
    state = track_tokens(state, response)
    
    if logger:
        logger.log_llm_response(
            "security_agent",
            response.content.strip(),
            state["last_message_tokens"],
            response.response_metadata if hasattr(response, 'response_metadata') else None
        )
    
    try:
        # Strip markdown code blocks if present
        response_text = response.content.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()
        
        result = json.loads(response_text)
        state["security_passed"] = result.get("passed", False)
        state["security_feedback"] = result.get("feedback", "")
        
        # Reset judge retry counter if answer passed
        if state["security_passed"]:
            state["judge_retry_count"] = 0
            
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails - be lenient
        # Accept answers that are at least 10 characters (very low bar)
        state["security_passed"] = len(state["user_answer"]) > 10
        state["security_feedback"] = "" if state["security_passed"] else "Please provide a more detailed answer"
        
        # Reset judge retry counter if answer passed
        if state["security_passed"]:
            state["judge_retry_count"] = 0
            
        if logger:
            logger.log_error("json_parse_error", "Failed to parse security agent response", {
                "response": response.content.strip()
            })
    
    if logger:
        logger.log_security_check(state["security_passed"], state["security_feedback"])
    
    # Store the Q&A pair in conversation history
    state["conversation_history"].append({
        "type": "user_answer",
        "question": state["current_question"],
        "answer": state["user_answer"],
        "passed": state["security_passed"]
    })
    
    if logger:
        logger.log_agent_end("security_agent", {
            "passed": state["security_passed"],
            "feedback": state["security_feedback"]
        })
    
    return state


def judge_agent(state: InterviewState) -> InterviewState:
    """Judge Agent: Provides feedback on failed answers"""
    state["current_agent"] = "⚖️ Judge Agent"
    
    logger = get_logger()
    if logger:
        logger.log_agent_start("judge_agent", state)
    
    # Get current retry count (before incrementing)
    current_retry_count = state.get("judge_retry_count", 0)
    
    # Check if we've already reached max retries
    if current_retry_count >= state.get("max_judge_retries", 2):
        # Already at max retries - provide final feedback and move on
        judge_feedback = f"""I understand this question might be challenging. Let's move forward - we can revisit this topic later if needed. 

Your answer was: "{state["user_answer"]}"

Let me ask you about something else."""
        
        if logger:
            logger.log_agent_end("judge_agent", {
                "action": "max_retries_reached",
                "retry_count": current_retry_count,
                "moving_on": True
            })
        
        # Mark as passed so we can move to next topic
        state["security_passed"] = True
        state["judge_retry_count"] = 0  # Reset for next question
        state["current_question"] = judge_feedback
        state["conversation_history"].append({
            "agent": "judge",
            "feedback": judge_feedback,
            "action": "max_retries_exceeded",
            "retry_count": current_retry_count
        })
        
        # Don't wait for input - let it flow to topic_guide to move on
        state["waiting_for_user_input"] = False
        
        return state
    
    # Increment retry counter (we're giving another chance)
    state["judge_retry_count"] = current_retry_count + 1
    
    model = get_llm()
    
    retry_msg = f" (Attempt {state['judge_retry_count']}/{state.get('max_judge_retries', 2)})" if state["judge_retry_count"] > 1 else ""
    
    prompt = f"""You are a judge providing constructive feedback in an interview.

Original Question: {state["current_question"]}
Employee Answer: {state["user_answer"]}
Issue: {state["security_feedback"]}

Provide friendly, constructive feedback and ask the employee to try again. Be specific about what's missing or unclear. Keep it brief and encouraging.{retry_msg}

Respond with ONLY your feedback message, nothing else."""
    
    if logger:
        logger.log_llm_request("judge_agent", prompt, str(model))
    
    response = model.invoke([HumanMessage(content=prompt)])
    judge_feedback = response.content.strip()
    state = track_tokens(state, response)
    
    if logger:
        logger.log_llm_response(
            "judge_agent",
            judge_feedback,
            state["last_message_tokens"],
            response.response_metadata if hasattr(response, 'response_metadata') else None
        )
    
    # Add to conversation history
    state["conversation_history"].append({
        "agent": "judge",
        "feedback": judge_feedback,
        "retry_count": state["judge_retry_count"],
        "tokens": state["last_message_tokens"]
    })
    
    # Store the feedback as the current message to show user
    state["current_question"] = judge_feedback
    
    # Clear the user answer so we don't re-process it
    state["user_answer"] = ""
    
    # Set flag to wait for user input again
    state["waiting_for_user_input"] = True
    
    if logger:
        logger.log_agent_end("judge_agent", {
            "feedback": judge_feedback,
            "retry_count": state["judge_retry_count"],
            "waiting_for_user_input": True
        })
    
    return state


def topic_guide(state: InterviewState) -> InterviewState:
    """Topic Guide: Evaluates answer depth and completeness"""
    state["current_agent"] = "📊 Topic Guide"
    
    logger = get_logger()
    if logger:
        logger.log_agent_start("topic_guide", state)
    
    state["topic_iteration_count"] += 1
    
    # Check max iterations first
    if state["topic_iteration_count"] >= state["max_iterations_per_topic"]:
        state["topic_depth_sufficient"] = True
        state["topic_feedback"] = "Max iterations reached"
        if logger:
            logger.log_topic_evaluation(True, "Max iterations reached")
            logger.log_agent_end("topic_guide", {"depth_sufficient": True, "reason": "max_iterations"})
        return state
    
    model = get_llm()
    
    example_qs = state["current_topic"].get('example_questions', [])
    examples_text = '\n'.join([f"- {q}" for q in example_qs])
    
    prompt = f"""You are evaluating an employee's answer about their knowledge and experience.

Theme: {state["current_topic"]["theme"]}
Topic: {state["current_topic"]["topic"]}
Example Questions Scope:
{examples_text}

Question Asked: {state["current_question"]}
Employee Answer: {state["user_answer"]}

Evaluate:
1. Does the answer demonstrate practical knowledge and experience?
2. Are relevant aspects of the topic covered?
3. Should we probe deeper with follow-up questions or move to next topic?

Respond ONLY with a JSON object:
{{"depth_sufficient": true/false, "feedback": "brief assessment"}}"""
    
    if logger:
        logger.log_llm_request("topic_guide", prompt, str(model))
    
    response = model.invoke([HumanMessage(content=prompt)])
    state = track_tokens(state, response)
    
    if logger:
        logger.log_llm_response(
            "topic_guide",
            response.content.strip(),
            state["last_message_tokens"],
            response.response_metadata if hasattr(response, 'response_metadata') else None
        )
    
    try:
        # Strip markdown code blocks if present
        response_text = response.content.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()
        
        result = json.loads(response_text)
        state["topic_depth_sufficient"] = result.get("depth_sufficient", False)
        state["topic_feedback"] = result.get("feedback", "")
    except json.JSONDecodeError:
        # Fallback
        state["topic_depth_sufficient"] = len(state["user_answer"]) > 50
        state["topic_feedback"] = "Good coverage"
        if logger:
            logger.log_error("json_parse_error", "Failed to parse topic_guide response", {
                "response": response.content.strip()
            })
    
    if logger:
        logger.log_topic_evaluation(state["topic_depth_sufficient"], state["topic_feedback"])
    
    # Add to conversation history
    state["conversation_history"].append({
        "agent": "topic_guide",
        "evaluation": state["topic_feedback"],
        "depth_sufficient": state["topic_depth_sufficient"],
        "tokens": state["last_message_tokens"]
    })
    
    if logger:
        logger.log_agent_end("topic_guide", {
            "depth_sufficient": state["topic_depth_sufficient"],
            "feedback": state["topic_feedback"]
        })
    
    return state


def probing_agent(state: InterviewState) -> InterviewState:
    """Probing Agent: Generates follow-up questions"""
    state["current_agent"] = "🔍 Probing Agent"
    
    logger = get_logger()
    if logger:
        logger.log_agent_start("probing_agent", state)
    
    # Increment topic iteration count
    state["topic_iteration_count"] = state.get("topic_iteration_count", 0) + 1
    
    model = get_llm()
    
    example_qs = state["current_topic"].get('example_questions', [])
    examples_text = '\n'.join([f"- {q}" for q in example_qs])
    
    prompt = f"""You are conducting a follow-up interview with an experienced employee.

Theme: {state["current_topic"]["theme"]}
Topic: {state["current_topic"]["topic"]}
Example Questions Scope:
{examples_text}

Previous Question: {state["current_question"]}
Employee Answer: {state["user_answer"]}
Assessment: {state["topic_feedback"]}

Generate ONE follow-up question that:
1. Digs deeper into the employee's experience
2. Explores aspects from the example questions not yet covered
3. Asks for specific examples or details

Keep it conversational and relevant to their previous answer.

Respond with ONLY the question, nothing else."""
    
    if logger:
        logger.log_llm_request("probing_agent", prompt, str(model))
    
    response = model.invoke([HumanMessage(content=prompt)])
    state["current_question"] = response.content.strip()
    state = track_tokens(state, response)
    
    if logger:
        logger.log_llm_response(
            "probing_agent",
            state["current_question"],
            state["last_message_tokens"],
            response.response_metadata if hasattr(response, 'response_metadata') else None
        )
    
    # Add to conversation history
    state["conversation_history"].append({
        "agent": "probing_agent",
        "question": state["current_question"],
        "tokens": state["last_message_tokens"]
    })
    
    # Clear the user answer so we don't re-process it
    state["user_answer"] = ""
    
    # Set flag to wait for user input
    state["waiting_for_user_input"] = True
    
    if logger:
        logger.log_agent_end("probing_agent", {
            "question": state["current_question"],
            "waiting_for_user_input": True
        })
    
    return state


def move_to_next_topic(state: InterviewState) -> InterviewState:
    """Helper function to advance to the next topic"""
    state["current_topic_index"] += 1
    
    if state["current_topic_index"] >= len(state["topics"]):
        state["interview_complete"] = True
    
    return state


def human_input_node(state: InterviewState) -> InterviewState:
    """
    Human-in-the-Loop (HITL) node that pauses graph execution for user input.
    
    This node:
    1. Gets called after question-generating agents (topic, judge, probing)
    2. Triggers an interrupt - graph pauses here
    3. Streamlit detects interrupt and waits for user input via chat_input
    4. When user provides input, Streamlit resumes the graph
    5. Graph continues from here to security_agent
    
    The interrupt is the key - it's LangGraph's built-in way to pause and resume.
    """
    # This node doesn't modify state, it just serves as an interrupt point
    # The interrupt happens automatically when this node is marked for interruption
    return state


def check_user_input_needed(state: InterviewState) -> Literal["wait", "continue"]:
    """Check if we need to wait for user input"""
    if state.get("waiting_for_user_input", False):
        return "wait"
    return "continue"


def feedback_agent(state: InterviewState) -> InterviewState:
    """Feedback Agent: Provides comprehensive feedback"""
    state["current_agent"] = "📝 Feedback Agent"
    
    model = get_llm()
    
    # Prepare conversation summary
    conversation_summary = []
    for entry in state["conversation_history"]:
        if "question" in entry:
            conversation_summary.append(f"Q: {entry['question']}")
        if "answer" in entry:
            conversation_summary.append(f"A: {entry['answer']}")
    
    conv_text = '\n'.join(conversation_summary[:20])  # Limit to avoid token overflow
    
    # Group topics by theme
    themes = {}
    for topic in state["topics"]:
        theme = topic.get('theme', 'General')
        if theme not in themes:
            themes[theme] = []
        themes[theme].append(topic['topic'])
    
    themes_text = '\n'.join([f"{theme}: {', '.join(topics)}" for theme, topics in themes.items()])
    
    prompt = f"""You are providing comprehensive feedback on an employee knowledge assessment interview.

Themes and Topics Covered:
{themes_text}

Sample Conversation:
{conv_text}

Provide feedback in markdown format with:
1. Overall Assessment (brief summary)
2. Key Strengths by Theme (2-3 bullet points per theme)
3. Knowledge Gaps or Development Areas (2-3 bullet points)
4. Recommendations (2-3 specific suggestions)

Keep it professional, constructive, and concise."""
    
    response = model.invoke([HumanMessage(content=prompt)])
    state = track_tokens(state, response)
    
    feedback_text = response.content.strip()
    
    # Store feedback as current_question so it can be displayed
    state["current_question"] = feedback_text
    
    # Store feedback in conversation history
    state["conversation_history"].append({
        "agent": "feedback_agent",
        "feedback": feedback_text,
        "tokens": state["last_message_tokens"]
    })
    
    # Ensure interview is marked as complete
    state["interview_complete"] = True
    
    return state


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_after_security(state: InterviewState) -> Literal["judge", "topic_guide"]:
    """Route based on security check results"""
    result = "topic_guide" if state["security_passed"] else "judge"
    
    logger = get_logger()
    if logger:
        logger.log_routing_decision(
            "security_agent",
            result,
            f"Security {'passed' if state['security_passed'] else 'failed'}"
        )
    
    return result


def route_after_judge(state: InterviewState) -> Literal["human_input_node", "topic_guide"]:
    """Route from judge based on whether we should wait for retry or move on"""
    # If waiting_for_user_input is False, judge gave up - go to topic_guide
    # If True, judge wants user to retry - go to HITL (interrupt)
    if state.get("waiting_for_user_input", True):
        return "human_input_node"
    else:
        # Judge gave up, move to topic_guide to continue
        return "topic_guide"


def route_after_topic_guide(state: InterviewState) -> Literal["topic_agent", "probing_agent", "end"]:
    """Route based on topic depth evaluation"""
    logger = get_logger()
    
    if state["topic_iteration_count"] >= state["max_iterations_per_topic"]:
        if state["current_topic_index"] + 1 >= len(state["topics"]):
            if logger:
                logger.log_routing_decision("topic_guide", "end", "Max iterations reached and last topic")
            return "end"
        else:
            if logger:
                logger.log_routing_decision("topic_guide", "topic_agent", "Max iterations reached, moving to next topic")
            return "topic_agent"
    
    if state["topic_depth_sufficient"]:
        if state["current_topic_index"] + 1 >= len(state["topics"]):
            if logger:
                logger.log_routing_decision("topic_guide", "end", "Depth sufficient and last topic")
            return "end"
        else:
            if logger:
                logger.log_routing_decision("topic_guide", "topic_agent", "Depth sufficient, moving to next topic")
            return "topic_agent"
    else:
        if logger:
            logger.log_routing_decision("topic_guide", "probing_agent", "Depth insufficient, asking follow-up")
        return "probing_agent"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_interview_graph():
    """Construct the multi-agent interview workflow graph with HITL interrupts
    
    Graph Flow (with Human-in-the-Loop using interrupts):
    
    START 
      └─> topic_agent (generates first question)
            └─> HITL (interrupt - waits for user)
                  └─> security_agent (validates answer)
                        ├─ Failed → judge_agent (provides feedback)
                        │            └─> HITL (interrupt - waits for retry)
                        │                  └─> security_agent (validates retry)
                        │
                        └─ Passed → topic_guide (evaluates depth)
                                      ├─ Not deep → probing_agent (follow-up)
                                      │              └─> HITL (interrupt)
                                      │                    └─> security_agent
                                      │
                                      ├─ Deep enough → next_topic → topic_agent → HITL
                                      │
                                      └─ All done → feedback_agent → END
    
    Key Points:
    - HITL node is marked with interrupt_before=["human_input_node"]
    - When graph reaches HITL, it pauses (interrupt)
    - Streamlit's chat_input handles user input
    - Streamlit calls graph.stream(..., config) to resume from HITL
    - Graph continues: HITL → security_agent → ...
    - This maintains graph context, no need to restart from START
    """
    
    # Create workflow with checkpointer for interrupt/resume
    workflow = StateGraph(InterviewState)
    
    # Add all agent nodes
    workflow.add_node("topic_agent", topic_agent)
    workflow.add_node("security_agent", security_agent)
    workflow.add_node("judge", judge_agent)
    workflow.add_node("topic_guide", topic_guide)
    workflow.add_node("probing_agent", probing_agent)
    workflow.add_node("next_topic", move_to_next_topic)
    workflow.add_node("human_input_node", human_input_node)  # HITL node
    workflow.add_node("feedback_agent", feedback_agent)
    
    # Start with topic_agent (first question)
    workflow.add_edge(START, "topic_agent")
    
    # Question agents → HITL (interrupt point)
    workflow.add_edge("topic_agent", "human_input_node")
    workflow.add_edge("probing_agent", "human_input_node")
    
    # Judge - conditional: either go to HITL for retry OR move on
    workflow.add_conditional_edges(
        "judge",
        route_after_judge,
        {
            "ask_again": "human_input_node",  # User should retry
            "max_retries": "topic_guide"  # Judge gave up, continue
        }
    )
    
    # HITL → security_agent (after user provides input and graph resumes)
    workflow.add_edge("human_input_node", "security_agent")
    
    # Security validates answer
    workflow.add_conditional_edges(
        "security_agent",
        route_after_security,
        {
            "failed": "judge",  # Failed validation
            "passed": "topic_guide"  # Passed validation
        }
    )
    
    # Topic guide evaluates depth
    workflow.add_conditional_edges(
        "topic_guide",
        route_after_topic_guide,
        {
            "next_topic": "next_topic",  # Move to next topic
            "ask_deeper": "probing_agent",  # Need more depth
            "end": "feedback_agent"  # All topics complete
        }
    )
    
    # Next topic preparation
    workflow.add_edge("next_topic", "topic_agent")
    
    # Feedback agent ends the interview
    workflow.add_edge("feedback_agent", END)
    
    # Compile with checkpointer and interrupt BEFORE human_input_node
    # This makes the graph pause when reaching HITL
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_input_node"]
    )

