from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth.router import router as auth_router
from conversion.router import router as conversion_router
from detection.router import router as detection_router
from tts.router import router as tts_router
from training.router import router as training_router
from history.router import router as history_router
import conversion.router as conv_mod
import detection.router as det_mod

app = FastAPI(
    title="ClearVoice API",
    version="1.0.0",
    description="Backend ClearVoice — Application IA pour la dysarthrie"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(conversion_router)
app.include_router(detection_router)
app.include_router(tts_router)
app.include_router(training_router)
app.include_router(history_router)


class URLsRequest(BaseModel):
    kaggle_conversion_url: str = None
    kaggle_detection_url:  str = None


@app.post("/admin/update-urls")
def update_urls(data: URLsRequest):
    if data.kaggle_conversion_url:
        conv_mod.KAGGLE_CONVERSION_URL = data.kaggle_conversion_url
    if data.kaggle_detection_url:
        det_mod.KAGGLE_DETECTION_URL = data.kaggle_detection_url
    return {
        "statut": "succes",
        "conversion_url": conv_mod.KAGGLE_CONVERSION_URL,
        "detection_url":  det_mod.KAGGLE_DETECTION_URL
    }


@app.get("/admin/urls")
def get_urls():
    return {
        "conversion_url": conv_mod.KAGGLE_CONVERSION_URL,
        "detection_url":  det_mod.KAGGLE_DETECTION_URL
    }


@app.get("/")
def root():
    return {
        "statut":  "ok",
        "message": "ClearVoice API fonctionne",
        "version": "1.0.0"
    }