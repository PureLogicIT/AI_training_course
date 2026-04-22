"""
download_models.py
==================
One-time script to pre-download all models required by Exercise 1.
Run this before starting the app to avoid slow first-run downloads.

Usage:
    python download_models.py
"""

import os
from huggingface_hub import snapshot_download

MODELS = [
    {
        "repo_id": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "local_dir": "./models/SmolLM2-1.7B-Instruct",
        "allow_patterns": ["*.safetensors", "*.json", "*.txt", "tokenizer.model"],
        "ignore_patterns": ["*.bin", "*.gguf"],
        "note": "~3.4 GB — text-generation model",
    },
    {
        "repo_id": "google/flan-t5-base",
        "local_dir": "./models/flan-t5-base",
        "allow_patterns": ["*.safetensors", "*.json", "*.txt", "*.model"],
        "ignore_patterns": ["*.bin", "*.gguf"],
        "note": "~1 GB — summarization model",
    },
    {
        "repo_id": "deepset/roberta-base-squad2",
        "local_dir": "./models/roberta-base-squad2",
        "allow_patterns": ["*.safetensors", "*.json", "*.txt", "*.model"],
        "ignore_patterns": ["*.bin", "*.gguf"],
        "note": "~500 MB — question-answering model",
    },
]


def download_if_needed(repo_id: str, local_dir: str, allow_patterns: list,
                       ignore_patterns: list, note: str) -> None:
    config_path = os.path.join(local_dir, "config.json")
    if os.path.exists(config_path):
        print(f"  [skip] Already present: {local_dir}")
        return

    print(f"  [download] {repo_id}  ({note})")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        allow_patterns=allow_patterns,
        ignore_patterns=ignore_patterns,
    )
    print(f"  [done] Saved to {local_dir}")


if __name__ == "__main__":
    print("Downloading all Exercise 1 models...\n")
    for m in MODELS:
        download_if_needed(**m)
    print("\nAll downloads complete. You can now run: python app.py")
