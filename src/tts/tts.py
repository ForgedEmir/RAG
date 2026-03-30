"""
Synthèse vocale via Edge TTS (voix Microsoft Neural).
Voix : Henri (homme, grave) avec pitch abaissé pour un ton solennel.
"""
import io
import logging

logger = logging.getLogger(__name__)

VOICE = "fr-FR-HenriNeural"
PITCH = "-15Hz"
RATE  = "-8%"


async def _generate(text: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, pitch=PITCH, rate=RATE)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


async def generer_audio(text: str) -> bytes:
    """Génère un MP3 en mémoire à partir du texte (max 2000 chars)."""
    return await _generate(text[:2000])
