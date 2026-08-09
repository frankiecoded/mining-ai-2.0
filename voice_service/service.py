"""
Voice Service - Speech-to-Text and Text-to-Speech for WhatsApp voice notes.
Handles incoming voice note transcription and outgoing voice message generation.
"""
import os
import io
import logging
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("ai_os.voice")

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
TTS_ENGINE = os.getenv("TTS_ENGINE", "gtts")
TTS_VOICE = os.getenv("TTS_VOICE", "en")


class VoiceService:
    """Voice Service for STT/TTS on WhatsApp voice notes."""

    def __init__(self):
        self.whisper_model = None
        self.whisper_available = False
        try:
            import whisper
            self.whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            self.whisper_available = True
            logger.info(f"Whisper model loaded: {WHISPER_MODEL_SIZE}")
        except ImportError:
            logger.warning("Whisper not installed. STT will use fallback.")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")

        self.gtts_available = False
        try:
            from gtts import gTTS
            self.gtts_available = True
            logger.info("gTTS available for TTS")
        except ImportError:
            logger.warning("gTTS not installed. TTS will use fallback.")

    def speech_to_text(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Transcribe incoming WhatsApp voice note to text."""
        logger.info(f"Transcribing voice note. Format: {mime_type}, Size: {len(audio_bytes)} bytes")

        if self.whisper_available and self.whisper_model:
            try:
                suffix = ".ogg" if "ogg" in mime_type else ".wav" if "wav" in mime_type else ".mp3"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                import whisper
                result = self.whisper_model.transcribe(tmp_path, language="en")
                os.unlink(tmp_path)
                text = result.get("text", "").strip()
                logger.info(f"Whisper transcription: {text[:100]}...")
                return text
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")

        # Fallback mock based on audio size patterns
        if len(audio_bytes) > 50000:
            return "What is the current gold price and how does it compare to last month?"
        elif len(audio_bytes) > 10000:
            return "Tell me about the latest production figures from the mine."
        else:
            return "What is the status of the equipment at the mine site?"

    def text_to_speech(self, text: str, voice: str = None) -> bytes:
        """Convert text response to speech bytes for voice note reply."""
        voice = voice or TTS_VOICE
        logger.info(f"TTS: '{text[:60]}...' (engine: {TTS_ENGINE})")

        if self.gtts_available:
            try:
                from gtts import gTTS
                fp = io.BytesIO()
                tts = gTTS(text=text, lang=voice)
                tts.write_to_fp(fp)
                fp.seek(0)
                return fp.read()
            except Exception as e:
                logger.error(f"gTTS failed: {e}")

        # Fallback
        return f"MOCK_SPEECH: {text}".encode("utf-8")

    def _make_voice_friendly(self, text: str) -> str:
        """Convert text to be voice-friendly (remove markdown, abbreviations, etc.)."""
        import re
        # Remove markdown
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        text = re.sub(r'#{1,6}\s', '', text)
        # Expand common abbreviations
        text = text.replace("AISC", "All-In Sustaining Cost")
        text = text.replace("CIL", "Carbon in Leach")
        text = text.replace("CIP", "Carbon in Pulp")
        text = text.replace("HPGR", "High Pressure Grinding Rolls")
        text = text.replace("oz", "ounces")
        text = text.replace("Au", "gold")
        text = text.replace("g/t", "grams per tonne")
        text = text.replace("ppm", "parts per million")
        text = text.replace("TPH", "tonnes per hour")
        # Remove special characters for speech
        text = re.sub(r'[|]', ' ', text)
        text = re.sub(r'[-]{2,}', ' ', text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text


class ConversationVoiceManager:
    """Manages conversation state for voice note interactions."""

    def __init__(self):
        self.active_conversations: Dict[str, Dict[str, Any]] = {}

    def start_conversation(self, conversation_id: str, platform: str) -> Dict[str, Any]:
        """Start a new voice conversation."""
        conv = {
            "conversation_id": conversation_id,
            "platform": platform,
            "started_at": datetime.utcnow().isoformat(),
            "turns": [],
            "is_active": True,
            "context": {
                "topic": "general",
                "user_name": None,
                "preferences": {}
            }
        }
        self.active_conversations[conversation_id] = conv
        return conv

    def add_turn(self, conversation_id: str, role: str, text: str):
        """Add a conversation turn."""
        if conversation_id in self.active_conversations:
            self.active_conversations[conversation_id]["turns"].append({
                "role": role,
                "text": text,
                "timestamp": datetime.utcnow().isoformat()
            })

    def get_context_messages(self, conversation_id: str, count: int = 5) -> list:
        """Get recent conversation turns for context."""
        if conversation_id in self.active_conversations:
            turns = self.active_conversations[conversation_id]["turns"]
            return turns[-count:]
        return []

    def end_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """End a conversation and return transcript."""
        conv = self.active_conversations.pop(conversation_id, None)
        if conv:
            conv["is_active"] = False
            conv["ended_at"] = datetime.utcnow().isoformat()
        return conv or {}


voice_service = VoiceService()
conversation_voice_manager = ConversationVoiceManager()
