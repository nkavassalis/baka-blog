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
