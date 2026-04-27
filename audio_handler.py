import numpy as np
import queue
import sounddevice as sd
import tensorflow as tf
import tensorflow_hub as hub
import pandas as pd
import config
import shutil
import os

# ==============================
# Internal State
# ==============================

audio_queue = queue.Queue()
temporal_counter = 0

# ==============================
# Load YAMNet Model with Retry Logic
# ==============================

def load_yamnet_model(max_retries=3):
    """Load YAMNet model with retry logic and cache clearing."""
    for attempt in range(max_retries):
        try:
            print(f"[INFO] Loading YAMNet model (attempt {attempt + 1}/{max_retries})...")
            yamnet = hub.load("https://tfhub.dev/google/yamnet/1")
            print("[INFO] YAMNet loaded successfully.")
            return yamnet
        except Exception as e:
            print(f"[WARNING] Failed to load YAMNet (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                # Clear cache before retrying
                cache_dir = os.path.join(os.environ.get('TEMP', '/tmp'), 'tfhub_modules')
                if os.path.exists(cache_dir):
                    print(f"[INFO] Clearing TensorFlow Hub cache at {cache_dir}")
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as cleanup_error:
                        print(f"[WARNING] Could not clear cache: {cleanup_error}")
                print("[INFO] Retrying...")
    
    raise RuntimeError("Failed to load YAMNet model after all retries")

yamnet = load_yamnet_model()

class_map_path = tf.keras.utils.get_file(
    "yamnet_class_map.csv",
    "https://storage.googleapis.com/audioset/yamnet/yamnet_class_map.csv"
)
# Use pandas to read class names exactly as YAMNet labels them (more reliable than CSV split)
df = pd.read_csv(class_map_path)
class_names = df['display_name'].tolist()

print("[INFO] YAMNet and class map loaded successfully.")


# ==============================
# Helper: Aggregate Siren Score
# ==============================
def classify_siren(mean_scores):
    """
    Ultra-sensitive siren detection.
    If any siren-related class appears, trigger detection.
    """

    siren_score = 0.0

    for idx, name in enumerate(class_names):
        if any(k.lower() in name.lower() for k in config.SIREN_KEYWORDS):
            siren_score += mean_scores[idx]

    # Detect even extremely small siren probabilities
    if siren_score > 0.005:
        return "SIREN", siren_score

    return "NORMAL TRAFFIC", siren_score

# ==============================
# Helper: Dominant Frequency
# ==============================

def get_dominant_frequency(audio, sr):
    """Hanning window before FFT for cleaner frequency estimation."""
    windowed = audio * np.hanning(len(audio))
    fft = np.fft.rfft(windowed)
    freqs = np.fft.rfftfreq(len(audio), d=1 / sr)
    magnitude = np.abs(fft)
    return float(freqs[np.argmax(magnitude)])


# ==============================
# Audio Callback
# ==============================

def audio_callback(indata, frames, time_info, status):
    if status:
        print("[WARNING] Audio input status:", status)
    audio_queue.put(indata.copy().flatten())


# ==============================
# Main Audio Processing Loop
# ==============================

def audio_processing_loop():
    global temporal_counter

    # Rolling 1-second audio buffer — gives YAMNet full context per inference
    audio_buffer = np.array([], dtype=np.float32)

    print("[INFO] Starting audio stream...")

    with sd.InputStream(
        channels=1,
        samplerate=config.SAMPLE_RATE,
        blocksize=config.BLOCK_SIZE,
        callback=audio_callback
    ):
        print("[INFO] Microphone stream started.")

        while True:
            block = audio_queue.get()

            # ----------------------------
            # 1. Accumulate rolling buffer
            # ----------------------------
            audio_buffer = np.concatenate([audio_buffer, block])
            # Keep only the latest 1 second
            if len(audio_buffer) > config.SAMPLE_RATE:
                audio_buffer = audio_buffer[-config.SAMPLE_RATE:]

            # Wait until we have at least 1 full second of audio
            if len(audio_buffer) < config.SAMPLE_RATE:
                continue

            # ----------------------------
            # 2. YAMNet Inference
            # ----------------------------
            scores, embeddings, spectrogram = yamnet(audio_buffer)
            mean_scores = np.mean(scores, axis=0)

            # ----------------------------
            # 3. Aggregate Siren Classification
            # ----------------------------
            category, siren_score = classify_siren(mean_scores)
            siren_detected = (category == "SIREN")

            # Top-1 class for display purposes
            top_idx = np.argmax(mean_scores)
            top_class = class_names[top_idx]
            top_confidence = float(mean_scores[top_idx])

            # ----------------------------
            # 4. Dominant Frequency
            # ----------------------------
            dominant_freq = get_dominant_frequency(audio_buffer, config.SAMPLE_RATE)
            wavelength = round(343.0 / dominant_freq, 4) if dominant_freq > 0 else 0

            # ----------------------------
            # 5. Temporal Smoothing
            #    TEMPORAL_FRAMES = 1 → instant trigger on first positive frame
            # ----------------------------
            if siren_detected:
                temporal_counter += 1
            else:
                temporal_counter = max(0, temporal_counter - 1)

            status = (
                "SIREN DETECTED"
                if temporal_counter >= config.TEMPORAL_FRAMES
                else "Normal traffic"
            )

            # ----------------------------
            # 6. Update Global State
            # ----------------------------
            if status == "SIREN DETECTED":
                config.latest_data["system"]["search_mode"] = True
                config.latest_data["system"]["search_reason"] = "Audio Siren"

            config.latest_data["audio"] = {
                "status": status,
                "confidence": round(float(siren_score), 2),
                "label": top_class,
                "category": category,
                "dominant_freq": round(dominant_freq, 1),
                "valid_frequency": config.LOWCUT <= dominant_freq <= config.HIGHCUT,
                "energy": 0.0,    # Not needed in this pipeline; kept for API compatibility
                "wavelength": wavelength
            }

            # ----------------------------
            # 7. Console Debug
            # ----------------------------
            print(
                f"[AUDIO] {status} | Label: {top_class} | Conf: {top_confidence:.2f} "
                f"| SirenScore: {siren_score:.3f} | Freq: {dominant_freq:.0f}Hz"
            )
