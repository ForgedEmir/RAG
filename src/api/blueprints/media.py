import logging
import os
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from src.api.auth import get_current_user
from src.api.limiter import limiter
from src.monitoring.tracker import track

logger = logging.getLogger(__name__)
media_router = APIRouter()

MAX_STT_SIZE = int(os.getenv("MAX_STT_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_AUDIO = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp3", "audio/ogg", "audio/mp4", "audio/x-m4a"}

@media_router.post("/api/tts")
@limiter.limit("30/minute")
async def tts(request: Request, user_id: str = Depends(get_current_user)):
    # WHY: TTS was previously public (only rate-limited by IP). Without auth,
    # anyone could exhaust the Edge-TTS quota. Now requires a valid JWT or
    # guest header, consistent with /api/ask.
    try:
        body = await request.json()
        if not (text := (body or {}).get("text", "")):
            return JSONResponse({"error": "Empty text"}, status_code=400)
        from src.tts.tts import generer_audio
        audio = await generer_audio(text)
        await track("tts", detail=f"{len(text)} chars")
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return JSONResponse({"error": "Internal error"}, status_code=500)

@media_router.post("/api/stt")
@limiter.limit("20/minute")
async def stt(request: Request, audio: UploadFile = File(...),
              user_id: str = Depends(get_current_user)):
    # WHY: STT was previously public (only rate-limited by IP). Without auth,
    # anyone could call the paid Groq Whisper API and exhaust the quota.
    # Now requires a valid JWT or guest header, consistent with /api/ask.
    import asyncio
    try:
        if audio.content_type and audio.content_type.lower() not in ALLOWED_AUDIO:
            return JSONResponse({"error": "Audio format not supported"}, status_code=400)

        content = await audio.read()
        if len(content) > MAX_STT_SIZE:
            limit_mb = MAX_STT_SIZE // (1024 * 1024)
            return JSONResponse({"error": f"Audio too large. Max: {limit_mb} MB"}, status_code=400)

        from openai import OpenAI
        stt_api_key = os.getenv("STT_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        stt_base_url = os.getenv("STT_BASE_URL", "https://api.groq.com/openai/v1")
        stt_model = os.getenv("STT_MODEL", "whisper-large-v3")
        client = OpenAI(api_key=stt_api_key, base_url=stt_base_url)

        # Whisper call can take seconds, wrap in thread to keep event loop free
        def _transcribe():
            return client.audio.transcriptions.create(
                model=stt_model,
                file=(audio.filename or "audio.webm", content),
            )

        transcription = await asyncio.to_thread(_transcribe)
        detected_lang = getattr(transcription, "language", "unknown")
        await track("voice", detail=f"{stt_model} | {audio.filename or 'audio.webm'} | lang:{detected_lang}")
        return {"text": transcription.text, "detected_language": detected_lang}
    except Exception as e:
        logger.error(f"STT Error: {e}")
        return JSONResponse({"error": "Internal error"}, status_code=500)
