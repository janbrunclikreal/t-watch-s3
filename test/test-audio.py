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

SAMPLE_RATE = 8000
TOTAL_SECONDS = 5
SAMPLE_BYTES = 2
TEMP_WAV_PATH = "/_audio_diag.wav"

def build_scale_frequencies():
    base_scale = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    return base_scale + list(reversed(base_scale[:-1]))

def generate_pcm_wav_buffer():
    """Vygeneruje kompletní WAV soubor v RAM/PSRAM."""
    frequencies = build_scale_frequencies()
    target_samples = int(SAMPLE_RATE * TOTAL_SECONDS)
    samples_per_note = target_samples // len(frequencies)

    pcm_data = bytearray(target_samples * SAMPLE_BYTES)
    byte_offset = 0
    note_index = 0
    sample_count = 0

    while sample_count < target_samples:
        frequency = frequencies[note_index % len(frequencies)]
        for sample_index in range(samples_per_note):
            if sample_count >= target_samples:
                break
            phase = sample_index / SAMPLE_RATE
            sample_value = int(10000 * math.sin(2 * math.pi * frequency * phase))
            struct.pack_into("<h", pcm_data, byte_offset, sample_value)
            byte_offset += SAMPLE_BYTES
            sample_count += 1
        note_index += 1

    data_size = len(pcm_data)
    riff_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        1,  # Mono
        SAMPLE_RATE,
        SAMPLE_RATE * SAMPLE_BYTES,
        SAMPLE_BYTES,
        SAMPLE_BYTES * 8,
        b"data",
        data_size,
    )

    return header + pcm_data

def main():
    print("=========================================")
    print("    DIAGNOSTIKA AUDIO VÝSTUPU T-WATCH S3  ")
    print("=========================================")

    audio_out = None
    wav_bytes = None
    gc.collect()

    print("\n[1/4] Inicializuji I2S (MAX98357A)...")
    try:
        audio_out = audiobusio.I2SOut(board.I2S_BCK, board.I2S_WS, board.I2S_DOUT)
        print("[OK] I2S sběrnice otevřena.")
    except Exception as exc:
        print("[ERR] Nelze otevřít I2S:", exc)
        return

    print("\n[2/4] Generuji 5s WAV tónovou stupnici do RAM/PSRAM...")
    wav_bytes = generate_pcm_wav_buffer()
    print(f"[OK] Vygenerováno {len(wav_bytes)} B kompletního WAVu v RAM.")

    print("\n[3/4] Zapisuji dočasný WAV soubor a přehrávám jej...")
    try:
        if audiocore is None:
            print("[ERR] Chybí modul audiocore.")
            return

        try:
            os.remove(TEMP_WAV_PATH)
        except OSError:
            pass

        with open(TEMP_WAV_PATH, "wb") as wav_file:
            wav_file.write(wav_bytes)
        wav_bytes = None
        gc.collect()

        with open(TEMP_WAV_PATH, "rb") as wav_file:
            wave_obj = audiocore.WaveFile(wav_file)
            audio_out.play(wave_obj)
            while audio_out.playing:
                time.sleep(0.05)

        print("[OK] Přehrávání dokončeno!")
    except Exception as e:
        print("[ERR] Přehrávání selhalo:", e)
    finally:
        try:
            os.remove(TEMP_WAV_PATH)
            print("[OK] Dočasný WAV soubor byl smazán.")
        except OSError as exc:
            print("[WARN] Mazání dočasného WAV souboru selhalo:", exc)

        print("\n[4/4] Uvolňuji I2S a paměť...")
        if audio_out is not None:
            try:
                audio_out.stop()
            except Exception:
                pass
            audio_out.deinit()
        wav_bytes = None
        gc.collect()
        print("[OK] I2S uvolněno.")

    print("\n=========================================")
    print("            TEST DOKONČEN                ")
    print("=========================================")

if __name__ == "__main__":
    main()