import os
import config

AUDIO_ENABLED = config.ENABLE_AUDIO

if AUDIO_ENABLED:
    import numpy as np
    import queue
    import sounddevice as sd
    import tensorflow as tf
    import tensorflow_hub as hub
    import pandas as pd
    import shutil

    # Internal State
    audio_queue = queue.Queue()
    temporal_counter = 0

    # Load YAMNet Model with Retry Logic
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
    df = pd.read_csv(class_map_path)
    class_names = df['display_name'].tolist()
    print("[INFO] YAMNet and class map loaded successfully.")

    def classify_siren(mean_scores):
        """Ultra-sensitive siren detection."""
        siren_score = 0.0
        for idx, name in enumerate(class_names):
            if any(k.lower() in name.lower() for k in config.SIREN_KEYWORDS):
                siren_score += mean_scores[idx]
        if siren_score > 0.005:
            return "SIREN", siren_score
        return "NORMAL TRAFFIC", siren_score

    def get_dominant_frequency(audio, sr):
        """Hanning window before FFT for cleaner frequency estimation."""
        windowed = audio * np.hanning(len(audio))
        fft = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(audio), d=1 / sr)
        magnitude = np.abs(fft)
        return float(freqs[np.argmax(magnitude)])

    def audio_callback(indata, frames, time_info, status):
        if status:
            print("[WARNING] Audio input status:", status)
        audio_queue.put(indata.copy().flatten())

    def audio_processing_loop():
        if not AUDIO_ENABLED:
            print("[INFO] Audio processing skipped — disabled.")
            return
        global temporal_counter
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
                audio_buffer = np.concatenate([audio_buffer, block])
                if len(audio_buffer) > config.SAMPLE_RATE:
                    audio_buffer = audio_buffer[-config.SAMPLE_RATE:]
                if len(audio_buffer) < config.SAMPLE_RATE:
                    continue
                scores, embeddings, spectrogram = yamnet(audio_buffer)
                mean_scores = np.mean(scores, axis=0)
                category, siren_score = classify_siren(mean_scores)
                siren_detected = (category == "SIREN")
                top_idx = np.argmax(mean_scores)
                top_class = class_names[top_idx]
                top_confidence = float(mean_scores[top_idx])
                dominant_freq = get_dominant_frequency(audio_buffer, config.SAMPLE_RATE)
                wavelength = round(343.0 / dominant_freq, 4) if dominant_freq > 0 else 0
                if siren_detected:
                    temporal_counter += 1
                else:
                    temporal_counter = max(0, temporal_counter - 1)
                status = (
                    "SIREN DETECTED"
                    if temporal_counter >= config.TEMPORAL_FRAMES
                    else "Normal traffic"
                )
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
                    "energy": 0.0,
                    "wavelength": wavelength
                }
                print(
                    f"[AUDIO] {status} | Label: {top_class} | Conf: {top_confidence:.2f} "
                    f"| SirenScore: {siren_score:.3f} | Freq: {dominant_freq:.0f}Hz"
                )
else:
    print("[INFO] Audio processing disabled (ENABLE_AUDIO=false)")
