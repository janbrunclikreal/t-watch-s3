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
TEMP_WAV_PATH = "/_audio_diag.wav"
SAMPLE_BYTES = 2

# T-Watch S3 onboard MAX98357A: BCLK=GPIO48, WCLK=GPIO15, DOUT=GPIO46.
I2S_PIN_NAMES = (
    ("I2S_BCLK", "IO48", "GPIO48", "D48"),
    ("I2S_WCLK", "IO15", "GPIO15", "D15"),
    ("I2S_DOUT", "IO46", "GPIO46", "D46"),
)


def build_scale_frequencies():
    base_scale = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    return base_scale + list(reversed(base_scale[:-1]))


def generate_pcm_bytes():
    frequencies = build_scale_frequencies()
    target_samples = int(SAMPLE_RATE * TOTAL_SECONDS)
    samples_per_note = target_samples // len(frequencies)

    pcm = bytearray(target_samples * SAMPLE_BYTES)
    byte_offset = 0
    note_index = 0
    sample_count = 0
    while sample_count < target_samples:
        frequency = frequencies[note_index % len(frequencies)]
        for sample_index in range(samples_per_note):
            if sample_count >= target_samples:
                break
            phase = sample_index / SAMPLE_RATE
            sample_value = int(12000 * math.sin(2 * math.pi * frequency * phase))
            struct.pack_into("<h", pcm, byte_offset, sample_value)
            byte_offset += SAMPLE_BYTES
            sample_count += 1
        note_index += 1

    return pcm


def create_wav_header(data_size):
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
        SAMPLE_RATE * SAMPLE_BYTES,
        SAMPLE_BYTES,
        SAMPLE_BYTES * 8,
        b"data",
        data_size,
    )
    return header


def resolve_i2s_pins():
    pins = []
    for aliases in I2S_PIN_NAMES:
        pin = None
        for name in aliases:
            if hasattr(board, name):
                pin = getattr(board, name)
                break
        if pin is None:
            return None
        pins.append(pin)
    return pins


def create_audio_output():
    i2s_pins = resolve_i2s_pins()
    if audiobusio is not None and i2s_pins is not None:
        try:
            return audiobusio.I2SOut(*i2s_pins), "MAX98357A I2S"
        except Exception as exc:
            print("[WARN] I2SOut selhal:", exc)

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
            print("[ERR] Nelze otevřít I2S MAX98357A (GPIO48, GPIO15, GPIO46).")
            print("[INFO] Zkontroluj, zda firmware CircuitPython zpřístupňuje IO48, IO15 a IO46.")
            return
        print(f"[OK] Audio výstup inicializován ({backend}).")

        print("\n[2/4] Generuji 5s tónovou stupnici do paměti...")
        pcm_data = generate_pcm_bytes()
        print(f"[OK] Vygenerováno {len(pcm_data)} bajtů PCM dat v RAM/PSRAM.")

        print("\n[3/4] Zápis dočasného souboru a přehrání...")
        try:
            with open(wav_path, "wb") as wav_file:
                wav_file.write(create_wav_header(len(pcm_data)))
                wav_file.write(pcm_data)
            pcm_data = None
            gc.collect()

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