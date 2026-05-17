import uuid
import httpx
from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from pydantic import BaseModel
from supabase_client import supabase
from typing import Optional

router = APIRouter(prefix="/training", tags=["Entraînement"])

# Liste des mots et phrases pour l'entraînement
EXERCICES = {
    "facile": [
        "Bonjour",
        "Merci",
        "Oui",
        "Non",
        "Eau",
        "Pain",
        "Maison",
        "Chat",
        "Chien",
        "Soleil"
    ],
    "moyen": [
        "Je vais bien",
        "Comment allez-vous",
        "S'il vous plaît",
        "Bonne journée",
        "Au revoir",
        "Je m'appelle",
        "J'ai besoin d'aide",
        "Pouvez-vous répéter"
    ],
    "difficile": [
        "Je voudrais un verre d'eau s'il vous plaît",
        "Pouvez-vous m'aider à communiquer",
        "Je comprends ce que vous dites",
        "La rééducation m'aide à progresser",
        "Mon orthophoniste suit mes progrès"
    ]
}


class NouvelleSessionRequest(BaseModel):
    niveau:  str = "facile"
    user_id: str


class SoumettreAudioRequest(BaseModel):
    session_id: str
    mot_cible:  str
    user_id:    str


@router.get("/exercices")
def get_exercices(niveau: str = "facile"):
    if niveau not in EXERCICES:
        raise HTTPException(400, "Niveau invalide. Choisir: facile, moyen, difficile")

    return {
        "statut":   "succes",
        "niveau":   niveau,
        "exercices": EXERCICES[niveau]
    }


@router.post("/nouvelle-session")
def nouvelle_session(data: NouvelleSessionRequest):
    try:
        import random

        mots = EXERCICES.get(data.niveau, EXERCICES["facile"])
        mots_selectionnes = random.sample(mots, min(5, len(mots)))

        session_id = str(uuid.uuid4())

        supabase.table("training_sessions").insert({
            "id":            session_id,
            "user_id":       data.user_id,
            "nb_mots_total": len(mots_selectionnes),
            "score_global":  0.0
        }).execute()

        supabase.table("historique").insert({
            "user_id":      data.user_id,
            "type_action":  "training",
            "reference_id": session_id
        }).execute()

        return {
            "statut":            "succes",
            "session_id":        session_id,
            "niveau":            data.niveau,
            "mots_a_prononcer":  mots_selectionnes,
            "nb_mots":           len(mots_selectionnes)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soumettre-audio")
async def soumettre_audio(
    fichier:    UploadFile = File(...),
    session_id: str = None,
    mot_cible:  str = None,
    user_id:    str = None,
    authorization: str = Header(None)
):
    try:
        audio_bytes = await fichier.read()

        attempt_id   = str(uuid.uuid4())
        url_audio    = ""
        score        = 0.0
        valide       = False

        # Upload audio dans Storage
        if user_id:
            chemin = f"{user_id}/training_{attempt_id}.wav"
            supabase.storage.from_("audio-originaux").upload(
                chemin,
                audio_bytes,
                {"content-type": "audio/wav"}
            )
            url_audio = supabase.storage.from_("audio-originaux")\
                .get_public_url(chemin)

        # Évaluation simple basée sur la durée de l'audio
        duree_estimation = len(audio_bytes) / 32000
        if duree_estimation >= 0.5:
            score  = min(1.0, duree_estimation / 3.0)
            valide = score >= 0.5

        # Sauvegarder la tentative
        supabase.table("training_attempts").insert({
            "id":         attempt_id,
            "session_id": session_id,
            "user_id":    user_id,
            "mot_cible":  mot_cible,
            "audio_url":  url_audio,
            "score":      round(score, 4),
            "valide":     valide
        }).execute()

        # Mettre à jour le score de la session
        tentatives = supabase.table("training_attempts")\
            .select("score, valide")\
            .eq("session_id", session_id)\
            .execute()

        if tentatives.data:
            nb_total   = len(tentatives.data)
            nb_reussis = sum(1 for t in tentatives.data if t["valide"])
            score_global = nb_reussis / nb_total if nb_total > 0 else 0

            supabase.table("training_sessions").update({
                "nb_mots_reussis": nb_reussis,
                "score_global":    round(score_global, 4)
            }).eq("id", session_id).execute()

        feedback = "Excellent !" if valide else "Essayez encore, parlez plus clairement."

        return {
            "statut":     "succes",
            "attempt_id": attempt_id,
            "mot_cible":  mot_cible,
            "score":      round(score, 4),
            "valide":     valide,
            "feedback":   feedback,
            "audio_url":  url_audio
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historique/{user_id}")
def historique_training(user_id: str):
    try:
        sessions = supabase.table("training_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()

        return {
            "statut":   "succes",
            "sessions": sessions.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}")
def detail_session(session_id: str):
    try:
        session = supabase.table("training_sessions")\
            .select("*")\
            .eq("id", session_id)\
            .single()\
            .execute()

        tentatives = supabase.table("training_attempts")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at")\
            .execute()

        return {
            "statut":     "succes",
            "session":    session.data,
            "tentatives": tentatives.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))