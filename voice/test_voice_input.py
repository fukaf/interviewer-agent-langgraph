"""
Simple test script for voice_input module
"""
from voice.voice_input import VoiceRecorder
import time

def test_voice_recorder():
    """Test the VoiceRecorder class"""
    print("Testing VoiceRecorder...")
    print("This will record for 10 seconds. Speak into your microphone.\n")
    
    recorder = VoiceRecorder()
    
    # Set up callbacks
    def on_recognizing(text):
        print(f"\r[LIVE] {text}", end='', flush=True)
    
    def on_recognized(text):
        print(f"\n[FINAL] {text}")
    
    def on_error(error):
        print(f"\n[ERROR] {error}")
    
    recorder.on_recognizing = on_recognizing
    recorder.on_recognized = on_recognized
    recorder.on_error = on_error
    
    # Start recording
    if recorder.start_recording():
        print("Recording started. Speak now...")
        
        # Record for 10 seconds
        for i in range(10, 0, -1):
            print(f"\nTime remaining: {i}s", end='')
            time.sleep(1)
        
        # Stop recording
        print("\n\nStopping recording...")
        final_text = recorder.stop_recording()
        
        print("\n" + "="*60)
        print("FINAL TRANSCRIPTION:")
        print("="*60)
        print(final_text)
        print("="*60)
    else:
        print("Failed to start recording. Check your Azure credentials.")

if __name__ == "__main__":
    test_voice_recorder()
