import os
import httpx
from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from fastapi.responses import StreamingResponse
from supabase_client import supabase
from preprocessing import pretraiter_audio
import io
import uuid

router = APIRouter(prefix="/conversion", tags=["Conversion"])

# Récupérer l'URL depuis les variables d'environnement
KAGGLE_CONVERSION_URL = os.getenv("KAGGLE_CONVERSION_URL", "https://surrogate-jujitsu-unlovely.ngrok-free.dev")
print(f"[DEBUG] KAGGLE_CONVERSION_URL = {KAGGLE_CONVERSION_URL}")


@router.post("/convertir")
async def convertir(
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

        # Vérifier durée minimum
        if duree < 1.5:
            raise HTTPException(
                400,
                f"Audio trop court après nettoyage ({duree:.1f}s). Minimum 1.5 secondes requis."
            )

        # ============================================================
        # APPEL AU MODÈLE KAGGLE (knn-vc)
        # ============================================================
        print("[INFO] Appel au modèle Kaggle knn-vc")
        print(f"[DEBUG] Envoi à Kaggle : {KAGGLE_CONVERSION_URL}/convert")

        async with httpx.AsyncClient(timeout=120.0) as client:
            reponse = await client.post(
                f"{KAGGLE_CONVERSION_URL}/convert",
                files={"file": (fichier.filename, audio_bytes_propre, "audio/wav")},
                headers={"ngrok-skip-browser-warning": "true"}
            )
            
            print(f"[DEBUG] Status code Kaggle : {reponse.status_code}")
            
            if reponse.status_code != 200:
                print(f"[DEBUG] Erreur Kaggle: {reponse.text[:500]}")
                raise HTTPException(500, f"Erreur du modèle: {reponse.status_code}")
            
            audio_converti = reponse.content
        # ============================================================

        session_id = str(uuid.uuid4())
        url_original = ""
        url_converti = ""

        if user_id:
            # Upload audio original
            chemin_original = f"{user_id}/original_{session_id}.wav"
            supabase.storage.from_("audio-originaux").upload(
                chemin_original, audio_bytes_brut, {"content-type": "audio/wav"}
            )
            url_original = supabase.storage.from_("audio-originaux")\
                .get_public_url(chemin_original)

            # Upload audio converti
            chemin_converti = f"{user_id}/converti_{session_id}.wav"
            supabase.storage.from_("audio-convertis").upload(
                chemin_converti, audio_converti, {"content-type": "audio/wav"}
            )
            url_converti = supabase.storage.from_("audio-convertis")\
                .get_public_url(chemin_converti)

            # Sauvegarder la session dans Supabase
            supabase.table("conversion_sessions").insert({
                "id":              session_id,
                "user_id":         user_id,
                "audio_original":  url_original,
                "audio_converti":  url_converti,
                "duree_secondes":  duree
            }).execute()

            # Ajouter dans l'historique
            supabase.table("historique").insert({
                "user_id":      user_id,
                "type_action":  "conversion",
                "reference_id": session_id
            }).execute()

        # Retourner l'audio converti
        return StreamingResponse(
            io.BytesIO(audio_converti),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=converti_{fichier.filename}",
                "X-Session-ID":        session_id,
                "X-URL-Original":      url_original,
                "X-URL-Converti":      url_converti,
                "X-Duree":             str(duree)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERREUR] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historique/{user_id}")
def historique_conversion(user_id: str):
    try:
        reponse = supabase.table("conversion_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()
        return {"statut": "succes", "sessions": reponse.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))