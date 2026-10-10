#!/bin/sh
set -eu
BASE_URL=https://raw.githubusercontent.com/Greenisus1/winnieai/main
DEST=${WINNIEAI_INSTALL_DIR:-$HOME/.local/share/winnieai-app}
BIN=${WINNIEAI_BIN_DIR:-$HOME/.local/bin}
mkdir -p "$DEST" "$BIN"
fetch() {
    if command -v wget >/dev/null 2>&1; then wget -q -O "$2" "$1";
    elif command -v curl >/dev/null 2>&1; then curl -fLsS "$1" -o "$2";
    else echo 'Install wget or curl first.' >&2; exit 1; fi
}
for file in winnieai.py app-store.sh VERSION; do
    tmp=$(mktemp "$DEST/.download.XXXXXX")
    if fetch "$BASE_URL/$file" "$tmp"; then mv "$tmp" "$DEST/$file";
    else rm -f "$tmp"; exit 1; fi
done
bash "$DEST/app-store.sh" install
# Install all 256 capitalization variants so phone autocorrect is harmless.
python3 - "$DEST" "$BIN" <<'PY'
import itertools, pathlib, shlex, sys
src, bindir=sys.argv[1:]
script='#!/bin/sh\nexec python3 '+shlex.quote(src+'/winnieai.py')+' "$@"\n'
for letters in itertools.product(*[(c.lower(),c.upper()) for c in 'winnieai']):
    path=pathlib.Path(bindir)/''.join(letters)
    path.write_text(script); path.chmod(0o755)
PY
printf '\nInstalled. Run: %s/WinnieAI\n' "$BIN"
case ":$PATH:" in *":$BIN:"*) echo 'You can also run: WinnieAI' ;; *) echo 'For short commands, add $HOME/.local/bin to PATH in your shell profile.' ;; esac
