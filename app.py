from flask import Flask, request, jsonify, send_from_directory, render_template
from pathlib import Path
import yaml
from datetime import datetime
import subprocess
from PIL import Image
import io
import uuid

CONFIG_PATH = Path("config.yaml")

# Load config.yaml
if CONFIG_PATH.exists():
    with open(CONFIG_PATH) as f:
        CONFIG = yaml.safe_load(f)
else:
    CONFIG = {}

EDITOR_HOST = CONFIG.get("editor", {}).get("host", "127.0.0.1")
EDITOR_PORT = CONFIG.get("editor", {}).get("port", 5000)

app = Flask(__name__)

POSTS_DIR = Path("content/posts")
IMAGES_DIR = Path("content/images")
POSTS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

MAX_WIDTH = CONFIG.get("images", {}).get("max_width", 1280)
MAX_HEIGHT = CONFIG.get("images", {}).get("max_height", 1280)
JPEG_QUALITY = CONFIG.get("images", {}).get("jpeg_quality", 80)

def list_posts():
    posts = []
    for f in POSTS_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        metadata = {}
        if content.startswith("---"):
            try:
                _, meta_block, _ = content.split("---", 2)
                metadata = yaml.safe_load(meta_block)
            except Exception:
                pass
        date_str = metadata.get("date", "")
        
        try:
            date_obj = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
            date_str = date_obj.strftime("%Y-%m-%d")
        except Exception:
            pass
        posts.append({
            "filename": f.name,
            "title": metadata.get("title", f.stem),
            "date": date_str
        })
    return sorted(posts, key=lambda x: x["date"], reverse=True)


@app.route("/")
def index():
    return render_template("editor.html")


@app.route("/api/posts")
def api_posts():
    return jsonify(list_posts())


@app.route("/api/post/<filename>", methods=["GET"])
def api_get_post(filename):
    path = POSTS_DIR / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify({"content": path.read_text(encoding="utf-8")})


@app.route("/api/post/<filename>", methods=["POST"])
def api_save_post(filename):
    data = request.json
    (POSTS_DIR / filename).write_text(data["content"], encoding="utf-8")
    return jsonify({"status": "saved"})


@app.route("/api/delete/<filename>", methods=["DELETE"])
def api_delete_post(filename):
    path = POSTS_DIR / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    path.unlink()
    return jsonify({"status": "deleted"})


@app.route("/api/new", methods=["POST"])
def api_new_post():
    data = request.json
    title = data.get("title", "Untitled Post")
    slug = title.lower().replace(" ", "-")
    filename = f"{slug}.md"
    today = datetime.now().strftime("%Y-%m-%d")
    template = f"""---
title: {title}
subtitle: Write your description here.
date: {today}
unlisted: false
---

Write your content here.
"""
    (POSTS_DIR / filename).write_text(template, encoding="utf-8")
    return jsonify({"filename": filename})


@app.route("/api/upload_image", methods=["POST"])
def api_upload_image():
    file = request.files["file"]
    unique_name = f"{uuid.uuid4().hex}.jpg"
    save_path = IMAGES_DIR / unique_name

    img = Image.open(file.stream)
    img = img.convert("RGB")  # ensure compatible with JPEG

    img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

    save_path = save_path.with_suffix(".jpg")
    img.save(save_path, "JPEG", quality=JPEG_QUALITY, optimize=True)

    return jsonify({
        "status": "uploaded",
        "path": f"../images/{save_path.name}",
        "filename": save_path.name
    })


@app.route("/api/regenerate", methods=["POST"])
def api_regenerate():
    try:
        result = subprocess.run(
            ["python", "make.py"],
            capture_output=True,
            text=True,
            check=False
        )
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


if __name__ == "__main__":
    print(f"Starting editor on {EDITOR_HOST}:{EDITOR_PORT}")
    app.run(debug=True, host=EDITOR_HOST, port=EDITOR_PORT)

