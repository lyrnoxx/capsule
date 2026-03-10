import logging
import os
import json
import re
import uuid
import tempfile
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

import torch
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

from logger import init_app as init_logger, create_blueprint as logger_bp

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# ── App init ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object("config.Config")

UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/outputs"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Extensions ────────────────────────────────────────────────────────
Compress(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["120/minute"])

init_logger(app)
app.register_blueprint(logger_bp(), url_prefix="/logger")

# Prevent Flask-Login from redirecting portfolio routes to a login page.
app.login_manager.login_view = None


@app.login_manager.unauthorized_handler
def _handle_unauthorized():
    if request.blueprint == "logger":
        return redirect(url_for("logger.login", next=request.url))
    return redirect(url_for("home"))


# ── Static-asset cache headers ────────────────────────────────────────
@app.after_request
def _add_cache_headers(response):
    if request.path.startswith("/static/"):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response


# ── Allowed upload types ──────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIMETYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file


def _is_allowed_image(file):
    """Validate extension and MIME type."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if file.content_type not in ALLOWED_MIMETYPES:
        return False
    return True


# ── Cache projects.json at module level ───────────────────────────────
_projects_path = os.path.join(os.path.dirname(__file__), "projects.json")
with open(_projects_path, encoding="utf-8") as _f:
    PROJECTS = json.load(_f)
PROJECT_TAGS = sorted({tag for p in PROJECTS for tag in p["tags"]})

# ── GitHub stats (cached) ─────────────────────────────────────────────
GITHUB_USERNAME = "lyrnoxx"
_github_cache = {"data": None, "ts": 0}
_GITHUB_TTL = 3600  # refresh every hour


def _fmt_number(n):
    """Format large numbers: 1200000 -> '1.2M', 54000 -> '54K'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def _fetch_github_stats():
    """Fetch real GitHub contribution data + repo stats."""
    now = time.time()
    if _github_cache["data"] and now - _github_cache["ts"] < _GITHUB_TTL:
        return _github_cache["data"]
    try:
        headers = {"User-Agent": "portfolio-app"}
        # ── Repos (for count + lines estimate) ────────────────────────
        url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos?per_page=100&type=owner"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            repos = json.loads(resp.read().decode())
        total_repos = len(repos)
        total_lines = sum(r.get("size", 0) for r in repos) * 20
        # ── Real contribution calendar (scrape GitHub HTML) ───────────
        contrib_url = f"https://github.com/users/{GITHUB_USERNAME}/contributions"
        creq = urllib.request.Request(contrib_url, headers={"User-Agent": "portfolio-app"})
        with urllib.request.urlopen(creq, timeout=10) as cresp:
            html = cresp.read().decode()
        # Total contributions from heading
        m = re.search(r'([\d,]+)\s+contributions?\s+in the last year', html)
        contributions = int(m.group(1).replace(',', '')) if m else 0
        # Parse each day: data-date + data-level
        day_pattern = re.compile(
            r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d)"'
        )
        days = []  # list of (date_str, level)
        for match in day_pattern.finditer(html):
            days.append((match.group(1), int(match.group(2))))
        days.sort(key=lambda x: x[0])
        # Build heatmap grid (weeks of 7 days)
        heatmap = []
        week = []
        for date_str, level in days:
            week.append({"date": date_str, "count": level, "level": level})
            if len(week) == 7:
                heatmap.append(week)
                week = []
        if week:
            heatmap.append(week)
        stats = {
            "repos": total_repos,
            "contributions": contributions,
            "lines": total_lines,
            "lines_fmt": _fmt_number(total_lines),
            "heatmap": heatmap,
        }
        _github_cache["data"] = stats
        _github_cache["ts"] = now
        return stats
    except Exception as exc:
        log.warning("GitHub stats fetch failed: %s", exc)
        return _github_cache["data"] or {
            "repos": 0, "contributions": 0, "lines": 0,
            "lines_fmt": "0", "heatmap": [],
        }

# ── Cache autoencoder model at startup ────────────────────────────────
from models.models import DenoisingAutoencoder  # noqa: E402

_ae_model = None
_ae_model_path = os.path.join(os.path.dirname(__file__), "models", "autoencoder.pth")
if os.path.exists(_ae_model_path):
    try:
        _ae_model = DenoisingAutoencoder()
        _ae_model.load_state_dict(torch.load(_ae_model_path, map_location="cpu", weights_only=True))
        _ae_model.eval()
        log.info("Autoencoder model loaded.")
    except Exception:
        log.exception("Failed to load autoencoder model.")
        _ae_model = None
else:
    log.warning("Autoencoder weights not found at %s", _ae_model_path)

# ── Routes ────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html", github_stats=_fetch_github_stats())


@app.route("/reinforce")
def reinforce():
    return render_template("project_reinforce.html")


@app.route("/autoencoder", methods=["GET", "POST"])
def autoencoder():
    if request.method == "POST":
        file = request.files.get("image")
        if not file or not _is_allowed_image(file):
            return render_template("project_autoencoder.html", error="Please upload a JPG or PNG image.")

        filename = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1].lower()}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        image = Image.open(filepath).convert("L").resize((28, 28))

        output_filename = f"{uuid.uuid4()}.png"
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

        if _ae_model is not None:
            img_tensor = torch.tensor(
                np.array(image, dtype=np.float32) / 255.0
            ).unsqueeze(0).unsqueeze(0)
            with torch.no_grad():
                output_tensor = _ae_model(img_tensor)
            output_img = Image.fromarray(
                (output_tensor.squeeze().numpy() * 255).astype(np.uint8)
            )
            output_img.save(output_path)
        else:
            image.save(output_path)

        return render_template(
            "project_autoencoder.html",
            input_image="uploads/" + filename,
            output_image="outputs/" + output_filename,
        )
    return render_template("project_autoencoder.html")


@app.route("/drone")
def drone():
    return render_template("project_drone.html")


@app.route("/drone/system")
def drone_system():
    return render_template("project_drone-system.html")


def cleanup_temp_dir(dir_path):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            log.info("Deleted temporary directory: %s", dir_path)
        except Exception:
            log.exception("Failed to delete temporary directory %s", dir_path)


def run_docker_command(temp_dir_path):
    temp_dir_path = os.path.normpath(os.path.abspath(temp_dir_path))
    command = [
        "/usr/bin/docker",
        "run",
        "--rm",
        "-v",
        f"{temp_dir_path}:/data",
        "map2dfusion",
        "DataPath=/data",
        "Win3D.Enable=0",
        "ShouldStop=1",
        "Map.File2Save=/data/output.png",
    ]

    log.info("Executing Docker command: %s", " ".join(command))

    try:
        log.info("Contents of %s: %s", temp_dir_path, os.listdir(temp_dir_path))
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=180
        )
        log.info("Docker STDOUT: %s", result.stdout)
        log.info("Docker STDERR: %s", result.stderr)
        return True, "Docker processing completed."

    except subprocess.CalledProcessError as e:
        log.error("Docker failed! STDOUT: %s STDERR: %s", e.stdout, e.stderr)
        return False, f"Docker failed: {e.stderr}"
    except Exception:
        log.exception("Unexpected error running Docker")
        return False, "Internal error during processing."

@app.route("/drone/stitch", methods=["GET", "POST"])
@csrf.exempt  # this route uses fetch + JSON responses; CSRF via header instead
@limiter.limit("10/minute")
def drone_stitch():
    if request.method == "POST":
        base_temp = "/var/www/tmp"
        os.makedirs(base_temp, exist_ok=True)
        temp_dir = tempfile.mkdtemp(dir=base_temp)
        os.chmod(temp_dir, 0o755)
        rgb_dir = os.path.join(temp_dir, "rgb")
        os.makedirs(rgb_dir, exist_ok=True)

        try:
            trajectory_file = request.files.get("trajectory")
            config_file = request.files.get("config")
            image_files = request.files.getlist("images")

            if not trajectory_file or not image_files or not config_file:
                raise ValueError(
                    "Missing trajectory file or config file or image folder files."
                )

            trajectory_file.save(os.path.join(temp_dir, "trajectory.txt"))
            log.info("Saved trajectory.txt to %s", temp_dir)

            config_file.save(os.path.join(temp_dir, "config.cfg"))
            log.info("Saved config.cfg to %s", temp_dir)

            for file in image_files:
                if file.filename:
                    base_filename = os.path.basename(file.filename)
                    file.save(os.path.join(rgb_dir, base_filename))
            log.info("Saved %d image files to %s", len(image_files), rgb_dir)

            success, message = run_docker_command(temp_dir)

            if not success:
                return jsonify({"success": False, "error": message}), 500

            source_path = os.path.join(temp_dir, "output.png")
            final_map_filename = f"map_{uuid.uuid4()}.png"
            destination_path = os.path.join(
                app.config["OUTPUT_FOLDER"], final_map_filename
            )

            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                final_image_url = url_for(
                    "static",
                    filename=f"outputs/{final_map_filename}",
                    _external=True,
                )
                log.info("Moved output file to %s", final_image_url)
            else:
                log.error("Docker succeeded but output.png not found.")
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Docker process finished, but the output file was not found.",
                        }
                    ),
                    500,
                )

            return (
                jsonify(
                    {
                        "success": True,
                        "imageUrl": final_image_url,
                        "message": "Stitching complete. Map saved.",
                    }
                ),
                200,
            )

        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception:
            log.exception("Unexpected error during drone stitching")
            return (
                jsonify({"success": False, "error": "Internal server error."}),
                500,
            )
        finally:
            cleanup_temp_dir(temp_dir)

    return render_template("project_drone-stitch.html")


@app.route("/drone/recent-works")
def recentworks():
    return render_template("awd.html")


@app.route("/talks")
def talks():
    return render_template("project_talks.html")


@app.route("/vision")
def vision():
    return render_template("project_vision.html")


@app.route("/graphics")
def graphics():
    return render_template("graphics.html")


@app.route("/projection")
def projection():
    return render_template(
        "project_projection.html", projects=PROJECTS, all_tags=PROJECT_TAGS
    )


@app.route("/nlp")
def nlp():
    return render_template("project_nlp.html")


# ── Contact form ──────────────────────────────────────────────────────
_MESSAGES_FILE = os.path.join(os.path.dirname(__file__), "messages.json")


def _save_message(name, email, message):
    """Append a contact message to messages.json."""
    import datetime
    entry = {
        "name": name,
        "email": email,
        "message": message,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    msgs = []
    if os.path.exists(_MESSAGES_FILE):
        with open(_MESSAGES_FILE, encoding="utf-8") as f:
            try:
                msgs = json.load(f)
            except json.JSONDecodeError:
                msgs = []
    msgs.append(entry)
    with open(_MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=2, ensure_ascii=False)


@app.route("/contact", methods=["GET", "POST"])
@limiter.limit("5/minute")
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not email or not message:
            return render_template(
                "contact.html", error="All fields are required."
            )
        _save_message(name, email, message)
        log.info("Contact form submitted by %s <%s>", name, email)
        return render_template("contact.html", success=True)
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)