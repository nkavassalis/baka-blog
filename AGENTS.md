# AGENTS.md — working on baka blog

A tiny Markdown → static-site blog: ~450 lines of Python, five Jinja templates, one stylesheet,
deployed as static files to S3 + CloudFront, with an optional local Flask editor. Keep it that way:
small, dependency-light, no build framework, no client-side JS except the 404 page's canvas.

## Layout

| Path | Role |
|---|---|
| `make.py` | the whole generator: parse posts → build tag indexes → render templates → copy assets → deploy |
| `app.py` | local Flask editor (`python app.py`), talks to `make.py` for regenerate/prune |
| `setup.sh` | one-time env bootstrap: creates `.venv/`, installs `requirements.txt`, seeds `config.yaml` |
| `templates/` | `index.html`, `post.html`, `tag.html`, `404.html`, plus the shared `tagnav.html` partial |
| `static/style.css` | single stylesheet; copied verbatim to `dist/style.css` |
| `static/images/` | site chrome (logo, background, author avatar) |
| `content/posts/*.md` | posts; filename stem = URL slug |
| `content/images/<slug>/` | per-post images, mirrored into `dist/images/<slug>/` |
| `config.yaml` | your site config (git-ignored); start from `config.yaml.example` |
| `dist/` | generated site — never hand-edit, never commit |
| `.file_hashes.json` | build cache of content/template/style hashes — generated, never commit |

## Commands

Every target in the Makefile runs `.venv/bin/python` (created by `./setup.sh`), so system Python
never needs the dependencies. If `.venv/bin/python` is missing, make fails with a pointer to
`./setup.sh`. To use a different interpreter: `make PYTHON=/path/to/python`.

| Command | What it does |
|---|---|
| `./setup.sh` | create `.venv/`, install requirements, seed `config.yaml` from the example (safe to re-run) |
| `make` / `.venv/bin/python make.py` | build **and deploy** to S3 + invalidate all of CloudFront |
| `make all` | clear caches, rebuild, redeploy |
| `make clean` | delete the build caches (`.file_hashes.json`, plus a legacy `.slug_uuid_mapping.json`) so the next build is unconditional |
| `make setup` | one-time S3 website + CloudFront 403/404 → `/404.html` wiring (idempotent) |
| `make prune` | delete images no post references — **locally and in the bucket** (prompts; `.venv/bin/python make.py prune --yes` to skip the prompt) |
| `source .venv/bin/activate && python app.py` | editor UI on `editor.host:editor.port` from config |

`make.py` skips the whole build when nothing's hash changed, so re-running it is cheap — but when
something *has* changed it deploys to production, not to a preview.

## Verifying a change without deploying

Render locally only (`render_templates` just writes files under `dist/`):

```bash
cp config.yaml.example config.yaml   # first time only; make.py refuses to run without a config
.venv/bin/python -c "
import make, pathlib
cfg = make.load_config()
posts = make.build_content()
make.render_templates(posts, cfg)
print(len(posts), 'posts rendered')
print(pathlib.Path('dist/index.html').read_text()[:400])
"
```

Useful entry points in `make.py`: `build_content()` (Markdown → HTML + metadata),
`build_tag_index(posts, config)`, `build_tag_cloud(tag_index)`, `build_pinned_tag_nav(config, tag_index)`,
`compute_related_posts`, `compute_adjacent_posts`, `render_templates(posts, config)`.

Then diff `dist/` to see exactly what a change did:

```bash
git status dist 2>/dev/null; ls -la dist dist/posts dist/tags
```

## Posts and front matter

Parsed by Python-Markdown's `meta` extension, so front matter is `key: value` lines (the `---`
fences are tolerated). Keys read by the generator:

- `title` — required (page title, index list, RSS).
- `date: YYYY-MM-DD` — required; drives ordering and the readable date. Wrong format = hard crash on build.
- `subtitle` — optional one-liner under the title on index and article pages.
- `tags:` — comma or repeated values; each becomes `tags/<slug>.html`. `slugify_tag()` lowercases and
  collapses non-alphanumerics to `-`.
- `unlisted: true` — hides the post from the index, tag pages, related/prev-next nav, and RSS, but the
  post page itself still builds.

Markdown is converted with `extensions=['meta', 'tables']` (see `make.py` `build_content`). If you want
fenced code blocks, footnotes, attribute lists, etc., add the extension there — and remember the hash
cache won't notice a `make.py` edit, so `make clean` first when testing generator changes.

Images: reference them as `![alt](../images/<slug>/<file>)`; the build copies
`content/images/<slug>/*` into `dist/images/<slug>/`. The editor normalises uploads to
`images.max_width` JPEG (EXIF orientation applied, light unsharp after resize).

## Templates

Jinja2 with `FileSystemLoader('templates')`, no autoescape (the config intentionally injects raw HTML
in `subtitle`/`footer`).

- Root-level pages (`index.html`, `404.html`, `pageN.html`) use `path_prefix=""`; everything under
  `posts/` or `tags/` is rendered with `path_prefix="../"`. Any new link in a template must use
  `{{ path_prefix }}`, or it breaks one of the two levels.
- `templates/tagnav.html` is included by every page template and reads `pinned_tags`,
  `current_tag_slug` and `path_prefix` from the including context — pass those when you add a template.
- `404.html` is rendered with just `config` + the tag-nav variables.

## Styles

One file, `static/style.css`, with a `:root` block of CSS variables up top — use the existing
`--color-*` variables rather than new literals. Styles for post content live under `article.content`,
tag lists under `.tag-cloud` / `.tag-nav`, lists under `.post-list`.

## Config keys

Anything new goes in `config.yaml.example` **and** the README, and should be read defensively
(`config['website'].get('key', default)`) so an older `config.yaml` still builds. Existing keys:
`website.{title,description,base_url,subtitle,footer,posts_per_page,related_posts_per_tag,author,
author_email,author_avatar,pinned_tags}`, `aws.{s3_bucket,cloudfront_dist_id}`,
`editor.{host,port}`, `images.{max_width,jpeg_quality}`.

## Editor (`app.py`)

REST-ish JSON API (`/api/posts`, `/api/post/<file>`, `/api/new`, `/api/upload_image/<slug>`,
`/api/images`, `/api/delete_image/...`, `/api/regenerate`, `/api/prune`) behind `templates/editor.html`.
It is meant for localhost only — never expose it. Deleting a post in the editor removes local files;
`make.py` then removes the deployed artifacts for that slug on the next build, and the editor's prune
button forwards to `make.py prune --yes`.

## Conventions / gotchas

- `config.yaml`, `dist/`, `.venv/`, `.file_hashes.json`, `__pycache__/` are git-ignored. `config.yaml` holds real
  bucket + distribution IDs — never commit it, never paste it into a PR.
- Post deletion goes through the editor: `app.py` calls `make.delete_post_artifacts(slug)`, which removes
  `posts/<slug>.html` and `images/<slug>/` from the bucket, from `dist/`, and invalidates those paths.
  A plain build never deletes anything from S3.
- `generate_rss_feed()` builds `feed.xml` by string template (25 newest listed posts); if you touch the
  item shape, keep `escape()` on interpolated text.
- Deploys are a full `aws s3 sync --acl public-read` + `/*` invalidation; there is no partial/incremental
  publish and no staging bucket. Assume any build you run against a real config publishes.
- Sample content in `content/posts/my-*-post.md` exists so a fresh clone builds something; a fork's real
  posts can live elsewhere — nothing in the generator depends on those filenames.

## Pull request hygiene

Run the local render above, confirm `dist/` output looks right, keep diffs scoped to the files you
actually changed, and update this file plus the README when behavior or commands change.
