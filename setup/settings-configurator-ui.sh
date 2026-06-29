#!/usr/bin/env sh
# POSIX convenience launcher for settings-configurator-ui.py.
# Resolves Python, offers package-manager install when Python is missing,
# and runs the wizard after a successful install.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_CMD=""
ARCH=$(uname -m 2>/dev/null || echo unknown)

detect_arch() {
  if command -v dpkg >/dev/null 2>&1; then
    dpkg --print-architecture 2>/dev/null || printf '%s\n' "$ARCH"
  elif command -v rpm >/dev/null 2>&1; then
    rpm --eval '%{_arch}' 2>/dev/null || printf '%s\n' "$ARCH"
  else
    printf '%s\n' "$ARCH"
  fi
}

python_is_supported() {
  "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 14))' >/dev/null 2>&1
}

find_python() {
  if command -v python3 >/dev/null 2>&1 && python_is_supported "$(command -v python3)"; then
    PYTHON_CMD=$(command -v python3)
    return 0
  fi
  if command -v python >/dev/null 2>&1 && python_is_supported "$(command -v python)"; then
    PYTHON_CMD=$(command -v python)
    return 0
  fi
  return 1
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "sudo was not found. Re-run as root or install Python manually."
    return 1
  fi
}

latest_version() {
  if command -v apt-cache >/dev/null 2>&1; then
    apt-cache policy python3 2>/dev/null | sed -n 's/^[[:space:]]*Candidate:[[:space:]]*//p' | head -n 1
  elif command -v dnf >/dev/null 2>&1; then
    dnf info python3 2>/dev/null | awk -F: '/^Version/ {gsub(/^[ \t]+/, "", $2); print $2; exit}'
  elif command -v yum >/dev/null 2>&1; then
    yum info python3 2>/dev/null | awk -F: '/^Version/ {gsub(/^[ \t]+/, "", $2); print $2; exit}'
  elif command -v zypper >/dev/null 2>&1; then
    zypper info python3 2>/dev/null | awk -F: '/^Version/ {gsub(/^[ \t]+/, "", $2); print $2; exit}'
  elif command -v pacman >/dev/null 2>&1; then
    pacman -Si python 2>/dev/null | awk -F: '/^Version/ {gsub(/^[ \t]+/, "", $2); print $2; exit}'
  elif command -v apk >/dev/null 2>&1; then
    apk info -v python3 2>/dev/null | head -n 1 | sed 's/^python3-//'
  else
    return 1
  fi
}

install_python() {
  if command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update && run_as_root apt-get install -y python3 python3-pip python3-venv
  elif command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y python3 python3-pip
  elif command -v yum >/dev/null 2>&1; then
    run_as_root yum install -y python3 python3-pip
  elif command -v zypper >/dev/null 2>&1; then
    run_as_root zypper --non-interactive install python3 python3-pip
  elif command -v pacman >/dev/null 2>&1; then
    run_as_root pacman -Sy --noconfirm python python-pip
  elif command -v apk >/dev/null 2>&1; then
    run_as_root apk add python3 py3-pip
  else
    echo "No supported package manager found."
    return 1
  fi
}

if ! find_python; then
  echo "Python was not found. This wizard requires Python."
  ARCH=$(detect_arch)
  echo "Detected architecture: $ARCH"
  LATEST=$(latest_version || true)
  if [ -n "${LATEST:-}" ]; then
    echo "Latest Python available from your package manager: $LATEST"
  else
    echo "Latest Python available from your package manager: unknown"
  fi
  printf "Install Python now using the system package manager? [y/N] "
  read -r ANSWER
  case "$ANSWER" in
    y|Y|yes|YES)
      echo "Installing Python for this architecture via the system package manager."
      if ! install_python; then
        echo "Could not install Python for architecture $ARCH using the system package manager."
        echo "Cannot continue without Python."
        exit 1
      fi
      ;;
    *)
      echo "Cannot continue without Python."
      exit 1
      ;;
  esac
  if ! find_python; then
    echo "Python installed, but this terminal cannot find it yet."
    echo "Open a new terminal and run this launcher again."
    echo "Cannot continue without Python."
    exit 1
  fi
fi

exec "$PYTHON_CMD" "$SCRIPT_DIR/settings-configurator-ui.py" "$@"
