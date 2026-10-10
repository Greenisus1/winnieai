# WinnieAI

An offline, fullscreen terminal version of a word-graph chatbot. Runs on a headless Raspberry Pi, DietPi, Linux or macOS over SSH. No desktop, browser, API key, network at runtime, GPU or pip packages needed. Python 3 and curses only.

## Install

```sh
wget -O install-winnieai.sh https://raw.githubusercontent.com/Greenisus1/winnieai/main/install.sh && bash install-winnieai.sh
```

On macOS use `curl -fLO` instead of `wget -O`. Run `~/.local/bin/WinnieAI`. With `~/.local/bin` on PATH, `winnieai`, `WinnieAI`, `WINNIEAI` and every other capitalization work. On Debian/DietPi the installer installs Python if needed; sudo is requested only for that system dependency. App files install under your current account, not automatically into someone else's home.

The `app-store.sh` marker lets Pi App Store discover this under Apps. Refresh the store, install WinnieAI, then launch it from Run apps. Its store launcher is always fullscreen. It does not need a separate catalog edit.

## Teach, then ask

- F2 opens a multiline teaching area. Paste text; Ctrl-D learns it. Esc cancels.
- F3 opens the graph. Up/Down select a word, Enter explores it. Mouse clicks also work in terminals supporting mouse events. F4 returns to chat.
- F1 shows help. Resize the terminal freely. Minimum size: 45 columns by 12 rows.
- Chat learns your words AFTER choosing an answer, so the new question does not become its own answer on that turn. Bot output is not used as training data.

Type:

```text
/teach favorite color => My favorite color is blue.
favorite color
/learn Apples grow on trees. Apples are fruit. Pears are fruit too.
/search apples
/graph apples
/read /home/me/notes.txt
/export /home/me/backup.Winnieai
/import /home/me/backup.Winnieai
/stats
/quit
```

`/teach` also corrects a reply for the same question. `/clear YES` deliberately clears local memory. Import replaces rather than merges memory, so export first if you want a backup. Invalid imports leave current memory intact.

## What learning means

Training adds symmetric links between words within a two-word window, keeps sentence/document frequencies, and builds normalized log-TF / smoothed-IDF neighbor vectors. Graph search compares these vectors using cosine similarity. Replies use exact taught question/reply pairs first, then similar taught prompts, then matching learned sentences. Unknown questions are admitted as unknown. Answers show their match type and similarity in the chat log.

This is a small association and retrieval learner, **not a large language model**. It does not reason, browse, verify claims or invent fluent new answers. You can teach a reliable reply explicitly. Sentence retrieval quotes learned material rather than treating it as verified truth.

Memory autosaves after teaching and chatting to `~/.local/share/winnieai/memory.Winnieai` (or `$XDG_DATA_HOME/winnieai/`). Atomic writes use private temporary files. Nothing uploads. Do not put secrets in text you plan to export or share.

Exports contain graph weights, document counts, frequencies, learned sentences and taught replies. Old HTML graph-only `.Winnieai` / JSON exports also import; they cannot restore sentences or replies the old format never saved. Graph labels preserve imported tokens; new text uses Unicode word tokens and strips common stopwords, without the old suffix-cutting that damaged words.

Limits: 100 KB per text import, 10,000 words/sentences/replies, 20 MB per memory import. Large corpora are outside this small Pi-friendly learner's scope.

## Script mode and tests

```sh
python3 winnieai.py --memory /tmp/demo.Winnieai --teach 'capital of France' 'Paris.'
python3 winnieai.py --memory /tmp/demo.Winnieai --ask 'capital of France'
python3 winnieai.py --memory /tmp/demo.Winnieai --learn 'Apples grow on trees.'
python3 winnieai.py --memory /tmp/demo.Winnieai --search apples
python3 -m unittest -v test_winnieai.py
```

The same core powers the terminal UI and script mode. Scripts do not require an interactive terminal. A malformed existing memory file is reported, not silently discarded.
