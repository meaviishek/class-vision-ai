"""Download the two face models (about 39 MB) into ./models.   Run:  python scripts/download_models.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.vision import models  # noqa: E402


def show(name: str, done: int, total: int) -> None:
    pct = f"{100 * done // total}%" if total else f"{done // 1024} KB"
    print(f"\r{name}: {pct}   ", end="", flush=True)


def main() -> int:
    todo = models.missing_models()
    if not todo:
        print("Models are already installed in", models.MODELS_DIR)
        return 0
    print("Downloading:", ", ".join(todo))
    try:
        models.download_models(show)
    except Exception as exc:
        print(f"\nDownload failed: {exc}")
        print("\nCheck your internet connection and run this again. Or download these files in a browser and put")
        print(f"them in {models.MODELS_DIR}:")
        for name in todo:
            print(f"  {name}")
            for url in models.MODELS[name].urls:
                print(f"    {url}")
        return 1
    print("\nDone. Models saved to", models.MODELS_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
