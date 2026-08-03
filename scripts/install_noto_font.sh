#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for Noto Sans TC (attempts apt first; fallback to direct download)
# Intended to be run as root (systemd oneshot at boot). Creates /var/lib/install_noto_font.done when finished.

MARKER="/var/lib/install_noto_font.done"
if [ -f "$MARKER" ]; then
  echo "Noto Sans TC already installed (marker exists)."
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Exiting." >&2
  exit 1
fi

install_via_apt() {
  echo "Using apt to install fonts-noto-cjk..."
  apt-get update -y
  apt-get install -y fonts-noto-cjk || return 1
  return 0
}

install_via_download() {
  echo "Attempting fallback download of Noto Sans TC OTF..."
  TMPDIR=$(mktemp -d)
  mkdir -p /usr/local/share/fonts/noto-sans-tc
  # try raw GitHub path (best-effort)
  URL="https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Taiwan/NotoSansTC-Regular.otf"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$TMPDIR/NotoSansTC-Regular.otf" || true
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMPDIR/NotoSansTC-Regular.otf" "$URL" || true
  fi

  if [ -f "$TMPDIR/NotoSansTC-Regular.otf" ]; then
    cp "$TMPDIR/NotoSansTC-Regular.otf" /usr/local/share/fonts/noto-sans-tc/
    fc-cache -f -v || true
    rm -rf "$TMPDIR"
    return 0
  fi

  echo "Fallback download failed; please install fonts manually on this distro." >&2
  rm -rf "$TMPDIR"
  return 1
}

echo "Installing Noto Sans TC (one-shot)."

if command -v apt-get >/dev/null 2>&1; then
  if install_via_apt; then
    echo "Installed via apt. Updating font cache..."
    fc-cache -f -v || true
    touch "$MARKER"
    echo "Done."
    exit 0
  else
    echo "apt install failed; trying fallback download..."
  fi
fi

# Try fallback download if apt not available or failed
if install_via_download; then
  touch "$MARKER"
  echo "Done (download fallback)."
  exit 0
fi

echo "All installation methods failed. Exiting with non-zero status." >&2
exit 2
