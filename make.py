import uuid
import math
import hashlib
import json
import subprocess
import markdown
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from xml.sax.saxutils import escape

CONFIG_PATH = "config.yaml"
HASHES_PATH = ".file_hashes.json"
MAPPING_PATH = ".slug_uuid_mapping.json"
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

def load_slug_uuid_mapping():
    if Path(MAPPING_PATH).exists():
        with open(MAPPING_PATH) as f:
            return json.load(f)
    return {}

def save_slug_uuid_mapping(mapping):
    with open(MAPPING_PATH, 'w') as f:
        json.dump(mapping, f, indent=2)

def build_content():
    posts = []
    md = markdown.Markdown(extensions=['meta'])
    slug_uuid_mapping = load_slug_uuid_mapping()

    mapping_changed = False

    for md_file in CONTENT_DIR.glob("*.md"):
        html = md.convert(md_file.read_text())
        metadata = {k: v[0] for k, v in md.Meta.items()}
        slug = md_file.stem

        if slug not in slug_uuid_mapping:
            slug_uuid_mapping[slug] = uuid.uuid4().hex
            mapping_changed = True

        date_obj = datetime.strptime(metadata['date'], "%Y-%m-%d")
        metadata['date_readable'] = date_obj.strftime("%B %d, %Y")

        posts.append({
            "content": html,
            "meta": metadata,
            "slug": slug,
            "uuid": slug_uuid_mapping[slug]
        })

    if mapping_changed:
        save_slug_uuid_mapping(slug_uuid_mapping)

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
        post_file = posts_dir / f"{post['uuid']}.html"
        post_file.write_text(post_template.render(post=post, config=config))

    generate_rss_feed(posts, OUTPUT_DIR, config)

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

def generate_rss_feed(posts, output_dir, config, feed_size=25):
    rss_items = []
    feed_posts = posts[:feed_size]
    base_url = config["website"]["base_url"]
    feed_url = f"{base_url}/feed.xml"

    for post in feed_posts:
        guid_url = f"{base_url}/posts/{post['uuid']}.html"
        title_text = escape(post['meta']['title'])
        description_text = escape(post['meta'].get('description', title_text))

        rss_items.append(f"""
        <item>
            <title>{title_text}</title>
            <link>{guid_url}</link>
            <description>{description_text}</description>
            <pubDate>{datetime.strptime(post['meta']['date'], '%Y-%m-%d').strftime('%a, %d %b %Y 00:00:00 GMT')}</pubDate>
            <guid>{guid_url}</guid>
        </item>""")

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(config["website"]["title"])}</title>
    <link>{base_url}</link>
    <atom:link href="{feed_url}" rel="self" type="application/rss+xml" />
    <description>{escape(config["website"]["description"])}</description>
    {''.join(rss_items)}
  </channel>
</rss>"""

    (output_dir / "feed.xml").write_text(rss_feed, encoding="utf-8")


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

