
# AI File Organizer (Local, via Ollama)

A Python-based file organization tool that uses a locally hosted AI model to analyze file contents and automatically organize them into categorized folders.

Built with Python and [Ollama](https://ollama.com), the application runs entirely on your own computer, without requiring a cloud API, API key, or internet connection after setup.

The tool emphasizes user control and file safety, allowing you to preview proposed changes, adjust classification specificity, and confirm file operations before they're applied.

## How It Works

1. **Scan Files:** Recursively scans a selected source directory, identifying supported files and extracting their contents.
2. **Analyze Content:** Uses a locally running AI model to determine each file's main subject or purpose.
3. **Summarize Large Documents:** For `.txt` files exceeding 10,000 characters, the program summarizes the entire document in chunks to preserve important information throughout the text.
4. **Generate Categories:** Creates a shared set of categories based on the analyzed files, with adjustable grouping specificity.
5. **Preview Organization:** Displays the proposed directory structure, including categories, filenames, and AI confidence levels.
6. **Confirm Changes:** Allows the user to review assignments, make overrides, and approve or cancel file operations.
7. **Organize Files:** Copies or moves files into their assigned folders, protecting against duplicate filenames and recording operations in a journal.

By default, the program operates in **preview-only mode**. Files are not moved unless execution is explicitly requested and confirmed.

## Features

### Local AI Classification
- Uses Ollama with `qwen2.5:3b` by default.
- Analyzes file contents and filenames to determine appropriate categories.
- Processes collections in batches to stay within configurable input limits.
- Supports different locally installed Ollama models.
- Includes an "Other" category for files that cannot be confidently classified.

### Adjustable Classification Specificity
Control how broadly or narrowly the AI groups files using a value between `0.0` and `1.0`.

- **0.0–0.33:** Broad categories that combine related subjects.
- **0.34–0.66:** Balanced grouping between broad and specific topics.
- **0.67–1.0:** More specific categories that distinguish individual subjects.

The default specificity is `0.5`.

The setting adjusts the classification instructions sent to the AI rather than enforcing a fixed number of categories.

### Large Document Summarization
Long `.txt` files can contain important information beyond the beginning of the document.

When a text file exceeds **10,000 characters**, the program uses a map-reduce summarization approach:

1. Splits the document into smaller chunks.
2. Uses the local AI model to summarize each chunk.
3. Combines those summaries into higher-level summaries.
4. Uses the resulting summary for file classification.

This allows information from throughout the document, including its ending, to contribute to classification instead of relying entirely on the first few thousand characters.

The summarization threshold and input-size limits are configurable.

### Directory Tree Preview
Before applying changes, the program displays a tree showing the proposed organization.

Example:

```text
Organized_Files/
├── Programming/ (2 files)
│   ├── python_notes.txt [f1; high confidence]
│   └── example_code.py [f2; high confidence]
├── Finance/ (1 files)
│   └── monthly_budget.csv [f3; medium confidence]
└── Other/ (1 files)
    └── unknown_file.dat [f4; low confidence]
```

Each file is assigned an ID and an AI-generated confidence level.

Users can review the proposed categories and manually override assignments before execution.

### User Confirmation
- Preview mode is enabled by default.
- The `--execute` option enables file operations.
- The program requests confirmation before making changes.
- Users can override individual file assignments.
- The `--yes` option can skip interactive confirmation when used with `--execute`.

### File Safety and Recovery
The program includes several safeguards:

- Duplicate filename handling to avoid overwriting existing files.
- SHA-256 checksum verification during transfers.
- File-change detection between scanning and execution.
- Protection against certain symbolic links and Windows reparse points.
- Operation journals recording file transfers.
- An undo function for restoring completed move operations when recovery checks pass.
- A copy option that preserves the original files.

These safeguards reduce the risk of unintended changes, but important files should still be backed up before testing.

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com) installed and running
- The `requests` Python package

Optional dependencies:
- `pypdf` for extracting text from PDF documents
- `python-docx` for extracting text from Word documents

## Setup

### 1. Install Ollama

Download Ollama from:

https://ollama.com/download

For Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify installation:

```bash
ollama -v
```

### 2. Download the AI Model

The program uses `qwen2.5:3b` by default.

```bash
ollama pull qwen2.5:3b
```

This is a relatively small model suitable for running locally, including on many laptops without dedicated graphics cards.

For potentially better classification accuracy, you can use a larger model such as `qwen2.5:7b`:

```bash
ollama pull qwen2.5:7b
```

Specify it when running the program:

```bash
python organize_files.py --model qwen2.5:7b
```

Larger models generally require more RAM and processing time.

### 3. Start Ollama

Ollama may start automatically after installation.

If it is not already running:

```bash
ollama serve
```

The program communicates with Ollama through:

`http://localhost:11434`

### 4. Install Python Dependencies

Clone the repository:

```bash
git clone https://github.com/zzubar1/local-ai-file-organizer.git
cd local-ai-file-organizer
```

Install the required dependency:

```bash
pip install requests
```

For optional PDF and Word document support:

```bash
pip install pypdf python-docx
```

## Usage

### Basic Usage

Run:

```bash
python organize_files.py
```

You will be prompted to enter:

- **Source folder:** Directory containing files to organize.
- **Output folder:** Directory where categorized files should be placed.

The output directory must be different from the source directory and cannot contain the source directory.

The program will scan, classify, and display the proposed organization without moving anything.

### Preview Files with Custom Specificity

```bash
python organize_files.py "source_folder" "output_folder" --specificity 0.8
```

This requests more specific category grouping while keeping the program in preview-only mode.

### Apply File Organization

```bash
python organize_files.py "source_folder" "output_folder" --execute
```

After displaying the proposed structure, the program requests confirmation before moving files.

### Copy Instead of Move

```bash
python organize_files.py "source_folder" "output_folder" --execute --copy
```

Copies files into categorized folders while retaining the originals.

### Change the Summarization Threshold

```bash
python organize_files.py "source_folder" "output_folder" --summary-threshold 15000
```

Changes the threshold for summarizing long `.txt` files to 15,000 characters.

### Adjust Input Processing Limits

```bash
python organize_files.py "source_folder" "output_folder" --sample-chars 3000 --batch-chars 20000
```

Controls the amount of text sampled and the input budget used when processing file batches.

### Undo File Moves

The program records transfer operations in a `.jsonl` journal inside the output folder.

Preview a restoration:

```bash
python organize_files.py --undo "path_to_journal.jsonl"
```

Apply the restoration:

```bash
python organize_files.py --undo "path_to_journal.jsonl" --execute
```

The undo operation checks file contents and destination conditions before restoring files. It does not overwrite existing files.

### Additional Options

Run:

```bash
python organize_files.py --help
```

To view all available command-line options.

## Supported File Types

The program supports text extraction from common file formats, including:

- Text: `.txt`, `.md`, `.rst`
- Code: `.py`, `.js`, `.ts`, `.cpp`, `.java`, `.html`, `.css`, and others
- Data: `.csv`, `.json`, `.xml`, `.yaml`, `.sql`
- Configuration: `.ini`, `.cfg`, `.toml`
- Documents: `.pdf`, `.docx` (optional dependencies required)

Unsupported formats can still be categorized using their filenames and extensions as context.

PDF and Word document extraction currently uses limited text samples rather than the full-document summarization used for large `.txt` files.

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: requests` | Run `pip install requests` using the same Python environment. |
| Ollama connection refused | Start Ollama using `ollama serve`. |
| Model not found | Run `ollama pull qwen2.5:3b` or install the model specified with `--model`. |
| PDF content not extracted | Install `pypdf`. |
| Word content not extracted | Install `python-docx`. |
| Slow classification | Try a smaller model, reduce input sizes, or process fewer files. |
| Unexpected categories | Adjust `--specificity` or manually override assignments. |
| Files aren't moving | Preview mode is the default; use `--execute` and confirm the operation. |
| Summarization takes too long | Increase the summarization threshold or use a faster local model. |

## Notes and Limitations

- AI-generated classifications are not guaranteed to be accurate.
- Classification specificity provides guidance to the model; results may vary.
- Large-document summarization requires additional inference calls and processing time.
- PDF and Word text extraction are limited to sampled content.
- Undo support applies to recorded move operations and is subject to integrity and path checks.
- Local inference eliminates the need to send documents to an external AI service, but users are responsible for the security of their local system.
- Always test file operations on nonessential files before organizing important documents.

## Technologies Used

- **Python** — File operations, directory traversal, command-line interface, and error handling
- **Ollama** — Local large language model inference
- **Qwen2.5** — Document analysis, summarization, and classification
- **Requests** — Communication with Ollama's local API
- **SHA-256** — File integrity verification

## Project Purpose

This project was developed to explore how locally hosted language models can automate practical tasks while maintaining user control over the results.

The goal is to combine AI-based content understanding with configurable classification, transparent previews, and safer file management.

The project is an ongoing learning experience focused on Python development, local AI integration, automation, and reliability.
