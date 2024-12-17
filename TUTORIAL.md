# Building an AI Interview Assistant: Step-by-Step Tutorial

This tutorial will guide you through creating an AI-powered Interview Assistant with voice capabilities using Flask, LangChain, and Eleven Labs.

For complete code examples and implementation details, please refer to this repository.

## Table of Contents
1. [Project Setup](#project-setup)
2. [Building the Backend](#building-the-backend)
3. [Creating the Frontend](#creating-the-frontend)
4. [Adding Voice Capabilities](#adding-voice-capabilities)
5. [Testing and Deployment](#testing-and-deployment)

## Project Setup

### 1. Create Project Structure```bash
mkdir interviewer-agent
cd interviewer-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
Create `requirements.txt`:
```txt
flask==3.0.0
langchain==0.1.0
langchain-openai==0.0.2
langgraph==0.0.10
python-dotenv==1.0.0
pypdf==3.17.1
requests==2.31.0
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables
Create `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key
ELEVEN_LABS_API_KEY=your_eleven_labs_api_key
ELEVEN_LABS_VOICE_ID=your_preferred_voice_id
```

## Building the Backend

### 1. Create Main Application File
Create `main.py` with basic Flask setup:
```python
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
```

### 2. Implement PDF Resume Parser
Add PDF parsing functionality:
```python
from langchain_community.document_loaders import PyPDFLoader

def parse_resume(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load_and_split()
    return "\n".join([page.page_content for page in pages])
```

### 3. Set Up LangChain Components
Configure the language model and prompts:
```python
from langchain_openai import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# Initialize components
memory = MemorySaver()
model = ChatOpenAI(temperature=0.7, model="gpt-4")

# Define prompts
INITIAL_ANALYSIS_PROMPT = """..."""  # Your prompt here
INTERVIEW_PROMPT = """..."""  # Your prompt here
FEEDBACK_PROMPT = """..."""  # Your prompt here
```

### 4. Implement API Endpoints
Create routes for file upload, interview, and feedback:
```python
@app.route('/api/upload', methods=['POST'])
def upload_resume():
    # Implementation here

@app.route('/api/interview', methods=['POST'])
def conduct_interview():
    # Implementation here

@app.route('/api/feedback', methods=['POST'])
def generate_feedback():
    # Implementation here
```

## Creating the Frontend

### 1. Set Up HTML Template
Create `templates/index.html` with basic structure:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Interview Assistant</title>
    <!-- Add required scripts -->
</head>
<body>
    <!-- Template structure -->
</body>
</html>
```

### 2. Add TailwindCSS and Vue.js
Include necessary CDN links:
```html
<head>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
```

### 3. Implement Vue.js Application
Create the main Vue application with required components:
```javascript
const app = createApp({
    data() {
        return {
            // Data properties
        }
    },
    methods: {
        // Application methods
    }
}).mount('#app')
```

## Adding Voice Capabilities

### 1. Implement Text-to-Speech
Add Eleven Labs integration:
```python
def text_to_speech(text):
    if not ELEVEN_LABS_API_KEY:
        return None
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}"
    # Implementation here
```

### 2. Add Speech Recognition
Implement browser's Web Speech API:
```javascript
initializeSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    // Configuration here
}
```

### 3. Handle Continuous Conversation
Implement turn-taking and audio playback:
```javascript
async startContinuousListening() {
    // Implementation here
}

async playAudio(audioData) {
    // Implementation here
}
```

## Testing and Deployment

### 1. Local Testing
Run the application:
```bash
python main.py
```

Access at `http://localhost:5001`

### 2. Testing Checklist
Test each feature thoroughly:

1. Resume Upload:
```python
def test_resume_upload():
    # Test with valid PDF
    with open('test_resume.pdf', 'rb') as f:
        response = client.post('/api/upload', 
            data={'resume': f, 'job_title': 'Software Engineer'})
        assert response.status_code == 200
        assert 'session_id' in response.json
    
    # Test without resume
    response = client.post('/api/upload', 
        data={'job_title': 'Software Engineer'})
    assert response.status_code == 400
```

2. Voice Recognition:
```javascript
// Browser console test
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => console.log('Microphone access granted'))
    .catch(err => console.error('Microphone access denied:', err));
```

3. Text-to-Speech:
```python
def test_tts():
    result = text_to_speech("Hello, this is a test.")
    assert result and result.startswith('data:audio/mpeg;base64,')
```

4. Interview Flow:
```python
def test_interview_flow():
    # Test interview response
    response = client.post('/api/interview', json={
        'session_id': 'test_session',
        'message': 'Tell me about your experience with Python.'
    })
    assert response.status_code == 200
    assert 'response' in response.json
    assert 'audio' in response.json
```

5. Feedback Generation:
```python
def test_feedback():
    response = client.post('/api/feedback', 
        json={'session_id': 'test_session'})
    assert response.status_code == 200
    assert 'feedback' in response.json
```

### 3. Common Issues and Solutions

1. **Speech Recognition Issues**
```javascript
// Add error handling for speech recognition
this.recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    switch (event.error) {
        case 'not-allowed':
            alert('Please enable microphone access');
            break;
        case 'no-speech':
            console.log('No speech detected');
            break;
        // Handle other cases
    }
};
```

2. **Audio Playback Issues**
```javascript
// Add comprehensive audio error handling
async playAudio(audioData) {
    if (!audioData) {
        console.error('No audio data received');
        return;
    }
    
    try {
        const audio = new Audio(audioData);
        await audio.play();
    } catch (error) {
        console.error('Audio playback error:', error);
        // Fallback to browser's TTS if available
        const utterance = new SpeechSynthesisUtterance(this.lastResponse);
        window.speechSynthesis.speak(utterance);
    }
}
```

3. **PDF Parsing Issues**
```python
def safe_parse_resume(file_path):
    try:
        loader = PyPDFLoader(file_path)
        pages = loader.load_and_split()
        if not pages:
            raise ValueError("No text content found in PDF")
        return "\n".join([page.page_content for page in pages])
    except Exception as e:
        print(f"Error parsing PDF: {str(e)}")
        raise ValueError("Unable to parse resume. Please ensure it's a text-based PDF.")
```

## Best Practices

### 1. Error Handling
Implement comprehensive error handling:
```python
class InterviewError(Exception):
    """Custom error for interview-related issues"""
    pass

def handle_interview_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InterviewError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred'}), 500
    return wrapper

@app.route('/api/interview', methods=['POST'])
@handle_interview_error
def conduct_interview():
    # Implementation with proper error handling
```

### 2. Security Measures
Implement security best practices:
```python
# File upload security
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_file_save(file):
    if not allowed_file(file.filename):
        raise ValueError("Invalid file type")
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = f"{timestamp}_{filename}"
    
    return safe_filename

# Input sanitization
def sanitize_input(text):
    return bleach.clean(text)
```

### 3. Performance Optimization
Implement performance improvements:
```python
# Caching
from functools import lru_cache

@lru_cache(maxsize=100)
def get_voice_synthesis(text):
    return text_to_speech(text)

# Clean up temporary files
def cleanup_temp_files():
    temp_dir = 'temp'
    current_time = time.time()
    for f in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, f)
        if os.path.getmtime(filepath) < current_time - 3600:  # 1 hour old
            os.remove(filepath)

# Session management
from flask_session import Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
```

## Deployment

### 1. Production Configuration
Create `config.py`:
```python
class Config:
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SESSION_TYPE = 'filesystem'
    UPLOAD_FOLDER = 'temp'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class ProductionConfig(Config):
    pass

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
```

### 2. WSGI Configuration
Create `wsgi.py`:
```python
from main import app
from config import ProductionConfig

app.config.from_object(ProductionConfig)

if __name__ == '__main__':
    app.run()
```

### 3. Gunicorn Configuration
Create `gunicorn_config.py`:
```python
bind = "0.0.0.0:5001"
workers = 4
threads = 2
timeout = 120
keepalive = 5
worker_class = "gthread"
```

### 4. Docker Support
Create `Dockerfile`:
```dockerfile
FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production

CMD ["gunicorn", "--config", "gunicorn_config.py", "wsgi:app"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5001:5001"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ELEVEN_LABS_API_KEY=${ELEVEN_LABS_API_KEY}
    volumes:
      - ./temp:/app/temp
```

## Resources and Further Reading

1. **API Documentation**
   - [OpenAI API](https://platform.openai.com/docs/api-reference)
   - [Eleven Labs API](https://docs.elevenlabs.io/api-reference)
   - [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)

2. **Security Resources**
   - [Flask Security](https://flask-security.readthedocs.io/)
   - [OWASP Top 10](https://owasp.org/www-project-top-ten/)

3. **Performance Optimization**
   - [Flask Caching](https://flask-caching.readthedocs.io/)
   - [Gunicorn Configuration](https://docs.gunicorn.org/en/latest/configure.html)

4. **Testing Resources**
   - [Flask Testing](https://flask.palletsprojects.com/en/2.0.x/testing/)
   - [pytest](https://docs.pytest.org/) 
