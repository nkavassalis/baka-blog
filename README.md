A simple markdown to static site generator blog, with a locally hosted editor. Supports S3 and CloudFront for hosting. Shared for folks who may want a very light weight website.

--- 

## Setup

```bash
pip install -r requirements.txt
```

Setup a config.yaml in the root directory based on the config.yaml.example

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
python app.py
```
to launch the post editor service

surf to http://localhost:5000

Do not expose the editor to the internet. Deleting files using the editor will not delete / remove them from S3.

---

See it live [baka.jp](https://baka.jp)
