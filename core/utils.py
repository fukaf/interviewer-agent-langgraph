"""
Utility functions for the interview system
"""
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
import pandas as pd
import os
from dotenv import load_dotenv
from interview_logging.interview_logger import get_logger

load_dotenv()


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


def load_topics_from_csv(csv_path: str) -> list[dict]:
    """Load interview topics from CSV file
    
    Args:
        csv_path: Path to the CSV file containing topics
        
    Returns:
        List of topic dictionaries with keys: theme, topic, example_questions
    """
    try:
        df = pd.read_csv(csv_path)
        topics = df.to_dict('records')
        
        # Parse semicolon-separated example questions
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
