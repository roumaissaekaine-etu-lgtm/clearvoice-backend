from fastapi import APIRouter, HTTPException, Header
from supabase_client import supabase

router = APIRouter(prefix="/history", tags=["Historique"])


@router.get("/{user_id}/complet")
def get_history_complet(
    user_id: str,
    authorization: str = Header(None)
):
    try:
        # Vérifier le token
        if authorization:
            token = authorization.replace("Bearer ", "")
            user = supabase.auth.get_user(token)
            if not user or user.user.id != user_id:
                raise HTTPException(401, "Non autorisé")

        # Récupérer toutes les sessions
        conversions = supabase.table("conversion_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        detections = supabase.table("detection_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        tts_sessions = supabase.table("tts_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        trainings = supabase.table("training_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        return {
            "statut": "succes",
            "conversions": conversions.data,
            "detections": detections.data,
            "tts": tts_sessions.data,
            "trainings": trainings.data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))