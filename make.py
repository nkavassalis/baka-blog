import math
import hashlib
import json
import subprocess
import markdown
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

CONFIG_PATH = "config.yaml"
HASHES_PATH = ".file_hashes.json"
CONTENT_DIR = Path("content/posts")
CONTENT_IMG_DIR = Path("content/images")
IMAGE_DIR = Path("static/images")
OUTPUT_DIR = Path("dist")
TEMPLATE_DIR = Path("templates")

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def compute_hash(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def load_hashes():
    return json.load(open(HASHES_PATH)) if Path(HASHES_PATH).exists() else {}

def save_hashes(hashes):
    with open(HASHES_PATH, 'w') as f:
        json.dump(hashes, f, indent=2)

def build_content():
    posts = []
    md = markdown.Markdown(extensions=['meta'])
    for md_file in CONTENT_DIR.glob("*.md"):
        html = md.convert(md_file.read_text())
        metadata = {k: v[0] for k, v in md.Meta.items()}
        slug = md_file.stem
        date_obj = datetime.strptime(metadata['date'], "%Y-%m-%d")
        metadata['date_readable'] = date_obj.strftime("%B %d, %Y")
        posts.append({"content": html, "meta": metadata, "slug": slug})
    return sorted(posts, key=lambda x: x['meta']['date'], reverse=True)

def render_templates(posts, config):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    POSTS_PER_PAGE = config['website']['posts_per_page']

    total_pages = math.ceil(len(posts) / POSTS_PER_PAGE)

    index_template = env.get_template("index.html")
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        paginated_posts = posts[start_idx:end_idx]

        page_filename = "index.html" if page_num == 1 else f"page{page_num}.html"
        (OUTPUT_DIR / page_filename).write_text(
            index_template.render(
                posts=paginated_posts,
                config=config,
                current_page=page_num,
                total_pages=total_pages
            )
        )

    post_template = env.get_template("post.html")
    posts_dir = OUTPUT_DIR / "posts"
    posts_dir.mkdir(exist_ok=True)
    for post in posts:
        post_file = posts_dir / f"{post['slug']}.html"
        post_file.write_text(post_template.render(post=post, config=config))


def copy_static_assets():
    assets_dir = OUTPUT_DIR / "images"
    assets_dir.mkdir(exist_ok=True, parents=True)
    for image in IMAGE_DIR.glob("*.*"):
        (assets_dir / image.name).write_bytes(image.read_bytes())
    (OUTPUT_DIR / "style.css").write_text((Path("static/style.css")).read_text())

def copy_content_images():
    output_images_dir = OUTPUT_DIR / "images"
    output_images_dir.mkdir(exist_ok=True, parents=True)
    for image in CONTENT_IMG_DIR.glob("*.*"):
        (output_images_dir / image.name).write_bytes(image.read_bytes())

def sync_s3_and_invalidate(config):
    bucket = config['aws']['s3_bucket']
    dist_id = config['aws']['cloudfront_dist_id']
    subprocess.run(["aws", "s3", "sync", str(OUTPUT_DIR), f"s3://{bucket}", "--acl", "public-read"], check=True)
    subprocess.run(["aws", "cloudfront", "create-invalidation", "--distribution-id", dist_id, "--paths", "/*"], check=True)
    print("Upload complete and CloudFront invalidated.")

def main():
    config = load_config()
    hashes = load_hashes()

    current_hashes = {
        "index_template": compute_hash(TEMPLATE_DIR / "index.html"),
        "post_template": compute_hash(TEMPLATE_DIR / "post.html"),
        "style": compute_hash(Path("static/style.css")),
        **{str(p): compute_hash(p) for p in CONTENT_DIR.glob("*.md")},
        **{str(p): compute_hash(p) for p in IMAGE_DIR.glob("*.*")},
        **{str(p): compute_hash(p) for p in CONTENT_IMG_DIR.glob("*.*")}
    }

    if hashes != current_hashes:
        posts = build_content()
        render_templates(posts, config)
        copy_static_assets()
        copy_content_images()
        sync_s3_and_invalidate(config)
        save_hashes(current_hashes)
        print("Site rebuilt and deployed.")
    else:
        print("No changes detected; skipping build.")

if __name__ == "__main__":
    main()

