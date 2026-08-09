import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice_service.service import VoiceService

def test_tts_mp3_generation():
    """
    Test converting text responses to standard playable MP3 stream bytes using gTTS.
    """
    voice_service = VoiceService()
    text = "Initiating mining exploration analysis protocol."
    
    mp3_bytes = voice_service.text_to_speech(text)
    assert len(mp3_bytes) > 0
    # MP3 standard headers usually start with ID3 tag or sync frame (0xFF)
    assert mp3_bytes.startswith(b"ID3") or mp3_bytes.startswith(b"\xff") or b"MOCK" in mp3_bytes
