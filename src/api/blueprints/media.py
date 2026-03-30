"""Router media — /api/tts, /api/stt"""
import logging
import os

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response

from src.api.limiter import limiter
from src.monitoring.tracker import track

logger = logging.getLogger(__name__)
media_router = APIRouter()


@media_router.post("/api/tts")
@limiter.limit("30/minute")
async def tts(request: Request):
    try:
        body = await request.json()
        text = (body or {}).get("text", "")
        if not text:
            return JSONResponse({"error": "Texte vide"}, status_code=400)
        from src.tts.tts import generer_audio
        audio = await generer_audio(text)
        track("tts", detail=f"{len(text)} chars")
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS : {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@media_router.post("/api/stt")
@limiter.limit("20/minute")
async def stt(request: Request, audio: UploadFile = File(...)):
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        content = await audio.read()
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(audio.filename or "audio.webm", content),
            language="fr",
        )
        track("voice", detail=f"whisper | {audio.filename or 'audio.webm'}")
        return {"text": transcription.text}
    except Exception as e:
        logger.error(f"STT : {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
