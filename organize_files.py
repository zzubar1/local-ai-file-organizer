"""
@file organize_files.py
@description Scans a folder, sends the full file collection to a locally-running
    Ollama model in a single pass, and sorts files into AI-generated category
    subfolders based on their content.
@dependencies requests (HTTP calls to the local Ollama server), Ollama itself
    (must be installed and running separately, see README.md)

Part of: AI File Organizer (Local, via Ollama)
Architectural Layer: CLI script / single entry point
"""

import os
import shutil
import requests
from pathlib import Path
import json
import time
import re
from typing import Any, Dict, Optional


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"  # Small model chosen as the default so this runs on CPU-only
                             # machines; swap for a larger model (e.g. qwen2.5:7b) for
                             # better classification accuracy at the cost of speed.

# WHY: These rules are handed to the model verbatim as part of the prompt, not just
# used for our own reference -- editing this string directly changes how the AI
# decides to group files. Keep it prescriptive and unambiguous, since a 3B-parameter
# model follows vague instructions poorly.
CLASSIFICATION_RULES = """
Organize files by their main subject or purpose.

- Group related files together using broad, useful categories.
- Do not create a category for only one file unless there is no sensible group.
- Do not make categories so broad that unrelated subjects are mixed together.
- Do not make categories so specific that one topic detail becomes its own folder.
- Use the majority of the file's content, not one isolated word or the filename alone.
- Keep category names short: no more than three words.
- Use no more than 12 categories across the collection.
- Use Other when the content is mixed, unclear, too short, or cannot be read.
- Never create a new category based only on a file extension.
"""

# NOTE: Only extensions in this set are opened and read as text. Anything else is
# still included in the collection and classified, but using only its filename and
# extension as context (see analyze_collection) -- this avoids trying to decode
# binary formats (images, PDFs, executables, etc.) as UTF-8 text.
TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".c", ".h",
    ".cpp", ".hpp", ".java", ".cs", ".go", ".rs", ".sql", ".sh", ".bat",
    ".ps1", ".toml", ".ini", ".cfg", ".log",
}


def ask_local_ai(prompt: str, retries: int = 2) -> dict:
    """
    Send a prompt to the local Ollama server and parse its JSON response.

    @param {str} prompt - The full prompt text to send to the model.
    @param {int} retries - Number of additional attempts after the first, used
        for both malformed-JSON responses and transient connection errors.
    @returns {dict} The parsed JSON object returned by the model.
    @throws {json.JSONDecodeError} If every attempt returns text that isn't valid JSON.
    @throws {requests.exceptions.RequestException} If every attempt fails to reach Ollama
        (e.g. the server isn't running, or the requested model isn't pulled).

    @example
    result = ask_local_ai('Return {"greeting": "hello"} as JSON.')
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 2):  # +2: one initial attempt plus `retries` retries
        try:
            response = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                timeout=120,  # NOTE: local inference on a 3B model can be slow on CPU-only
                              # hardware, especially with a large file collection in the prompt.
            )
            response.raise_for_status()
            return json.loads(response.json()["response"])
        except json.JSONDecodeError as e:
            # WHY: small local models sometimes wrap valid-looking JSON in extra prose,
            # or truncate output, even with "format": "json" set. A short retry loop
            # recovers most of these without failing the whole run.
            last_error = e
            time.sleep(0.5)
        except requests.exceptions.RequestException as e:
            last_error = e
            time.sleep(1.0)
    # WHY: re-raise rather than silently returning a default here -- the caller
    # (analyze_collection) needs to distinguish "AI gave a bad answer" from
    # "AI never answered" so it can report a clear failure instead of guessing.
    raise last_error if last_error else RuntimeError("Unknown error contacting Ollama")


class TextFileOrganizer:
    """Reads, classifies, and moves files from a source folder into category
    subfolders within an output folder, using a local Ollama model."""

    def __init__(self, source_folder: str, output_folder: str):
        """
        @param {str} source_folder - Folder to scan (recursively) for files to sort.
        @param {str} output_folder - Folder where category subfolders are created.
            Created automatically if it doesn't already exist.
        """
        self.source_folder = Path(source_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.rules = CLASSIFICATION_RULES.strip()
        self.discovered_categories = {"Other"}

    def analyze_collection(self, files_and_contents: list) -> Dict[str, Any]:
        """
        Classify every file in the collection in a single AI call.

        WHY: files are analyzed together, rather than one at a time, so the model
        can compare them and group related content into shared categories -- a
        per-file loop would have no way to notice that two files belong together.

        @param {list} files_and_contents - List of dicts with keys "path" (Path)
            and "content" (str or None if the file wasn't read as text).
        @returns {Dict[str, Any]} Dict with:
            - "assignments": filename -> category name, covering every input file.
            - "categories": cleaned list of {name, files, reasoning} groups actually used.
        @throws {ValueError} If the model's response doesn't contain a categories list.
        """
        file_descriptions = []
        for index, item in enumerate(files_and_contents, 1):
            file_path = item["path"]
            content = item["content"] or "[Content could not be read; use the filename and extension as context.]"
            # NOTE: content is capped at 4000 chars per file so a handful of large
            # files can't blow out the model's context window and crowd out the
            # rest of the collection.
            file_descriptions.append(
                f"FILE {index}: {file_path.name}\n"
                f"Extension: {file_path.suffix or '[none]'}\n"
                f"Content:\n{content[:4000]}"
            )
        collection_text = "\n\n---\n\n".join(file_descriptions)

        prompt = f"""You are organizing a collection of files into folders.

Your job is to analyze ALL files together BEFORE assigning any folder.

Follow these rules:
{self.rules}

Important:
- Compare files with one another.
- Files about the same subject or closely related subject should share a folder.
- Files about unrelated subjects should be placed in different folders.
- Do NOT classify files one at a time.
- Create the smallest sensible set of broad categories.
- Use a maximum of 12 categories.
- Category names must be no more than 3 words.
- Every file must appear exactly once in the output.
- Do not move or modify any files yourself.

Return JSON only in exactly this shape:
{{
    "categories": [
        {{
            "name": "short category name",
            "files": ["exact_filename_1.txt", "exact_filename_2.txt"],
            "reasoning": "brief explanation of why these files belong together"
        }}
    ]
}}

Here is the COMPLETE FILE COLLECTION:

{collection_text}
"""
        result = ask_local_ai(prompt)
        categories = result.get("categories", [])
        if not isinstance(categories, list):
            raise ValueError("AI did not return a valid categories list")

        valid_names = {item["path"].name for item in files_and_contents}
        assignments = {}
        cleaned_categories = []

        for category_data in categories:
            if not isinstance(category_data, dict):
                continue

            category = str(category_data.get("name", "Other")).strip()
            # WHY: strip characters that are illegal in Windows/macOS/Linux folder
            # names -- the model isn't aware of filesystem naming rules, so this
            # sanitization has to happen on our side before we use the name as a path.
            category = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', category)
            category = re.sub(r'\s+', ' ', category).strip('. ')
            if not category or len(category.split()) > 3:
                category = "Other"

            filenames = category_data.get("files", [])
            if not isinstance(filenames, list):
                filenames = []

            clean_files = []
            for filename in filenames:
                filename = str(filename)
                # WHY: `filename not in assignments` guards against the model listing
                # the same file under two different categories -- first assignment wins.
                if filename in valid_names and filename not in assignments:
                    assignments[filename] = category
                    clean_files.append(filename)

            if clean_files:
                cleaned_categories.append({
                    "name": category,
                    "files": clean_files,
                    "reasoning": str(category_data.get("reasoning", ""))
                })

        # WHY: if the model omits a file from its response entirely (rather than
        # misclassifying it), it must still end up somewhere -- falling back to
        # "Other" guarantees every input file gets moved, never silently dropped.
        for filename in valid_names:
            if filename not in assignments:
                assignments[filename] = "Other"

        self.discovered_categories = {c["name"] for c in cleaned_categories}
        self.discovered_categories.add("Other")

        return {"assignments": assignments, "categories": cleaned_categories}

    def create_category_folder(self, category: str) -> Path:
        """
        @param {str} category - Sanitized category name.
        @returns {Path} Path to the (now-existing) subfolder for this category.
        """
        category_folder = self.output_folder / category
        category_folder.mkdir(parents=True, exist_ok=True)
        return category_folder

    def move_file(self, file_path: Path, category: str) -> bool:
        """
        Move a single file into its assigned category folder.

        @param {Path} file_path - Current location of the file.
        @param {str} category - Category name (folder will be created if needed).
        @returns {bool} True if the move succeeded, False otherwise.
        """
        try:
            category_folder = self.create_category_folder(category)
            destination = category_folder / file_path.name
            original_destination = destination
            counter = 1
            # WHY: if two files share a name (e.g. moved from different subfolders
            # of the source into the same category), overwriting one silently would
            # lose data -- appending a counter keeps both instead.
            while destination.exists():
                destination = category_folder / f"{original_destination.stem}_{counter}{original_destination.suffix}"
                counter += 1
            shutil.move(str(file_path), str(destination))
            print(f"  Moved: {file_path.name} -> {category}/")
            return True
        except Exception as e:
            print(f"  Error moving {file_path.name}: {e}")
            return False

    def organize_files(self) -> Dict:
        """
        Run the full pipeline: scan, read, classify, and move.

        @returns {Dict} Stats dict with total_files, processed, failed, and a
            per-category file count breakdown.
        """
        stats = {"total_files": 0, "processed": 0, "failed": 0, "categories": {}}

        output_resolved = self.output_folder.resolve()
        # WHY: the output folder can legally sit inside the source folder (e.g. a
        # "sorted/" subfolder). Excluding anything under output_resolved from the
        # scan prevents the script from re-processing files it already moved on
        # a previous run.
        files = [
            path for path in self.source_folder.rglob("*")
            if path.is_file() and output_resolved not in path.resolve().parents
        ]
        stats["total_files"] = len(files)
        print(f"Found {len(files)} files to process")
        if not files:
            return stats

        # Read everything first -- classification needs every file's content
        # available up front (see analyze_collection), not one at a time.
        files_and_contents = []
        for file_path in files:
            try:
                content = None
                if file_path.suffix.lower() in TEXT_EXTENSIONS:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if not content.strip():
                        # NOTE: empty text files are skipped rather than sorted into
                        # "Other" -- there's nothing for the model to classify.
                        continue
                files_and_contents.append({"path": file_path, "content": content})
            except Exception as e:
                print(f"  Could not read {file_path.name}: {e}")

        if not files_and_contents:
            print("No readable files found.")
            stats["failed"] = stats["total_files"]
            return stats

        # Analyze the whole collection at once
        try:
            collection_analysis = self.analyze_collection(files_and_contents)
        except Exception as e:
            # WHY: if classification fails outright, nothing has been moved yet --
            # fail the whole batch cleanly rather than falling back to per-file
            # guesses that would contradict the "analyze together" design.
            print(f"Collection analysis failed: {e}")
            stats["failed"] = len(files_and_contents)
            return stats

        assignments = collection_analysis["assignments"]

        # Move files into place
        for item in files_and_contents:
            file_path = item["path"]
            category = assignments.get(file_path.name, "Other")
            if self.move_file(file_path, category):
                stats["processed"] += 1
            else:
                stats["failed"] += 1

        for category_folder in self.output_folder.iterdir():
            if category_folder.is_dir():
                count = len([f for f in category_folder.iterdir() if f.is_file()])
                if count > 0:
                    stats["categories"][category_folder.name] = count

        return stats

    def print_summary(self, stats: Dict):
        """@param {Dict} stats - Stats dict as returned by organize_files()."""
        print(f"\nTotal files found: {stats['total_files']}")
        print(f"Successfully processed: {stats['processed']}")
        print(f"Failed: {stats['failed']}")
        if stats["categories"]:
            print("Files per category:")
            for category, count in stats["categories"].items():
                print(f"  {category}: {count} files")


def check_ollama_available() -> bool:
    """
    Verify the local Ollama server is reachable before processing any files.

    WHY: without this check, the first sign of trouble would be a confusing
    connection error mid-way through classification -- checking up front gives
    a clear, actionable message instead.

    @returns {bool} True if Ollama responded, False if it couldn't be reached.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
        if not any(OLLAMA_MODEL in m for m in models):
            print(f"WARNING: Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}")
        return True
    except requests.exceptions.RequestException:
        return False


def get_folder_paths():
    """
    Prompt the user for a source and output folder, validating both.

    @returns {tuple[str, str]} (source_folder, output_folder)
    """
    while True:
        source_folder = input("Source folder: ").strip().strip('"')
        if os.path.isdir(source_folder):
            break
        print(f"ERROR: Folder '{source_folder}' does not exist.")

    while True:
        output_folder = input("Output folder: ").strip().strip('"')
        # WHY: source and output must differ -- otherwise category folders would
        # be created inside the very folder being scanned, and re-running the
        # script would try to re-sort its own output.
        if output_folder and Path(output_folder).resolve() != Path(source_folder).resolve():
            break
        print("ERROR: Choose a non-empty output folder different from the source folder.")

    return source_folder, output_folder


def main():
    """Entry point: validate the environment, gather input, and run the organizer."""
    try:
        if not check_ollama_available():
            print("ERROR: Could not reach Ollama at http://localhost:11434")
            return

        source_folder, output_folder = get_folder_paths()
        organizer = TextFileOrganizer(source_folder, output_folder)
        stats = organizer.organize_files()
        organizer.print_summary(stats)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()