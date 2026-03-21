"""
Synthèse vocale française via Edge TTS (Microsoft Neural voices).
Voix : Henri (homme, grave) avec pitch abaissé pour un rendu solennel.
"""
import asyncio
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


def generer_audio(text: str) -> bytes:
    """Génère un fichier MP3 en mémoire à partir du texte."""
    return asyncio.run(_generate(text[:2000]))
