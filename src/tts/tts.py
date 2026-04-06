import io
import edge_tts

VOICE = "fr-FR-HenriNeural"
PITCH = "-15Hz"
RATE  = "-8%"
TEXT_LIMIT = 2000


async def generer_audio(text: str) -> bytes:
    communicate = edge_tts.Communicate(text[:TEXT_LIMIT], VOICE, pitch=PITCH, rate=RATE)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()
