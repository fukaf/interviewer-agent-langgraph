"""
Test continuous speech recognition with Azure Speech SDK
This demonstrates how to use continuous recognition instead of single-shot recognition.
"""
import azure.cognitiveservices.speech as speechsdk
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure Speech configuration
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
SPEECH_LANGUAGE = os.getenv("SPEECH_LANGUAGE")


def test_continuous_recognition_from_mic():
    """
    Test continuous speech recognition from microphone.
    Recognizes speech continuously until user says 'stop' or presses Ctrl+C.
    """
    print("=== Testing Continuous Recognition from Microphone ===")
    print("Speak into your microphone. Say 'stop' or press Ctrl+C to end.\n")
    
    # Configure speech recognition
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language = SPEECH_LANGUAGE
    
    # Use default microphone
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    # Variable to manage recognition state
    done = False
    all_results = []
    
    # Callback to stop continuous recognition
    def stop_cb(evt):
        """Callback that stops continuous recognition upon receiving event"""
        print(f'\n[CLOSING] {evt}')
        speech_recognizer.stop_continuous_recognition()
        nonlocal done
        done = True
    
    # Event handlers for different recognition events
    def recognizing_cb(evt):
        """Called during recognition (intermediate results)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            print(f'[RECOGNIZING] {evt.result.text}', end='\r')
    
    def recognized_cb(evt):
        """Called when recognition is complete (final result)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f'\n[RECOGNIZED] {evt.result.text}')
            all_results.append(evt.result.text)
            
            # Stop if user says 'stop' or '停止' (Japanese)
            if evt.result.text.lower() in ['stop', 'stop.', '停止', '停止。', 'ストップ', 'ストップ。']:
                print("\n[INFO] Stop command detected. Ending recognition...")
                speech_recognizer.stop_continuous_recognition()
                nonlocal done
                done = True
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print(f'\n[NO MATCH] Speech could not be recognized: {evt.result.no_match_details}')
    
    def session_started_cb(evt):
        """Called when recognition session starts"""
        print(f'[SESSION STARTED] {evt}\n')
    
    def session_stopped_cb(evt):
        """Called when recognition session stops"""
        print(f'\n[SESSION STOPPED] {evt}')
    
    def canceled_cb(evt):
        """Called when recognition is canceled"""
        print(f'\n[CANCELED] {evt}')
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f'[ERROR] ErrorDetails: {evt.error_details}')
    
    # Connect callbacks to events
    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(session_started_cb)
    speech_recognizer.session_stopped.connect(session_stopped_cb)
    speech_recognizer.canceled.connect(canceled_cb)
    
    # Connect stop callbacks
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)
    
    # Start continuous recognition
    speech_recognizer.start_continuous_recognition()
    
    # Keep running until done
    try:
        while not done:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user. Stopping recognition...")
        speech_recognizer.stop_continuous_recognition()
        done = True
    
    # Print summary
    print("\n" + "="*60)
    print(f"Recognition complete. Captured {len(all_results)} utterances:")
    print("="*60)
    for i, result in enumerate(all_results, 1):
        print(f"{i}. {result}")
    print("="*60)
    
    return all_results


def test_continuous_recognition_from_file(audio_file: str):
    """
    Test continuous speech recognition from audio file.
    
    Args:
        audio_file: Path to audio file (WAV format recommended)
    """
    print(f"=== Testing Continuous Recognition from File ===")
    print(f"Processing audio file: {audio_file}\n")
    
    if not os.path.exists(audio_file):
        print(f"[ERROR] Audio file not found: {audio_file}")
        return []
    
    # Configure speech recognition
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language = SPEECH_LANGUAGE
    
    # Configure audio input from file
    audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    # Variable to manage recognition state
    done = False
    all_results = []
    
    # Callback to stop continuous recognition
    def stop_cb(evt):
        """Callback that stops continuous recognition upon receiving event"""
        print(f'\n[CLOSING] {evt}')
        speech_recognizer.stop_continuous_recognition()
        nonlocal done
        done = True
    
    # Event handlers
    def recognizing_cb(evt):
        """Called during recognition (intermediate results)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            print(f'[RECOGNIZING] {evt.result.text}')
    
    def recognized_cb(evt):
        """Called when recognition is complete (final result)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f'[RECOGNIZED] {evt.result.text}')
            all_results.append(evt.result.text)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print(f'[NO MATCH] Speech could not be recognized')
    
    def session_started_cb(evt):
        """Called when recognition session starts"""
        print(f'[SESSION STARTED] {evt}\n')
    
    def session_stopped_cb(evt):
        """Called when recognition session stops"""
        print(f'\n[SESSION STOPPED] {evt}')
    
    def canceled_cb(evt):
        """Called when recognition is canceled"""
        print(f'\n[CANCELED] {evt}')
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f'[ERROR] ErrorDetails: {evt.error_details}')
    
    # Connect callbacks to events
    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(session_started_cb)
    speech_recognizer.session_stopped.connect(session_stopped_cb)
    speech_recognizer.canceled.connect(canceled_cb)
    
    # Connect stop callbacks
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)
    
    # Start continuous recognition
    speech_recognizer.start_continuous_recognition()
    
    # Keep running until done
    while not done:
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "="*60)
    print(f"Recognition complete. Captured {len(all_results)} utterances:")
    print("="*60)
    for i, result in enumerate(all_results, 1):
        print(f"{i}. {result}")
    print("="*60)
    
    return all_results


def test_continuous_recognition_with_timeout(timeout_seconds: int = 30):
    """
    Test continuous speech recognition with a timeout.
    
    Args:
        timeout_seconds: Maximum duration for recognition in seconds
    """
    print(f"=== Testing Continuous Recognition with {timeout_seconds}s Timeout ===")
    print("Speak into your microphone.\n")
    
    # Configure speech recognition
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language = SPEECH_LANGUAGE
    
    # Use default microphone
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    # Variable to manage recognition state
    done = False
    all_results = []
    start_time = time.time()
    
    # Callback to stop continuous recognition
    def stop_cb(evt):
        """Callback that stops continuous recognition upon receiving event"""
        print(f'\n[CLOSING] {evt}')
        speech_recognizer.stop_continuous_recognition()
        nonlocal done
        done = True
    
    # Event handlers
    def recognized_cb(evt):
        """Called when recognition is complete (final result)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f'[RECOGNIZED] {evt.result.text}')
            all_results.append(evt.result.text)
    
    # Connect callbacks
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)
    
    # Start continuous recognition
    speech_recognizer.start_continuous_recognition()
    
    # Keep running until done or timeout
    try:
        while not done:
            time.sleep(0.5)
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed >= timeout_seconds:
                print(f"\n[INFO] Timeout reached ({timeout_seconds}s). Stopping recognition...")
                speech_recognizer.stop_continuous_recognition()
                break
            
            # Show remaining time
            remaining = timeout_seconds - elapsed
            print(f"[TIME] {remaining:.1f}s remaining...", end='\r')
    
    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user. Stopping recognition...")
        speech_recognizer.stop_continuous_recognition()
    
    # Wait a bit for cleanup
    time.sleep(1)
    
    # Print summary
    print("\n" + "="*60)
    print(f"Recognition complete. Captured {len(all_results)} utterances:")
    print("="*60)
    for i, result in enumerate(all_results, 1):
        print(f"{i}. {result}")
    print("="*60)
    
    return all_results


if __name__ == "__main__":
    import sys
    
    print("Azure Speech SDK - Continuous Recognition Test\n")
    
    # Check if credentials are set
    if not SPEECH_KEY:
        print("[ERROR] AZURE_SPEECH_KEY not found in environment variables.")
        print("Please set it in your .env file or environment.")
        sys.exit(1)
    
    print("Select test mode:")
    print("1. Continuous recognition from microphone")
    print("2. Continuous recognition from audio file")
    print("3. Continuous recognition with 30s timeout")
    print("4. Run all tests")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        test_continuous_recognition_from_mic()
    
    elif choice == "2":
        audio_file = input("Enter path to audio file (WAV format): ").strip()
        test_continuous_recognition_from_file(audio_file)
    
    elif choice == "3":
        test_continuous_recognition_with_timeout(timeout_seconds=30)
    
    elif choice == "4":
        print("\n" + "="*60)
        print("Running all tests...")
        print("="*60 + "\n")
        
        # Test 1: Microphone (10s timeout for demo)
        print("\n[TEST 1/2] Microphone with 10s timeout")
        test_continuous_recognition_with_timeout(timeout_seconds=10)
        
        # Test 2: Ask for audio file (optional)
        print("\n[TEST 2/2] Audio file (optional)")
        audio_file = input("Enter path to audio file (or press Enter to skip): ").strip()
        if audio_file and os.path.exists(audio_file):
            test_continuous_recognition_from_file(audio_file)
        else:
            print("Skipping audio file test.")
        
        print("\n" + "="*60)
        print("All tests complete!")
        print("="*60)
    
    else:
        print("[ERROR] Invalid choice. Please run again and select 1-4.")
