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

    tmp_input = None
    tmp_output = None

    try:
        # ==============================
        # Sauvegarder fichier temporaire
        # ==============================
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as f:
            f.write(audio_bytes)
            tmp_input = f.name

        print(f"[INFO] Audio temporaire : {tmp_input}")

        # ==============================
        # Chargement audio sécurisé
        # ==============================
        try:
            audio, _ = librosa.load(
                tmp_input,
                sr=SR,
                mono=True,
                dtype=np.float32
            )
        except Exception as e:
            print("[ERREUR] Impossible de charger l'audio")
            print(str(e))
            raise Exception(f"Erreur chargement audio : {str(e)}")

        # Vérification audio vide
        if audio is None or len(audio) == 0:
            raise Exception("Audio vide ou illisible")

        duree = len(audio) / SR

        print(f"[INFO] Durée audio : {duree:.2f} sec")

        # ==============================
        # Vérification durée minimale
        # ==============================
        if duree < 0.5:
            raise Exception(
                "Audio trop court. Minimum 0.5 seconde requis."
            )

        # ==============================
        # Suppression des silences
        # ==============================
        hop = 128

        rms = librosa.feature.rms(
            y=audio,
            frame_length=512,
            hop_length=hop
        )[0]

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
                    segments.append(
                        audio[int(t0 * SR):int(t1 * SR)]
                    )

                in_speech = False

        if len(segments) > 0:

            silence = np.zeros(
                int(0.05 * SR),
                dtype=np.float32
            )

            audio_final = segments[0]

            for s in segments[1:]:
                audio_final = np.concatenate(
                    [audio_final, silence, s]
                )

            audio = audio_final

        # ==============================
        # Filtrage fréquence
        # ==============================
        sos = butter(
            4,
            [60 / (SR / 2), 7500 / (SR / 2)],
            btype='band',
            output='sos'
        )

        audio = sosfilt(sos, audio).astype(np.float32)

        # ==============================
        # Réduction du bruit
        # ==============================
        try:

            bruit = audio[:int(0.2 * SR)]

            if len(bruit) > 0:

                energie_bruit = np.sqrt(
                    np.mean(bruit ** 2)
                )

                if energie_bruit > 0.005:

                    audio_d = nr.reduce_noise(
                        y=audio,
                        sr=SR,
                        y_noise=bruit,
                        prop_decrease=0.65,
                        stationary=True
                    )

                    ratio = (
                        np.sqrt(np.mean(audio_d ** 2))
                        /
                        (np.sqrt(np.mean(audio ** 2)) + 1e-8)
                    )

                    if ratio >= 0.3:
                        audio = audio_d.astype(np.float32)

        except Exception as e:
            print("[WARNING] Réduction bruit ignorée")
            print(str(e))

        # ==============================
        # Normalisation volume
        # ==============================
        rms_val = np.sqrt(np.mean(audio ** 2))

        if rms_val > 0:

            gain = min(0.08 / rms_val, 10.0)

            audio = np.clip(
                audio * gain,
                -1.0,
                1.0
            )

        audio = audio.astype(np.float32)

        # ==============================
        # Sauvegarde finale
        # ==============================
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as f:
            tmp_output = f.name

        sf.write(tmp_output, audio, SR)

        with open(tmp_output, "rb") as f:
            audio_propre_bytes = f.read()

        duree_finale = len(audio) / SR

        print("[INFO] Prétraitement terminé")

        return audio_propre_bytes, duree_finale

    except Exception as e:

        print("[ERREUR PREPROCESSING]")
        print(str(e))

        raise Exception(str(e))

    finally:

        try:
            if tmp_input and os.path.exists(tmp_input):
                os.remove(tmp_input)
        except:
            pass

        try:
            if tmp_output and os.path.exists(tmp_output):
                os.remove(tmp_output)
        except:
            pass