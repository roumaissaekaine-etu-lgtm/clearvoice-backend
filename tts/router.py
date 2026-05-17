import uuid
import io
import edge_tts
import asyncio
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase_client import supabase

router = APIRouter(prefix="/tts", tags=["Synthèse Vocale"])


class TTSRequest(BaseModel):
    texte:   str
    langue:  str = "fr-FR"
    voix:    str = "fr-FR-HenriNeural"


VOIX_DISPONIBLES = {
    "fr-FR-HenriNeural":    "Homme français",
    "fr-FR-DeniseNeural":   "Femme française",
    "ar-MA-JamalNeural":    "Homme arabe marocain",
    "ar-MA-MounaNeural":    "Femme arabe marocaine",
    "en-US-GuyNeural":      "Homme anglais",
    "en-US-JennyNeural":    "Femme anglaise",
}


async def generer_audio_tts(texte: str, voix: str) -> bytes:
    communicate = edge_tts.Communicate(texte, voix)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    audio_buffer.seek(0)
    return audio_buffer.read()


@router.get("/voix")
def liste_voix():
    return {
        "statut": "succes",
        "voix":   VOIX_DISPONIBLES
    }


@router.post("/synthesiser")
async def synthesiser(
    data: TTSRequest,
    authorization: str = Header(None)
):
    try:
        if not data.texte.strip():
            raise HTTPException(400, "Le texte ne peut pas être vide")

        if len(data.texte) > 1000:
            raise HTTPException(400, "Le texte ne doit pas dépasser 1000 caractères")

        # Récupérer user_id depuis le token
        user_id = None
        if authorization:
            token = authorization.replace("Bearer ", "")
            user = supabase.auth.get_user(token)
            if user and user.user:
                user_id = user.user.id

        # Générer l'audio avec Edge-TTS
        audio_bytes = await generer_audio_tts(data.texte, data.voix)

        # Sauvegarder dans Supabase si connecté
        session_id = str(uuid.uuid4())
        url_audio  = ""

        if user_id:
            # Upload audio TTS dans Storage
            chemin_audio = f"{user_id}/tts_{session_id}.mp3"
            supabase.storage.from_("audio-tts").upload(
                chemin_audio,
                audio_bytes,
                {"content-type": "audio/mpeg"}
            )
            url_audio = supabase.storage.from_("audio-tts")\
                .get_public_url(chemin_audio)

            # Sauvegarder la session TTS
            supabase.table("tts_sessions").insert({
                "id":         session_id,
                "user_id":    user_id,
                "texte_entre": data.texte,
                "audio_url":  url_audio,
            }).execute()

            # Ajouter dans l'historique
            supabase.table("historique").insert({
                "user_id":      user_id,
                "type_action":  "tts",
                "reference_id": session_id
            }).execute()

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=tts_{session_id}.mp3",
                "X-Session-ID":        session_id,
                "X-Audio-URL":         url_audio
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historique/{user_id}")
def historique_tts(user_id: str):
    try:
        reponse = supabase.table("tts_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        return {
            "statut":   "succes",
            "sessions": reponse.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))