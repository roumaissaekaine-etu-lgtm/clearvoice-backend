from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase_client import supabase

router = APIRouter(prefix="/auth", tags=["Authentification"])


class InscriptionRequest(BaseModel):
    email:    str
    password: str
    nom:      str
    age:      int
    sexe:     str
    origine:  str


class ConnexionRequest(BaseModel):
    email:    str
    password: str


@router.post("/inscription")
def inscription(data: InscriptionRequest):
    try:
        reponse = supabase.auth.sign_up({
            "email":    data.email,
            "password": data.password,
            "options": {
                "data": {"nom": data.nom}
            }
        })

        if not reponse.user:
            raise HTTPException(400, "Erreur création compte")

        user_id = reponse.user.id

        supabase.table("profiles").upsert({
            "id":      user_id,
            "nom":     data.nom,
            "age":     data.age,
            "sexe":    data.sexe,
            "origine": data.origine
        }).execute()

        return {
            "statut":  "succes",
            "message": "Compte créé avec succès",
            "user_id": user_id,
            "email":   data.email
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/connexion")
def connexion(data: ConnexionRequest):
    try:
        reponse = supabase.auth.sign_in_with_password({
            "email":    data.email,
            "password": data.password
        })

        if not reponse.user:
            raise HTTPException(401, "Email ou mot de passe incorrect")

        return {
            "statut":       "succes",
            "message":      "Connexion réussie",
            "user_id":      reponse.user.id,
            "email":        reponse.user.email,
            "access_token": reponse.session.access_token
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/profil/{user_id}")
def profil(user_id: str):
    try:
        reponse = supabase.table("profiles")\
            .select("*")\
            .eq("id", user_id)\
            .single()\
            .execute()

        if not reponse.data:
            raise HTTPException(404, "Profil non trouvé")

        return {
            "statut": "succes",
            "profil": reponse.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deconnexion")
def deconnexion():
    try:
        supabase.auth.sign_out()
        return {
            "statut":  "succes",
            "message": "Déconnexion réussie"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))