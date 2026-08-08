import gc
import math
import os
import struct
import time

import board

try:
    import audiobusio
except ImportError:
    audiobusio = None

try:
    import audiocore
except ImportError:
    audiocore = None

try:
    import audiopwmio
except ImportError:
    audiopwmio = None


SAMPLE_RATE = 8000
TOTAL_SECONDS = 5
NOTE_SECONDS = 0.5
TEMP_WAV_PATH = "/_audio_diag.wav"


def build_scale_frequencies():
    base_scale = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    return base_scale + list(reversed(base_scale[:-1]))


def generate_wav_bytes():
    frequencies = build_scale_frequencies()
    samples_per_note = int(SAMPLE_RATE * NOTE_SECONDS)
    target_samples = int(SAMPLE_RATE * TOTAL_SECONDS)

    pcm = bytearray()
    note_index = 0
    while len(pcm) < target_samples:
        frequency = frequencies[note_index % len(frequencies)]
        for sample_index in range(samples_per_note):
            if len(pcm) >= target_samples:
                break
            phase = sample_index / SAMPLE_RATE
            sample_value = 128 + int(58 * math.sin(2 * math.pi * frequency * phase))
            pcm.append(max(0, min(255, sample_value)))
        note_index += 1

    data_size = len(pcm)
    riff_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        SAMPLE_RATE,
        SAMPLE_RATE,
        1,
        8,
        b"data",
        data_size,
    )
    return header + pcm


def create_audio_output():
    if audiobusio is not None and all(
        hasattr(board, name) for name in ("I2S_BCLK", "I2S_WCLK", "I2S_DOUT")
    ):
        try:
            return audiobusio.I2SOut(board.I2S_BCLK, board.I2S_WCLK, board.I2S_DOUT), "i2s"
        except Exception as exc:
            print("[WARN] I2SOut selhal:", exc)

    if audiopwmio is not None:
        for pin_name in ("SPEAKER", "BUZZER", "A0"):
            if hasattr(board, pin_name):
                try:
                    return audiopwmio.PWMAudioOut(getattr(board, pin_name)), f"pwm:{pin_name}"
                except Exception as exc:
                    print(f"[WARN] PWMAudioOut přes {pin_name} selhal:", exc)

    return None, None


def cleanup_audio_output(audio_out):
    if audio_out is None:
        return

    for method_name in ("stop", "deinit"):
        method = getattr(audio_out, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass


def main():
    print("=========================================")
    print("        DIAGNOSTIKA AUDIO VÝSTUPU       ")
    print("=========================================")

    audio_out = None
    wav_path = TEMP_WAV_PATH

    try:
        gc.collect()

        print("\n[1/4] Inicializuji audio výstup...")
        audio_out, backend = create_audio_output()
        if audio_out is None:
            print("[ERR] Nepodařilo se najít podporovaný audio výstup na této desce.")
            return
        print(f"[OK] Audio výstup inicializován ({backend}).")

        print("\n[2/4] Generuji 5s tónovou stupnici do paměti...")
        wav_data = generate_wav_bytes()
        print(f"[OK] Vygenerováno {len(wav_data)} bajtů WAV dat v RAM.")

        print("\n[3/4] Zápis dočasného souboru a přehrání...")
        try:
            with open(wav_path, "wb") as wav_file:
                wav_file.write(wav_data)

            if audiocore is None:
                print("[ERR] Chybí audiocore, soubor nelze přehrát.")
                return

            with open(wav_path, "rb") as wav_file:
                sample = audiocore.WaveFile(wav_file)
                audio_out.play(sample)
                while getattr(audio_out, "playing", False):
                    time.sleep(0.05)
            print("[OK] Přehrávání dokončeno.")
        finally:
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
                    print("[OK] Dočasný WAV soubor byl smazán.")
            except Exception as exc:
                print("[WARN] Mazání dočasného souboru selhalo:", exc)

        print("\n[4/4] Čistím výstup a uvolňuji paměť...")
    finally:
        cleanup_audio_output(audio_out)
        audio_out = None
        gc.collect()
        print("[OK] Audio výstup byl bezpečně uvolněn.")

    print("\n=========================================")
    print("      DIAGNOSTIKA AUDIO DOKONČENA       ")
    print("=========================================")


if __name__ == "__main__":
    main()