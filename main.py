from datetime import datetime
from flask import Flask, render_template, request, jsonify
from langchain.schema.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.document_loaders import PyPDFLoader
from langchain.tools import Tool
import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

ELEVEN_LABS_API_KEY = os.getenv('ELEVEN_LABS_API_KEY')
ELEVEN_LABS_VOICE_ID = os.getenv('ELEVEN_LABS_VOICE_ID', '29vD33N1CtxCmqQRPOHJ')  # Default to Indian male voice (Arun)

app = Flask(__name__)
app.jinja_env.variable_start_string = '{[{'
app.jinja_env.variable_end_string = '}]}'

# Initialize memory and OpenAI model
memory = MemorySaver()
model = ChatOpenAI(temperature=0.7, model="gpt-4")

# Function to convert text to speech using Eleven Labs
def text_to_speech(text):
    if not ELEVEN_LABS_API_KEY:
        return None
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_LABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            # Convert audio data to base64 for sending to frontend
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:audio/mpeg;base64,{audio_base64}"
    except Exception as e:
        print(f"Error in text_to_speech: {str(e)}")
        return None
    
    return None

# Define interview system prompts
INITIAL_ANALYSIS_PROMPT = """You are an expert technical interviewer. Analyze the candidate's resume and job requirements silently. 
DO NOT share your analysis with the candidate. Instead, start directly with a warm, professional greeting and your first question.
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

class ResumeAnalysisTool(Tool):
    def __init__(self):
        super().__init__(
            name="resume_analyzer",
            func=self.analyze_resume,
            description="Analyzes a candidate's resume for relevant skills and experience"
        )
    
    def analyze_resume(self, file_path):
        loader = PyPDFLoader(file_path)
        pages = loader.load_and_split()
        return "\n".join([page.page_content for page in pages])



agent_executor = create_react_agent(
    model,
    tools=[],
    checkpointer=memory
)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_title = request.form.get('job_title')
    
    if not job_title:
        return jsonify({'error': 'No job title provided'}), 400
    
    # Save resume temporarily
    resume_path = f"temp/{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    resume_file.save(resume_path)

    resume_content = ResumeAnalysisTool().analyze_resume(resume_path)
    
    try:
        # Initial analysis and first question
        config = {"configurable": {"thread_id": "interview_session"}}
        
        analysis_response = agent_executor.invoke({
            "messages": [
                SystemMessage(content=INITIAL_ANALYSIS_PROMPT),
                HumanMessage(content=f"Resume content: {resume_content}"),
                HumanMessage(content=f"Start the interview for the position of {job_title}")
            ]
        }, config=config)
        
        response_text = analysis_response["messages"][-1].content
        
        # Generate audio for initial greeting
        audio_data = text_to_speech(response_text)
        
        return jsonify({
            'status': 'success',
            'session_id': config["configurable"]["thread_id"],
            'initial_analysis': response_text,
            'audio': audio_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/interview', methods=['POST'])
def conduct_interview():
    session_id = request.json.get('session_id')
    user_response = request.json.get('message')
    
    if not session_id or not user_response:
        return jsonify({'error': 'Missing session_id or message'}), 400
    
    try:
        config = {"configurable": {"thread_id": session_id}}
        
        interview_response = agent_executor.invoke({
            "messages": [
                SystemMessage(content=INTERVIEW_PROMPT),
                HumanMessage(content=user_response)
            ]
        }, config=config)
        
        response_text = interview_response["messages"][-1].content
        
        # Generate audio response
        audio_data = text_to_speech(response_text)
        
        return jsonify({
            'response': response_text,
            'session_id': session_id,
            'audio': audio_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def generate_feedback():
    session_id = request.json.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'No session_id provided'}), 400
    
    try:
        config = {"configurable": {"thread_id": session_id}}
        
        feedback_response = agent_executor.invoke({
            "messages": [
                SystemMessage(content=FEEDBACK_PROMPT),
                HumanMessage(content="Generate final feedback for the candidate")
            ]
        }, config=config)
        
        return jsonify({
            'feedback': feedback_response["messages"][-1].content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('temp', exist_ok=True)
    app.run(debug=True, port=5001)
