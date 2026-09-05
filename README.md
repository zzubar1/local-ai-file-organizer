# AI File Organizer (Local, via Ollama)

A Python script that reads all the files in a folder, uses a locally-running AI model to figure out what they're about, and sorts them into categorized subfolders — no cloud API, no API key, everything runs on your own machine.

## How it works

1. Scans a source folder (recursively) for files.
2. Reads the text content of supported file types.
3. Sends the whole collection to a local AI model (via [Ollama](https://ollama.com)) in one pass, so it can group related files together rather than classifying them one at a time.
4. Moves each file into a category subfolder inside your chosen output folder.

Nothing is moved until the AI has classified the entire collection, and no file leaves your computer — everything happens locally.

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com) installed and running
- The `requests` Python package

## Setup

### 1. Install Ollama

Ollama runs the AI model locally on your machine.

- **Windows / macOS**: download the installer from [ollama.com](https://ollama.com/download) and run it.
- **Linux**:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

Verify it installed correctly:
```bash
ollama -v
```

### 2. Pull the model

This script uses `qwen2.5:3b` by default (a small, fast model — good for most machines including laptops without a GPU). Pull it with:

```bash
ollama pull qwen2.5:3b
```

This downloads a few GB, so it may take a few minutes.

> **Want more accurate categorization?** You can swap in a larger model like `qwen2.5:7b` by changing the `OLLAMA_MODEL` variable near the top of the script, then running `ollama pull qwen2.5:7b`. Larger models are slower but generally better at following the JSON formatting and grouping instructions.

### 3. Make sure Ollama is running

Installing Ollama on Windows/macOS typically starts it automatically in the background (look for its icon in your system tray/menu bar). If it's not running, start it manually:

```bash
ollama serve
```
Leave that terminal window open — the script talks to Ollama over `http://localhost:11434`.

### 4. Install Python dependencies

Clone this repo, then from the project folder run:

```bash
pip install -r requirements.txt
```

(or just `pip install requests` if you don't have a requirements file)

## Usage

Run the script:

```bash
python organize_files.py
```

You'll be prompted for:
- **Source folder** — the folder containing the files you want organized
- **Output folder** — where the sorted/categorized folders should be created (must be different from the source folder)

The script will scan, analyze, and move your files, printing progress as it goes.

## Notes

- Supported text-based file types include `.txt`, `.md`, `.py`, `.js`, `.json`, `.csv`, `.html`, `.css`, and several other common code/text formats (see `TEXT_EXTENSIONS` in the script for the full list). Other file types are still sorted, using their filename/extension as context.
- The AI creates at most 12 categories, using an "Other" category as a catch-all for unclear or unrelated content.
- If Ollama isn't running or the model isn't pulled, the script will tell you before it starts processing files.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'requests'` | Run `pip install requests`. If using VS Code, make sure the selected Python interpreter matches the one you installed the package into (`Ctrl+Shift+P` → "Python: Select Interpreter"). |
| `404 Client Error` when contacting Ollama | The model specified in `OLLAMA_MODEL` isn't pulled yet. Run `ollama pull <model-name>`. |
| Connection refused / can't reach Ollama | Ollama isn't running. Start it with `ollama serve` or open the Ollama app. |

## License

MIT (or your preferred license — add a `LICENSE` file to the repo)
