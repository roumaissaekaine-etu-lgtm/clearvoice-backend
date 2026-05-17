import numpy as np
import librosa
import noisereduce as nr
from scipy.signal import butter, sosfilt
import soundfile as sf
import tempfile
import os

SR = 16000

def pretraiter_audio(audio_bytes: bytes) -> tuple:
    """
    Reçoit les bytes d'un fichier audio.
    Retourne les bytes de l'audio nettoyé et la durée en secondes.
    """

    # Sauvegarder temporairement
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_input = f.name

    try:
        # Étape 1 — Standardisation
        audio, _ = librosa.load(tmp_input, sr=SR, mono=True, dtype=np.float32)
        duree = len(audio) / SR

        # Vérification durée minimale
        if duree < 0.5:
            raise ValueError("Audio trop court. Minimum 0.5 seconde requis.")

        # Étape 2 — VAD (suppression silences)
        hop = 128
        rms = librosa.feature.rms(y=audio, frame_length=512, hop_length=hop)[0]
        seuil = np.percentile(rms, 15)
        masque = rms > seuil
        segments = []
        in_speech = False
        debut = 0
        for i, v in enumerate(masque):
            if v and not in_speech:
                debut = i
                in_speech = True
            elif not v and in_speech:
                t0 = debut * hop / SR
                t1 = i * hop / SR
                if (t1 - t0) > 0.2:
                    segments.append(audio[int(t0*SR):int(t1*SR)])
                in_speech = False
        if segments:
            silence = np.zeros(int(0.05 * SR), dtype=np.float32)
            audio = segments[0]
            for s in segments[1:]:
                audio = np.concatenate([audio, silence, s])

        # Étape 3 — Débruitage
        sos = butter(4, [60/(SR/2), 7500/(SR/2)], btype='band', output='sos')
        audio = sosfilt(sos, audio).astype(np.float32)
        bruit = audio[:int(0.2 * SR)]
        if np.sqrt(np.mean(bruit**2)) > 0.005:
            audio_d = nr.reduce_noise(
                y=audio, sr=SR, y_noise=bruit,
                prop_decrease=0.65, stationary=True
            )
            ratio = np.sqrt(np.mean(audio_d**2)) / (np.sqrt(np.mean(audio**2)) + 1e-8)
            if ratio >= 0.3:
                audio = audio_d

        # Étape 4 — Normalisation volume
        rms_val = np.sqrt(np.mean(audio**2))
        if rms_val > 0:
            audio = np.clip(audio * min(0.08/rms_val, 10.0), -1.0, 1.0)
        audio = audio.astype(np.float32)

        # Sauvegarder l'audio propre
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_output = f.name
        sf.write(tmp_output, audio, SR)

        with open(tmp_output, "rb") as f:
            audio_propre_bytes = f.read()

        duree_finale = len(audio) / SR

        return audio_propre_bytes, duree_finale

    finally:
        if os.path.exists(tmp_input):
            os.remove(tmp_input)
        if 'tmp_output' in locals() and os.path.exists(tmp_output):
            os.remove(tmp_output)