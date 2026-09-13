import math
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import markdown
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from xml.sax.saxutils import escape

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

def slugify_tag(tag):
    s = re.sub(r'[^a-z0-9]+', '-', tag.lower()).strip('-')
    return s or 'tag'

def parse_tags(meta_values):
    if not meta_values:
        return []
    raw_parts = []
    for value in meta_values:
        raw_parts.extend(value.split(','))
    seen = []
    for part in raw_parts:
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen

def build_content():
    posts = []
    md = markdown.Markdown(extensions=['meta'])
    for md_file in CONTENT_DIR.glob("*.md"):
        html = md.convert(md_file.read_text())
        metadata = {k: v[0] for k, v in md.Meta.items() if k != 'tags'}
        tags = parse_tags(md.Meta.get('tags'))
        slug = md_file.stem
        date_obj = datetime.strptime(metadata['date'], "%Y-%m-%d")
        metadata['date_readable'] = date_obj.strftime("%B %d, %Y")
        posts.append({
            "content": html,
            "meta": metadata,
            "slug": slug,
            "tags": [{"name": t, "slug": slugify_tag(t)} for t in tags],
        })
    return sorted(posts, key=lambda x: x['meta']['date'], reverse=True)

def build_tag_index(posts):
    index = {}
    for post in posts:
        if post['meta'].get('unlisted', '').lower() == 'true':
            continue
        for tag in post['tags']:
            entry = index.setdefault(tag['slug'], {"name": tag['name'], "slug": tag['slug'], "posts": []})
            entry['posts'].append(post)
    return index

def build_tag_cloud(tag_index):
    return [
        {"name": tag['name'], "slug": tag['slug'], "count": len(tag['posts'])}
        for tag in sorted(tag_index.values(), key=lambda t: t['name'].lower())
    ]

def compute_related_posts(post, tag_index, limit):
    sections = []
    for tag in post['tags']:
        entry = tag_index.get(tag['slug'])
        if not entry:
            continue
        related = [p for p in entry['posts'] if p['slug'] != post['slug']][:limit]
        if related:
            sections.append({"tag": tag, "posts": related})
    return sections

def compute_adjacent_posts(posts):
    listed = [p for p in posts if p['meta'].get('unlisted', '').lower() != 'true']
    nav = {}
    for i, post in enumerate(listed):
        nav[post['slug']] = {
            "newer": listed[i - 1] if i > 0 else None,
            "older": listed[i + 1] if i < len(listed) - 1 else None,
        }
    return nav

def render_templates(posts, config):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    POSTS_PER_PAGE = config['website']['posts_per_page']
    related_limit = config['website'].get('related_posts_per_tag', 5)

    listed_posts = [p for p in posts if p['meta'].get('unlisted', '').lower() != 'true']
    total_pages = max(1, math.ceil(len(listed_posts) / POSTS_PER_PAGE))

    tag_index = build_tag_index(posts)
    tag_cloud = build_tag_cloud(tag_index)
    adjacent = compute_adjacent_posts(posts)

    index_template = env.get_template("index.html")
    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * POSTS_PER_PAGE
        end_idx = start_idx + POSTS_PER_PAGE
        paginated_posts = listed_posts[start_idx:end_idx]
        page_filename = "index.html" if page_num == 1 else f"page{page_num}.html"
        (OUTPUT_DIR / page_filename).write_text(
            index_template.render(
                posts=paginated_posts,
                config=config,
                current_page=page_num,
                total_pages=total_pages,
                tag_cloud=tag_cloud,
                path_prefix="",
            )
        )

    tag_template = env.get_template("tag.html")
    tags_dir = OUTPUT_DIR / "tags"
    tags_dir.mkdir(exist_ok=True)
    for tag in tag_index.values():
        (tags_dir / f"{tag['slug']}.html").write_text(
            tag_template.render(
                tag=tag,
                posts=tag['posts'],
                config=config,
                tag_cloud=tag_cloud,
                path_prefix="../",
            )
        )

    post_template = env.get_template("post.html")
    posts_dir = OUTPUT_DIR / "posts"
    posts_dir.mkdir(exist_ok=True)
    for post in posts:
        related = compute_related_posts(post, tag_index, related_limit)
        nav = adjacent.get(post['slug'], {"newer": None, "older": None})
        post_file = posts_dir / f"{post['slug']}.html"
        post_file.write_text(post_template.render(
            post=post,
            config=config,
            related_sections=related,
            newer_post=nav['newer'],
            older_post=nav['older'],
            path_prefix="../",
        ))

    not_found_template = env.get_template("404.html")
    (OUTPUT_DIR / "404.html").write_text(not_found_template.render(config=config))

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
    for image in CONTENT_IMG_DIR.glob("*/*.*"):
        relative_path = image.relative_to(CONTENT_IMG_DIR)
        target_dir = output_images_dir / relative_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / image.name).write_bytes(image.read_bytes())

def setup_hosting(config):
    bucket = config['aws']['s3_bucket']
    dist_id = config['aws']['cloudfront_dist_id']

    print(f"Configuring S3 website on s3://{bucket} (index.html / 404.html)...")
    subprocess.run([
        "aws", "s3", "website", f"s3://{bucket}",
        "--index-document", "index.html",
        "--error-document", "404.html",
    ], check=True)

    print(f"Configuring CloudFront custom error response on {dist_id}...")
    result = subprocess.run(
        ["aws", "cloudfront", "get-distribution-config", "--id", dist_id],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    etag = payload["ETag"]
    dist_config = payload["DistributionConfig"]

    desired_rules = [
        {
            "ErrorCode": code,
            "ResponsePagePath": "/404.html",
            "ResponseCode": "404",
            "ErrorCachingMinTTL": 10,
        }
        for code in (403, 404)
    ]

    errors = dist_config.setdefault("CustomErrorResponses", {"Quantity": 0, "Items": []})
    items = errors.get("Items", []) or []

    changed = False
    for desired in desired_rules:
        existing = next((i for i in items if i.get("ErrorCode") == desired["ErrorCode"]), None)
        if existing and all(existing.get(k) == v for k, v in desired.items()):
            continue
        if existing:
            existing.update(desired)
        else:
            items.append(desired)
        changed = True

    if not changed:
        print("CloudFront already has the desired 403/404 rules; skipping update.")
        return

    errors["Items"] = items
    errors["Quantity"] = len(items)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(dist_config, f)
        cfg_path = f.name

    subprocess.run([
        "aws", "cloudfront", "update-distribution",
        "--id", dist_id,
        "--if-match", etag,
        "--distribution-config", f"file://{cfg_path}",
    ], check=True)
    print("CloudFront distribution updated. Propagation may take several minutes.")

def find_orphan_images():
    """Return image files in content/images/<slug>/ not referenced by any post markdown."""
    referenced = set()
    for md_file in CONTENT_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        referenced.update(re.findall(r"[A-Za-z0-9._-]+\.(?:jpe?g|png|gif|webp|svg)", text, re.IGNORECASE))
    return sorted(
        p for p in CONTENT_IMG_DIR.glob("*/*.*")
        if p.is_file() and p.name not in referenced
    )

def _aws_rm(url, extra_args=None):
    cmd = ["aws", "s3", "rm", url, "--only-show-errors"] + (extra_args or [])
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"  warning: remote delete failed for {url} (exit {result.returncode})")
    return result.returncode

def _invalidate(dist_id, paths):
    if not dist_id or not paths:
        return
    print(f"Invalidating CloudFront: {' '.join(paths)}")
    subprocess.run(
        ["aws", "cloudfront", "create-invalidation",
         "--distribution-id", dist_id, "--paths", *paths],
        check=False,
    )

def prune_images(assume_yes=False):
    """Delete images not used by any post, locally and from the remote bucket."""
    config = load_config()
    bucket = config["aws"]["s3_bucket"]
    dist_id = config["aws"].get("cloudfront_dist_id")

    orphans = find_orphan_images()
    if not orphans:
        print("Nothing to prune; every image is referenced by a post.")
        return

    print(f"Found {len(orphans)} image(s) not referenced by any post:")
    for p in orphans:
        print(f"  - {p.parent.name}/{p.name}")

    if not assume_yes:
        answer = input("Delete these locally AND from the remote bucket? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    invalidation_paths = []
    for p in orphans:
        slug, name = p.parent.name, p.name
        _aws_rm(f"s3://{bucket}/images/{slug}/{name}")
        p.unlink(missing_ok=True)
        (OUTPUT_DIR / "images" / slug / name).unlink(missing_ok=True)
        invalidation_paths.append(f"/images/{slug}/{name}")
        print(f"Pruned {slug}/{name}")

    for folder in CONTENT_IMG_DIR.glob("*"):
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()

    _invalidate(dist_id, invalidation_paths)
    print("Prune complete.")

def delete_post_artifacts(slug):
    """Delete a removed post's remote objects (post page + its image folder) and dist copies."""
    if not slug or slug in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
        raise ValueError(f"invalid slug: {slug!r}")

    config = load_config()
    bucket = config["aws"]["s3_bucket"]
    dist_id = config["aws"].get("cloudfront_dist_id")

    print(f"Removing s3://{bucket}/posts/{slug}.html ...")
    _aws_rm(f"s3://{bucket}/posts/{slug}.html")

    print(f"Removing s3://{bucket}/images/{slug}/ ...")
    _aws_rm(f"s3://{bucket}/images/{slug}/", extra_args=["--recursive"])

    # Remove dist copies so a later sync cannot resurrect anything.
    (OUTPUT_DIR / "posts" / f"{slug}.html").unlink(missing_ok=True)
    dist_images = OUTPUT_DIR / "images" / slug
    if dist_images.is_dir():
        shutil.rmtree(dist_images)

    _invalidate(dist_id, [f"/posts/{slug}.html", f"/images/{slug}/*"])
    print(f"Remote cleanup done for post '{slug}'.")

def sync_s3_and_invalidate(config):
    bucket = config['aws']['s3_bucket']
    dist_id = config['aws']['cloudfront_dist_id']
    subprocess.run(["aws", "s3", "sync", str(OUTPUT_DIR), f"s3://{bucket}", "--acl", "public-read"], check=True)
    subprocess.run(["aws", "cloudfront", "create-invalidation", "--distribution-id", dist_id, "--paths", "/*"], check=True)
    print("Upload complete and CloudFront invalidated.")

def generate_rss_feed(posts, output_dir, config, feed_size=25):
    rss_items = []
    feed_posts = [p for p in posts if p['meta'].get('unlisted', '').lower() != 'true'][:feed_size]
    base_url = config["website"]["base_url"]
    feed_url = f"{base_url}/feed.xml"

    for post in feed_posts:
        guid_url = f"{base_url}/posts/{post['slug']}.html"
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
        "tag_template": compute_hash(TEMPLATE_DIR / "tag.html"),
        "not_found_template": compute_hash(TEMPLATE_DIR / "404.html"),
        "style": compute_hash(Path("static/style.css")),
        "config": compute_hash(Path(CONFIG_PATH)),
        **{str(p): compute_hash(p) for p in CONTENT_DIR.glob("*.md")},
        **{str(p): compute_hash(p) for p in IMAGE_DIR.glob("*.*")},
        **{str(p): compute_hash(p) for p in CONTENT_IMG_DIR.glob("*/*.*")}
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
    args = sys.argv[1:]
    if args and args[0] == "setup":
        setup_hosting(load_config())
    elif args and args[0] == "prune":
        prune_images(assume_yes="--yes" in args[1:])
    else:
        main()

