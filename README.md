A simple markdown to static site generator blog, with a locally hosted editor. Supports S3 and CloudFront for hosting. Shared for folks who may want a very light weight website.

--- 

## Setup

```bash
./setup.sh
```

Creates `.venv/`, installs `requirements.txt` into it, and copies `config.yaml.example` to
`config.yaml` if you don't have one yet (edit it next — `make.py` refuses to run without a config).
Every `make` target then runs through `.venv/bin/python` automatically; no activation needed.
Run `./setup.sh` again any time requirements change (it recreates the venv cleanly).

```bash
make
```
to generate the static site

```bash
make clean
```
to clean the locally generated files

```bash
make all
```
to clean the locally generated files and re-upload the site to S3 / wipe CF

```bash
make setup
```
one-time hosting configuration: points the S3 bucket's website index/error documents at `index.html` / `404.html`, and adds CloudFront custom error responses mapping both 403 and 404 to `/404.html`. Idempotent — safe to re-run; it only triggers a CloudFront update when the rules have drifted.

```bash
source .venv/bin/activate
python app.py
```
to launch the post editor service

surf to http://localhost:5000

Do not expose the editor to the internet. Deleting files using the editor will not delete / remove them from S3.

---

## LLM-friendly files

Every build publishes (set `website.llms_txt: false` to opt out of the llms files):

- **`/llms.txt`** — a [llms.txt](https://llmstxt.org) markdown index of every listed post (title,
  URL, date, tags) so assistants like ChatGPT/Gemini can discover and fetch your posts.
- **`/llms-full.txt`** — the full post archive as plain Markdown (front matter stripped, unlisted
  posts excluded), for LLMs that prefer one fetch.
- **`/robots.txt`** — always written, open by default (`User-agent: * / Allow: /`) with a comment
  welcoming AI retrieval bots and a `Sitemap:` pointer. Nothing is blocked, so training opt-outs
  (e.g. `Google-Extended` disallow) are intentionally absent — add them by hand only if you change
  your mind; crawling for search/RAG still works via `*`.
- **`/sitemap.xml`** — always written: index (+ pagination), every listed post with `lastmod`, and
  every non-empty tag page. Unlisted posts never appear.

---

## Social preview cards

Every public page ships Open Graph + Twitter card metadata (`templates/share.html`) plus a canonical
URL and meta description. Post pages use the post's **first content image** as `og:image` (external
image URLs work too, SVGs are skipped); with no image — and on the index/tag/404 pages — they fall
back to `website.share_image` (default `images/logo.png`). Descriptions come from the post's
`description:` front matter, else `subtitle:`, else the first ~300 characters of the post text. Add
`description:` front matter to a post when you want to control its card text.

---

## Pinned tags

`website.pinned_tags` in `config.yaml` turns any set of tags into a static nav bar under the site
subtitle, shown on every page (index, post, tag, 404):

```yaml
website:
  pinned_tags:
    - technology
    - photography
    - games
    - other
```

- Links point at `tags/<slug>.html`, with the slug generated the same way as every other tag
  (lowercased, non-alphanumerics collapsed to `-`), so names can be written in any case or spacing.
- The bar is rendered exactly in the order you list it, and only with the tags you list — it is not
  alphabetical and does not grow on its own, unlike the tag cloud at the bottom of the index page,
  which is derived from the posts themselves.
- Empty pinned tags are still linked: `make` generates a `tags/<slug>.html` page for each one, so a
  pinned link never 404s before you have filed a post under it. The index tag cloud hides zero-post
  tags.
- On a tag page the matching entry is underlined as the active item.
- Omit `pinned_tags` (or leave it empty) and no nav bar is rendered at all.

Markup lives in `templates/tagnav.html` (included by every page template); style it with
`.tag-nav`, `.tag-nav-link`, `.tag-nav-active` and `.tag-nav-sep` in `static/style.css`.

---

See it live [baka.jp](https://baka.jp)
