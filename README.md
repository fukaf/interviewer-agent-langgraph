# AI Interview Assistant

An intelligent interview assistant that conducts voice-enabled technical interviews, providing real-time conversation and comprehensive feedback.

## Features

### Core Functionality
- PDF resume parsing and analysis
- Interactive voice-based interviews
- Real-time speech recognition
- Natural voice responses using Eleven Labs
- Comprehensive feedback generation
- Markdown-formatted reports

### Technical Features
- Voice input using Web Speech API
- Text-to-Speech with Eleven Labs
- Real-time transcription
- Continuous conversation flow
- Session management
- PDF parsing and analysis

### User Interface
- Modern, responsive design with TailwindCSS
- Real-time chat interface
- Voice recording controls
- Loading states and animations
- Markdown rendering for feedback
- Progress indicators

## Prerequisites

- Python 3.8+
- OpenAI API key (GPT-4 access required)
- Eleven Labs API key
- Modern web browser with microphone support
- PDF reader for resume uploads

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd interviewer-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
ELEVEN_LABS_API_KEY=your_eleven_labs_api_key_here
ELEVEN_LABS_VOICE_ID=your_preferred_voice_id_here
```

5. Create required directories:
```bash
mkdir templates temp
```

## Usage

1. Start the Flask server:
```bash
python main.py
```

2. Open your browser and navigate to:
```
http://localhost:5001
```

3. Upload a resume (PDF format)
4. Enter the job title
5. Start the interview
6. Speak or type your responses
7. Get comprehensive feedback

## Interview Flow

1. **Resume Analysis**
   - Upload resume
   - System analyzes skills and experience
   - Prepares personalized questions

2. **Interactive Interview**
   - Voice-based conversation
   - Real-time transcription
   - Natural follow-up questions
   - Continuous turn-taking

3. **Feedback Generation**
   - Overall assessment
   - Key strengths
   - Areas for improvement
   - Technical skills evaluation
   - Actionable recommendations

## Voice Features

### Speech Recognition
- Real-time transcription
- Automatic silence detection
- Continuous listening mode
- Push-to-talk option

### Text-to-Speech
- Natural voice synthesis
- Automatic playback
- Queue management
- Error handling

## Project Structure

```
interviewer-agent/
├── main.py              # Main application file
├── requirements.txt     # Python dependencies
├── .env                # Environment variables
├── README.md           # Project documentation
├── TUTORIAL.md         # Step-by-step tutorial
├── templates/          # HTML templates
│   └── index.html      # Main interface
└── temp/              # Temporary file storage
```

## Configuration

### Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key
- `ELEVEN_LABS_API_KEY`: Your Eleven Labs API key
- `ELEVEN_LABS_VOICE_ID`: Voice ID for synthesis

### Application Settings
- Port: 5001 (configurable)
- Temp directory: ./temp
- Supported formats: PDF

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for GPT-4
- Eleven Labs for voice synthesis
- LangChain community
- Flask framework
- Vue.js and TailwindCSS

## Support

For support, please:
1. Check the TUTORIAL.md for detailed guidance
2. Review common issues in documentation
3. Open an issue for bugs or suggestions

## Roadmap

- [ ] Add user authentication
- [ ] Implement interview recording
- [ ] Add industry-specific templates
- [ ] Create interview scoring system
- [ ] Add database persistence
- [ ] Implement caching
- [ ] Add load balancing