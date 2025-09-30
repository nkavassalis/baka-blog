from flask import Flask, request, jsonify, send_from_directory, render_template
from pathlib import Path
import yaml
from datetime import datetime
import subprocess
from PIL import Image
import uuid
import os

CONFIG_PATH = Path("config.yaml")

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
        slug = f.stem
        posts.append({
            "filename": f.name,
            "title": metadata.get("title", f.stem),
            "date": date_str,
            "slug": slug
        })
    return sorted(posts, key=lambda x: x["date"], reverse=True)

def list_images(slug=None):
    images = []
    if slug:
        folder = IMAGES_DIR / slug
        if not folder.exists():
            return []
        for f in folder.glob("*.*"):
            if f.is_file():
                images.append({
                    "filename": f.name,
                    "url": f"/images/{slug}/{f.name}",
                    "size": f.stat().st_size
                })
    else:
        for folder in IMAGES_DIR.glob("*"):
            if folder.is_dir():
                for f in folder.glob("*.*"):
                    if f.is_file():
                        images.append({
                            "filename": f.name,
                            "url": f"/images/{folder.name}/{f.name}",
                            "size": f.stat().st_size,
                            "slug": folder.name
                        })
    return sorted(images, key=lambda x: x["filename"], reverse=True)

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
    slug = Path(filename).stem
    img_folder = IMAGES_DIR / slug
    if img_folder.exists():
        for f in img_folder.glob("*"):
            f.unlink()
        img_folder.rmdir()
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
    return jsonify({"filename": filename, "slug": slug})

@app.route("/api/upload_image/<slug>", methods=["POST"])
def api_upload_image(slug):
    folder = IMAGES_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    file = request.files["file"]
    unique_name = f"{uuid.uuid4().hex}.jpg"
    save_path = folder / unique_name
    img = Image.open(file.stream)
    img = img.convert("RGB")
    img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)
    img.save(save_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return jsonify({
        "status": "uploaded",
        "path": f"../images/{slug}/{save_path.name}",
        "filename": save_path.name
    })

@app.route("/api/images/<slug>", methods=["GET"])
def api_images(slug):
    return jsonify(list_images(slug))

@app.route("/api/delete_image/<slug>/<filename>", methods=["DELETE"])
def api_delete_image(slug, filename):
    path = IMAGES_DIR / slug / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    path.unlink()
    return jsonify({"status": "deleted"})

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

@app.route("/images/<slug>/<path:filename>")
def serve_image(slug, filename):
    return send_from_directory(IMAGES_DIR / slug, filename)

if __name__ == "__main__":
    print(f"Starting editor on {EDITOR_HOST}:{EDITOR_PORT}")
    app.run(debug=True, host=EDITOR_HOST, port=EDITOR_PORT)

