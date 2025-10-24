# AI Interview Agent - Streamlit Version

A streamlined version of the AI Interview Agent using Streamlit for the UI, focusing on core interview functionality.

## Features

- **Interactive Interview**: Conduct technical interviews with an AI interviewer
- **Job-Specific Questions**: Enter any job title to get relevant interview questions
- **Natural Conversation**: The AI asks follow-up questions based on your responses
- **Detailed Feedback**: Get comprehensive feedback at the end of the interview

## Setup

1. **Install Dependencies**:
```powershell
pip install -r requirements.txt
```

2. **Configure Environment**:
Create a `.env` file in the project root with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

3. **Run the Application**:
```powershell
streamlit run streamlit_app.py
```

The application will open in your default web browser at `http://localhost:8501`

## How to Use

1. **Start Interview**:
   - Enter the job title in the sidebar (e.g., "Senior Software Engineer", "Data Scientist")
   - Click "Start Interview"

2. **Answer Questions**:
   - Type your responses in the chat input
   - The AI will ask follow-up questions based on your answers
   - Be specific and provide examples from your experience

3. **Get Feedback**:
   - Click "End Interview & Get Feedback" when you're ready
   - Review the detailed feedback including strengths, areas for improvement, and recommendations

4. **Start New Interview**:
   - Click "Reset Interview" or "Start New Interview" to begin again

## Features Removed from Original

- Resume upload and analysis
- Audio/Text-to-speech functionality (ElevenLabs integration)
- Flask web server and HTML templates

## Core Functions

The app uses three main functions from the original codebase:

- `start_interview(job_title, session_id)`: Initiates the interview
- `conduct_interview(session_id, user_response)`: Continues the conversation
- `generate_feedback(session_id)`: Provides final assessment

## Tips for Best Results

- Provide detailed answers with specific examples
- Don't rush - take time to think through your responses
- Ask for clarification if needed
- Be honest about your experience and skills
