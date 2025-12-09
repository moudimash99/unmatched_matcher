import json
import os
import re
from pathlib import Path

import requests

JSON_FILE = "hero_avatars.json"   # your JSON file
OUTPUT_DIR = Path("pics")     # folder to save images

def slugify(name: str) -> str:
    """Make a safe filename from fighter name."""
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)     # remove weird chars
    name = re.sub(r"\s+", "_", name)         # spaces -> _
    name = re.sub(r"_+", "_", name)          # collapse multiple _
    return name or "image"

def main():
    # Load mapping of {fighter_name: image_url}
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, url in data.items():
        slug = slugify(name)
        # Try to keep extension from URL, fallback to .jpg
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        filename = OUTPUT_DIR / f"{slug}{ext}"

        print(f"Downloading {name} -> {filename}")

        try:
            resp = requests.get(
                url,
                timeout=20,
                headers={
                    # Some CDNs like having a UA
                    "User-Agent": "Mozilla/5.0 (compatible; fighter-image-downloader/1.0)"
                },
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  !! Failed to download {name}: {e}")
            continue

        with open(filename, "wb") as img_file:
            img_file.write(resp.content)

    print("Done ✅")

if __name__ == "__main__":
    main()
