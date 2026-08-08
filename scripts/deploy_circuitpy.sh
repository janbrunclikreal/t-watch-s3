#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="${SOURCE_DIR:-$ROOT_DIR/}"
SERIAL_PORT="${SERIAL_PORT:-}"
DRY_RUN="${DRY_RUN:-0}"
REQUIRE_SERIAL="${REQUIRE_SERIAL:-0}"
WEBSERIAL_BREAK="${WEBSERIAL_BREAK:-0}"

find_circuitpy_mount() {
  if [[ -n "${CIRCUITPY_MOUNT:-}" ]]; then
    if [[ -d "$CIRCUITPY_MOUNT" ]]; then
      printf '%s\n' "$CIRCUITPY_MOUNT"
      return 0
    fi
    echo "ERROR: CIRCUITPY_MOUNT je nastaveno, ale cesta neexistuje: $CIRCUITPY_MOUNT" >&2
    return 1
  fi

  local candidates=(
    "/mnt/chromeos/removable/CIRCUITPY"
    "/media/$USER/CIRCUITPY"
    "/run/media/$USER/CIRCUITPY"
  )

  local path
  for path in "${candidates[@]}"; do
    if [[ -d "$path" ]]; then
      printf '%s\n' "$path"
      return 0
    fi
  done

  echo "ERROR: CIRCUITPY mount nebyl nalezen. Nastav CIRCUITPY_MOUNT=/cesta/k/CIRCUITPY" >&2
  return 1
}

auto_detect_serial_port() {
  local dev
  for dev in /dev/ttyACM* /dev/ttyUSB*; do
    if [[ -e "$dev" ]]; then
      printf '%s\n' "$dev"
      return 0
    fi
  done
  return 1
}

interrupt_circuitpython() {
  local port="$1"

  if [[ ! -e "$port" ]]; then
    echo "WARN: Serial port neexistuje: $port. Přeskakuji Ctrl+C." >&2
    return 0
  fi

  if ! command -v stty >/dev/null 2>&1; then
    echo "WARN: stty není dostupné. Přeskakuji Ctrl+C přes serial." >&2
    return 0
  fi

  echo "INFO: Posílám Ctrl+C na $port (zastavení běžícího interpretu)."
  if ! stty -F "$port" raw -echo 115200 min 0 time 5; then
    echo "WARN: Nepodařilo se nastavit parametry serial portu. Přeskakuji Ctrl+C." >&2
    return 0
  fi

  # Pošli Ctrl+C vícekrát, aby REPL spolehlivě přerušil code.py smyčku.
  printf '\003\003\003' >"$port" || true
}

assert_mount_is_writable() {
  local mount_path="$1"

  local mount_opts=""
  mount_opts="$(awk -v target="$mount_path" '$2==target{print $4; exit}' /proc/mounts || true)"
  if [[ -n "$mount_opts" && (",$mount_opts," == *,ro,* ) ]]; then
    echo "ERROR: CIRCUITPY je přimountovaný read-only ($mount_path)." >&2
    echo "TIP: Odpoj a znovu připoj hodinky, případně restartuj zařízení." >&2
    return 1
  fi

  local test_file="$mount_path/.sync_write_test_$$"
  if ! echo "write-test" >"$test_file" 2>/dev/null; then
    echo "ERROR: CIRCUITPY není zapisovatelný (write test selhal)." >&2
    echo "TIP: Zkontroluj boot.py, storage mount mód a USB připojení." >&2
    return 1
  fi
  rm -f "$test_file"
}

require_tools() {
  if ! command -v rsync >/dev/null 2>&1; then
    echo "ERROR: rsync není nainstalovaný." >&2
    echo "TIP: sudo apt install rsync" >&2
    return 1
  fi
}

run_rsync() {
  local source_dir="$1"
  local target_dir="$2"

  local -a rsync_opts=(
    -rltv
    --delete
    --modify-window=1
    --no-perms
    --no-owner
    --no-group
    --exclude=.git/
    --exclude=.gitignore
    --exclude=.vscode/
    --exclude=README.md
    --exclude=LICENSE
    --exclude=test/
    --exclude=settings.toml
    --exclude=kroky_db.json
    --exclude=boot_out.txt
    --exclude=scripts/
    --filter=P\ .fseventsd
    --filter=P\ .Trashes
    --filter=P\ .Trash-1000
    --filter=P\ .metadata_never_index
  )

  if [[ "$DRY_RUN" == "1" ]]; then
    rsync_opts+=(--dry-run)
    echo "INFO: DRY_RUN=1, změny se pouze vypíšou."
  fi

  rsync "${rsync_opts[@]}" "$source_dir" "$target_dir"
}

manual_break_via_webserial() {
  echo "INFO: WEBSERIAL_BREAK=1: přeruš běžící program v WebSerial konzoli (Ctrl+C)."
  echo "INFO: Až uvidíš REPL prompt, potvrď pokračování klávesou Enter."
  read -r -p "Pokračovat v deploy? [Enter] " _
}

TARGET_DIR="$(find_circuitpy_mount)"

require_tools

if [[ "$WEBSERIAL_BREAK" == "1" ]]; then
  manual_break_via_webserial
else
  if [[ -z "$SERIAL_PORT" ]]; then
    SERIAL_PORT="$(auto_detect_serial_port || true)"
  fi

  if [[ -n "$SERIAL_PORT" ]]; then
    interrupt_circuitpython "$SERIAL_PORT"
  else
    if [[ "$REQUIRE_SERIAL" == "1" ]]; then
      echo "ERROR: Serial port nebyl nalezen a REQUIRE_SERIAL=1." >&2
      echo "TIP: Přepni USB zařízení do Linuxu a nastav SERIAL_PORT=/dev/ttyACM0 (nebo /dev/ttyUSB0)." >&2
      exit 1
    fi
    echo "INFO: Serial port nebyl nalezen. Pokračuji bez Ctrl+C (Chromebook režim)." >&2
  fi
fi

assert_mount_is_writable "$TARGET_DIR"

echo "INFO: Synchronizuji $SOURCE_DIR -> $TARGET_DIR"
run_rsync "$SOURCE_DIR" "$TARGET_DIR"

echo "OK: Deploy dokončen."