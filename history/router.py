from fastapi import APIRouter, HTTPException
from supabase_client import supabase

router = APIRouter(prefix="/history", tags=["Historique"])


@router.get("/{user_id}")
def historique_global(user_id: str):
    try:
        reponse = supabase.table("historique")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        return {
            "statut":   "succes",
            "historique": reponse.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}/complet")
def historique_complet(user_id: str):
    try:
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

        tts = supabase.table("tts_sessions")\
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
            "statut":      "succes",
            "conversions": conversions.data,
            "detections":  detections.data,
            "tts":         tts.data,
            "trainings":   trainings.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))