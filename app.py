from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template, send_from_directory, flash, abort
from werkzeug.utils import secure_filename
import secrets
import os
import json
import threading
import mimetypes
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_FILE = BASE_DIR / "items.json"
FOLDERS_FILE = BASE_DIR / "folders.json"
UPLOAD_DIR.mkdir(exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "512"))
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024
ALLOWED = None  # Set to a set of extensions if you want to restrict uploads.
LOCK = threading.Lock()

# Folders are virtual: they only exist in folders.json. Every file stays flat inside
# uploads/ with a random name, and each item just records the id of its folder
# (None = top level). So a folder name can never be used to reach other paths on disk.


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_items():
    return _read(DATA_FILE)


def save_items(items):
    _write(DATA_FILE, items)


def load_folders():
    return _read(FOLDERS_FILE)


def save_folders(folders):
    _write(FOLDERS_FILE, folders)


def find_folder(folder_id, folders=None):
    if not folder_id:
        return None
    return next((f for f in (folders if folders is not None else load_folders()) if f["id"] == folder_id), None)


def breadcrumb(folder, folders):
    """Folders from the top level down to `folder`."""
    chain = []
    seen = set()
    while folder and folder["id"] not in seen:
        seen.add(folder["id"])
        chain.append(folder)
        folder = find_folder(folder.get("parent"), folders)
    return list(reversed(chain))


def folder_options(folders):
    """Every folder as (id, 'A / B / C'), sorted by path. Used by the destination dropdowns."""
    opts = [(f["id"], " / ".join(x["name"] for x in breadcrumb(f, folders))) for f in folders]
    return sorted(opts, key=lambda o: o[1].lower())


def descendant_ids(folder_id, folders):
    ids = {folder_id}
    changed = True
    while changed:
        changed = False
        for f in folders:
            if f.get("parent") in ids and f["id"] not in ids:
                ids.add(f["id"])
                changed = True
    return ids


def valid_folder_id(raw, folders):
    """Return raw if it names an existing folder, otherwise None (top level)."""
    raw = (raw or "").strip()
    return raw if raw and find_folder(raw, folders) else None


# What the browser may display inline. Anything else (html, svg, scripts...) is download-only,
# because opening an uploaded .html/.svg on this site would run its code with the site's rights.
INLINE_TEXT_EXT = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".yml", ".yaml", ".ini", ".conf",
                   ".py", ".js", ".ts", ".css", ".sh", ".c", ".h", ".cpp", ".java", ".go", ".rs", ".sql", ".toml"}


def preview_kind(item):
    """'image' | 'video' | 'audio' | 'pdf' | 'text' | None (not previewable)."""
    if item.get("kind") != "file":
        return None
    name = item.get("name", "").lower()
    ext = os.path.splitext(name)[1]
    mime = mimetypes.guess_type(name)[0] or ""
    if mime.startswith("image/") and mime != "image/svg+xml":
        return "image"
    if mime in ("video/mp4", "video/webm", "video/ogg"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime == "application/pdf":
        return "pdf"
    if ext in INLINE_TEXT_EXT:
        return "text"
    return None


@app.context_processor
def inject_helpers():
    return {"preview_kind": preview_kind}


def go(folder_id):
    return redirect(url_for("browse", folder_id=folder_id) if folder_id else url_for("index"))


@app.get("/")
def index():
    return browse(None)


@app.get("/f/<folder_id>")
def browse(folder_id):
    folders = load_folders()
    current = None
    if folder_id:
        current = find_folder(folder_id, folders)
        if not current:
            abort(404)
    items = [x for x in load_items() if (x.get("folder") or None) == folder_id]
    items.sort(key=lambda x: x.get("created", ""), reverse=True)
    subfolders = sorted((f for f in folders if (f.get("parent") or None) == folder_id),
                        key=lambda f: f["name"].lower())
    all_items = load_items()
    counts = {f["id"]: sum(1 for x in all_items if x.get("folder") == f["id"]) +
                       sum(1 for g in folders if g.get("parent") == f["id"]) for f in subfolders}
    return render_template(
        "index.html", items=items, max_mb=MAX_MB, current=current, subfolders=subfolders,
        counts=counts, crumbs=breadcrumb(current, folders), options=folder_options(folders),
    )


@app.post("/folder/new")
def new_folder():
    with LOCK:
        folders = load_folders()
        parent = valid_folder_id(request.form.get("parent"), folders)
        name = " ".join(request.form.get("name", "").split())[:60]
        if not name:
            flash("Enter a folder name.", "error")
        elif any(f["name"].lower() == name.lower() and (f.get("parent") or None) == parent for f in folders):
            flash("A folder with that name already exists here.", "error")
        else:
            folders.append({"id": secrets.token_urlsafe(9), "name": name, "parent": parent,
                            "created": datetime.now(timezone.utc).isoformat()})
            save_folders(folders)
            flash(f"Folder “{name}” created.", "success")
    return go(parent)


@app.post("/folder/<folder_id>/rename")
def rename_folder(folder_id):
    with LOCK:
        folders = load_folders()
        folder = find_folder(folder_id, folders)
        if not folder:
            abort(404)
        name = " ".join(request.form.get("name", "").split())[:60]
        if not name:
            flash("Enter a folder name.", "error")
        elif any(f["id"] != folder_id and f["name"].lower() == name.lower()
                 and f.get("parent") == folder.get("parent") for f in folders):
            flash("A folder with that name already exists here.", "error")
        else:
            folder["name"] = name
            save_folders(folders)
            flash("Folder renamed.", "success")
    return go(folder_id)


@app.post("/folder/<folder_id>/delete")
def delete_folder(folder_id):
    with LOCK:
        folders = load_folders()
        folder = find_folder(folder_id, folders)
        if not folder:
            abort(404)
        gone = descendant_ids(folder_id, folders)
        items = load_items()
        removed = [x for x in items if x.get("folder") in gone]
        for x in removed:
            try:
                (UPLOAD_DIR / x["stored"]).unlink(missing_ok=True)
            except OSError:
                pass
        save_items([x for x in items if x.get("folder") not in gone])
        save_folders([f for f in folders if f["id"] not in gone])
        flash(f"Folder “{folder['name']}” deleted with {len(removed)} item(s).", "success")
    return go(folder.get("parent"))


@app.post("/upload")
def upload():
    files = request.files.getlist("files")
    folder_id = valid_folder_id(request.form.get("folder"), load_folders())
    saved = []
    for file in files:
        if not file or not file.filename:
            continue
        original = secure_filename(file.filename) or "file"
        stored = f"{secrets.token_urlsafe(10)}_{original}"
        file.save(UPLOAD_DIR / stored)
        saved.append({
            "id": secrets.token_urlsafe(9),
            "kind": "file",
            "name": original,
            "stored": stored,
            "folder": folder_id,
            "size": (UPLOAD_DIR / stored).stat().st_size,
            "created": datetime.now(timezone.utc).isoformat()
        })
    if saved:
        with LOCK:
            items = load_items()
            items.extend(saved)
            save_items(items)
        flash(f"Uploaded {len(saved)} file(s).", "success")
    else:
        flash("Choose at least one file first.", "error")
    return go(folder_id)


@app.post("/text")
def add_text():
    content = request.form.get("content", "").strip()
    title = request.form.get("title", "").strip()[:100] or "Shared text"
    folder_id = valid_folder_id(request.form.get("folder"), load_folders())
    if not content:
        flash("Enter some text first.", "error")
        return go(folder_id)
    item_id = secrets.token_urlsafe(9)
    filename = f"text_{item_id}.txt"
    (UPLOAD_DIR / filename).write_text(content, encoding="utf-8")
    item = {
        "id": item_id, "kind": "text", "name": title, "stored": filename, "folder": folder_id,
        "size": len(content.encode("utf-8")),
        "preview": content[:180], "created": datetime.now(timezone.utc).isoformat()
    }
    with LOCK:
        items = load_items()
        items.append(item)
        save_items(items)
    flash("Text saved. Use Copy or Open to share it.", "success")
    return go(folder_id)


@app.post("/move/<item_id>")
def move(item_id):
    with LOCK:
        items = load_items()
        item = next((x for x in items if x.get("id") == item_id), None)
        if not item:
            abort(404)
        target = valid_folder_id(request.form.get("folder"), load_folders())
        item["folder"] = target
        save_items(items)
    flash("Item moved.", "success")
    return go(target)


@app.get("/download/<item_id>")
def download(item_id):
    item = next((x for x in load_items() if x.get("id") == item_id), None)
    if not item:
        abort(404)
    return send_from_directory(UPLOAD_DIR, item["stored"], as_attachment=True, download_name=item["name"])


@app.get("/raw/<item_id>")
def raw(item_id):
    """Serve a file for display inside the page (only the safe types above)."""
    item = next((x for x in load_items() if x.get("id") == item_id), None)
    kind = preview_kind(item) if item else None
    if not kind:
        abort(404)
    mime = "text/plain; charset=utf-8" if kind == "text" else (mimetypes.guess_type(item["name"])[0] or "application/octet-stream")
    resp = send_from_directory(UPLOAD_DIR, item["stored"], mimetype=mime, as_attachment=False)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if kind != "pdf":  # Chrome's PDF viewer does not work inside a CSP sandbox
        resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resp


@app.get("/preview/<item_id>")
def preview(item_id):
    items = load_items()
    item = next((x for x in items if x.get("id") == item_id), None)
    kind = preview_kind(item) if item else None
    if not kind:
        abort(404)
    siblings = [x for x in items if (x.get("folder") or None) == (item.get("folder") or None) and preview_kind(x)]
    siblings.sort(key=lambda x: x.get("created", ""), reverse=True)
    pos = next(i for i, x in enumerate(siblings) if x["id"] == item_id)
    text = None
    if kind == "text":
        text = (UPLOAD_DIR / item["stored"]).read_text(encoding="utf-8", errors="replace")[:500_000]
    return render_template(
        "preview.html", item=item, kind=kind, text=text, back=item.get("folder"),
        prev=siblings[pos - 1] if pos > 0 else None,
        next=siblings[pos + 1] if pos + 1 < len(siblings) else None,
    )


@app.get("/view/<item_id>")
def view_text(item_id):
    item = next((x for x in load_items() if x.get("id") == item_id and x.get("kind") == "text"), None)
    if not item:
        abort(404)
    content = (UPLOAD_DIR / item["stored"]).read_text(encoding="utf-8", errors="replace")
    return render_template("view.html", item=item, content=content, back=item.get("folder"))


@app.post("/delete/<item_id>")
def delete(item_id):
    with LOCK:
        items = load_items()
        item = next((x for x in items if x.get("id") == item_id), None)
        if not item:
            abort(404)
        try:
            (UPLOAD_DIR / item["stored"]).unlink(missing_ok=True)
        except OSError:
            pass
        save_items([x for x in items if x.get("id") != item_id])
    flash("Item deleted.", "success")
    return go(item.get("folder"))


@app.errorhandler(413)
def too_large(_error):
    flash(f"File is too large. Maximum upload size is {MAX_MB} MB.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Accessible from other devices on the same LAN. Use 127.0.0.1 instead for this computer only.
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "5000")), debug=False)
