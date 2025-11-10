"""
Voice input module for Streamlit interview app
Provides continuous speech recognition functionality using Azure Speech SDK
"""
import azure.cognitiveservices.speech as speechsdk
import threading
import time
import datetime
import os
from typing import Optional, Callable
from dotenv import load_dotenv

load_dotenv()

# Azure Speech configuration
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
SPEECH_LANGUAGE = os.getenv("SPEECH_LANGUAGE", "ja-JP")


class VoiceRecorder:
    """
    Manages continuous voice recording and transcription for Streamlit app.
    Thread-safe implementation that updates session state via callbacks.
    """
    
    def __init__(self):
        self.recognizer: Optional[speechsdk.SpeechRecognizer] = None
        self.is_recording = False
        self.all_results = []
        self.current_text = ""
        self._lock = threading.Lock()
        self.duration = 0.0
        
        # Callbacks for Streamlit integration
        self.on_recognizing: Optional[Callable[[str], None]] = None
        self.on_recognized: Optional[Callable[[str], None]] = None
        self.on_session_started: Optional[Callable[[], None]] = None
        self.on_session_stopped: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def start_recording(self) -> bool:
        """
        Start continuous speech recognition from microphone.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not SPEECH_KEY:
            if self.on_error:
                self.on_error("Azure Speech Key not configured")
            return False
        
        if self.is_recording:
            return True
        
        try:
            # Configure speech recognition
            speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
            speech_config.speech_recognition_language = SPEECH_LANGUAGE
            
            # Use default microphone
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            self.recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            
            # Reset state
            with self._lock:
                self.all_results = []
                self.current_text = ""
                self.is_recording = True
            
            # Connect event handlers
            self.recognizer.recognizing.connect(self._on_recognizing)
            self.recognizer.recognized.connect(self._on_recognized)
            self.recognizer.session_started.connect(self._on_session_started)
            self.recognizer.session_stopped.connect(self._on_session_stopped)
            self.recognizer.canceled.connect(self._on_canceled)
            
            # Start continuous recognition in background
            self.recognizer.start_continuous_recognition_async()
            
            if self.on_session_started:
                self.on_session_started()
            
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to start recording: {str(e)}")
            return False
    
    def stop_recording(self) -> str:
        """
        Stop continuous speech recognition and return final transcription.
        
        Returns:
            str: Complete transcribed text
        """
        if not self.is_recording or not self.recognizer:
            return self.get_final_text()
        
        try:
            # Stop recognition
            self.recognizer.stop_continuous_recognition_async()
            
            with self._lock:
                self.is_recording = False
            
            # Wait a bit for final events to process
            time.sleep(0.5)
            
            if self.on_session_stopped:
                self.on_session_stopped()
            
            return self.get_final_text()
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Error stopping recording: {str(e)}")
            return self.get_final_text()
    
    def get_final_text(self) -> str:
        """Get the complete transcribed text"""
        with self._lock:
            return " ".join(self.all_results).strip()
    
    def get_current_text(self) -> str:
        """Get the current intermediate text (while speaking)"""
        with self._lock:
            if self.current_text:
                base_text = " ".join(self.all_results)
                return f"{base_text} {self.current_text}".strip()
            return " ".join(self.all_results).strip()
            
    
    # Event handlers (called by Azure SDK)
    
    def _on_recognizing(self, evt):
        """Handle intermediate recognition results (while speaking)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            with self._lock:
                self.current_text = evt.result.text
                if self.current_text:
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open("transcription_log.txt", "a", encoding="utf-8") as f:
                        f.write(f"[{timestamp}] {self.current_text}\n")
            
            if self.on_recognizing:
                self.on_recognizing(self.get_current_text())
    
    def _on_recognized(self, evt):
        """Handle final recognition results (sentence complete)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            with self._lock:
                self.all_results.append(evt.result.text)
                self.current_text = ""
                self.duration = evt.result.duration
            
            if self.on_recognized:
                self.on_recognized(self.get_final_text())
        
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            # Speech could not be recognized - ignore
            pass
    
    def _on_session_started(self, evt):
        """Handle session start"""
        pass
    
    def _on_session_stopped(self, evt):
        """Handle session stop"""
        with self._lock:
            self.is_recording = False
    
    def _on_canceled(self, evt):
        """Handle cancellation/errors"""
        with self._lock:
            self.is_recording = False
        
        if evt.reason == speechsdk.CancellationReason.Error:
            error_msg = f"Recognition error: {evt.error_details}"
            if self.on_error:
                self.on_error(error_msg)


# Singleton instance for Streamlit app
_recorder_instance: Optional[VoiceRecorder] = None


def get_voice_recorder() -> VoiceRecorder:
    """Get or create the global voice recorder instance"""
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = VoiceRecorder()
    return _recorder_instance


def reset_voice_recorder():
    """Reset the voice recorder (useful for cleanup)"""
    global _recorder_instance
    if _recorder_instance and _recorder_instance.is_recording:
        _recorder_instance.stop_recording()
    _recorder_instance = None
