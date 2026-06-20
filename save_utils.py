# save_utils.py
import os
import json
import tempfile

def get_user_data_dir(app_name="Mouse Slip"):
    """Returns the folder path where progress.txt is stored."""
    local = (
        os.getenv("LOCALAPPDATA") or
        os.getenv("APPDATA") or
        os.path.expanduser("~")
    )
    appdir = os.path.join(local, app_name)
    try:
        os.makedirs(appdir, exist_ok=True)
    except Exception:
        appdir = tempfile.gettempdir()
    return appdir

# Progress save file location
SAVE_PATH = os.path.join(get_user_data_dir("Mouse Slip"), "progress.txt")

def default_save():
    """Default save structure used on first run."""
    return {
        "highest_completed_seq_index": -1,
        "best_times": {},
        "difficulty": None,     # "normal" or "hard"
        "hearts": "default"     # "default" or int heart value
    }

def load_save():
    """Loads progress.txt safely, creating defaults as needed."""
    try:
        if not os.path.exists(SAVE_PATH):
            return default_save()

        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure new keys exist for backward compatibility
        if "difficulty" not in data:
            data["difficulty"] = None
        if "hearts" not in data:
            data["hearts"] = "default"

        return data

    except Exception:
        return default_save()

def save_progress(data):
    """Writes the progress dictionary to progress.txt safely."""
    try:
        parent = os.path.dirname(SAVE_PATH)
        os.makedirs(parent, exist_ok=True)
    except Exception:
        pass

    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    except Exception:
        # fallback if something goes wrong
        try:
            fallback = os.path.join(tempfile.gettempdir(), "progress.txt")
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            print("Failed to save progress.")
