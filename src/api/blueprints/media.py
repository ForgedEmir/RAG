import logging
import os
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from src.api.limiter import limiter
from src.monitoring.tracker import track

logger = logging.getLogger(__name__)
media_router = APIRouter()

MAX_STT_SIZE = int(os.getenv("MAX_STT_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_AUDIO = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp3", "audio/ogg", "audio/mp4", "audio/x-m4a"}

@media_router.post("/api/tts")
@limiter.limit("30/minute")
async def tts(request: Request):
    try:
        body = await request.json()
        if not (text := (body or {}).get("text", "")):
            return JSONResponse({"error": "Texte vide"}, status_code=400)
        from src.tts.tts import generer_audio
        audio = await generer_audio(text)
        track("tts", detail=f"{len(text)} chars")
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@media_router.post("/api/stt")
@limiter.limit("20/minute")
async def stt(request: Request, audio: UploadFile = File(...)):
    try:
        if audio.content_type and audio.content_type.lower() not in ALLOWED_AUDIO:
            return JSONResponse({"error": "Format audio non supporté"}, status_code=400)

        content = await audio.read()
        if len(content) > MAX_STT_SIZE:
            limit_mb = MAX_STT_SIZE // (1024 * 1024)
            return JSONResponse({"error": f"Audio trop volumineux. Max: {limit_mb} MB"}, status_code=400)

        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.groq.com/openai/v1")
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=(audio.filename or "audio.webm", content),
            language="fr",
        )
        track("voice", detail=f"whisper | {audio.filename or 'audio.webm'}")
        return {"text": transcription.text}
    except Exception as e:
        logger.error(f"STT Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
