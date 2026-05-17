import httpx
import uuid
from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from supabase_client import supabase
from preprocessing import pretraiter_audio

router = APIRouter(prefix="/detection", tags=["Détection"])

KAGGLE_DETECTION_URL = "https://untold-humorist-backfire.ngrok-free.dev"


@router.post("/analyser")
async def analyser(
    fichier: UploadFile = File(...),
    authorization: str = Header(None)
):
    try:
        user_id = None
        if authorization:
            token = authorization.replace("Bearer ", "")
            user = supabase.auth.get_user(token)
            if user and user.user:
                user_id = user.user.id

        # Lire l'audio brut
        audio_bytes_brut = await fichier.read()

        # Vérifier la taille
        taille_mb = len(audio_bytes_brut) / (1024 * 1024)
        if taille_mb > 50:
            raise HTTPException(400, "Fichier trop volumineux. Maximum 50 MB.")

        # Prétraitement
        audio_bytes_propre, duree = pretraiter_audio(audio_bytes_brut)

        if duree < 0.5:
            raise HTTPException(
                400,
                f"Audio trop court ({duree:.1f}s). Minimum 0.5 seconde requis."
            )

        # Envoyer l'audio propre à Kaggle
        async with httpx.AsyncClient(timeout=120.0) as client:
            reponse = await client.post(
                f"{KAGGLE_DETECTION_URL}/detect",
                files={"file": (fichier.filename, audio_bytes_propre, "audio/wav")},
                headers={"ngrok-skip-browser-warning": "true"}
            )

        if reponse.status_code != 200:
            raise HTTPException(500, "Erreur lors de la détection")

        resultat   = reponse.json()
        session_id = str(uuid.uuid4())
        url_audio  = ""

        if user_id:
            chemin = f"{user_id}/detection_{session_id}.wav"
            supabase.storage.from_("audio-originaux").upload(
                chemin, audio_bytes_brut, {"content-type": "audio/wav"}
            )
            url_audio = supabase.storage.from_("audio-originaux")\
                .get_public_url(chemin)

            supabase.table("detection_sessions").insert({
                "id":              session_id,
                "user_id":         user_id,
                "audio_url":       url_audio,
                "severity_score":  resultat.get("severity_score", 0),
                "niveau":          resultat.get("niveau", "modéré"),
                "description":     resultat.get("description", ""),
                "score_confiance": resultat.get("score", 0),
                "toutes_probs":    resultat.get("toutes_probs", {})
            }).execute()

            supabase.table("historique").insert({
                "user_id":      user_id,
                "type_action":  "detection",
                "reference_id": session_id
            }).execute()

        return {
            "statut":         "succes",
            "session_id":     session_id,
            "severity_score": resultat.get("severity_score"),
            "niveau":         resultat.get("niveau"),
            "description":    resultat.get("description"),
            "score":          resultat.get("score"),
            "label_brut":     resultat.get("label_brut"),
            "toutes_probs":   resultat.get("toutes_probs"),
            "audio_url":      url_audio
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historique/{user_id}")
def historique_detection(user_id: str):
    try:
        reponse = supabase.table("detection_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()
        return {"statut": "succes", "sessions": reponse.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))