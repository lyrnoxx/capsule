from flask import render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_user, logout_user, current_user

from . import db
from .models import User, Item, LogEntry

# Routes that guests (unauthenticated users) may access
_OPEN_ENDPOINTS = {"logger.login", "logger.signup", "logger.static"}


def register_routes(bp):
    """Attach all routes to the given Blueprint."""

    @bp.before_request
    def _require_login():
        """Redirect to logger login for any protected logger route."""
        if request.endpoint in _OPEN_ENDPOINTS:
            return  # allow through
        if not current_user.is_authenticated:
            return redirect(url_for("logger.login", next=request.url))

    # ─── Auth ─────────────────────────────────────────────────────────
    @bp.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for("logger.dashboard"))
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]
            confirm = request.form["confirm"]
            if not username or not password:
                flash("Username and password are required.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            elif User.query.filter_by(username=username).first():
                flash("Username already taken.", "error")
            else:
                user = User(username=username)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for("logger.dashboard"))
        return render_template("logger/signup.html")

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("logger.dashboard"))
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user, remember=True)
                next_page = request.args.get("next")
                return redirect(next_page or url_for("logger.dashboard"))
            flash("Invalid username or password.", "error")
        return render_template("logger/login.html")

    @bp.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("logger.login"))

    # ─── Pages ────────────────────────────────────────────────────────
    @bp.route("/")
    def dashboard():
        items = (
            Item.query.filter_by(user_id=current_user.id)
            .order_by(Item.created_at.desc())
            .all()
        )
        for item in items:
            item.apply_decay()
        db.session.commit()
        return render_template("logger/dashboard.html", items=items)

    @bp.route("/items/new", methods=["GET", "POST"])
    def create_item():
        if request.method == "POST":
            item = Item(
                user_id=current_user.id,
                name=request.form["name"],
                description=request.form.get("description", ""),
                frequency=float(request.form.get("frequency", 1)),
                alpha=float(request.form.get("alpha", 1)),
                decay_rate=float(request.form.get("decay_rate", 0.05)),
                target=float(request.form.get("target", 100)),
            )
            db.session.add(item)
            db.session.commit()
            return redirect(url_for("logger.dashboard"))
        return render_template("logger/item_form.html", item=None)

    @bp.route("/items/<int:item_id>")
    def item_detail(item_id):
        item = Item.query.filter_by(
            id=item_id, user_id=current_user.id
        ).first_or_404()
        item.apply_decay()
        db.session.commit()
        logs = item.logs.order_by(LogEntry.logged_at.desc()).limit(50).all()
        return render_template("logger/item_detail.html", item=item, logs=logs)

    @bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
    def edit_item(item_id):
        item = Item.query.filter_by(
            id=item_id, user_id=current_user.id
        ).first_or_404()
        if request.method == "POST":
            item.name = request.form["name"]
            item.description = request.form.get("description", "")
            item.frequency = float(request.form.get("frequency", 1))
            item.alpha = float(request.form.get("alpha", 1))
            item.decay_rate = float(request.form.get("decay_rate", 0.05))
            item.target = float(request.form.get("target", 100))
            db.session.commit()
            return redirect(url_for("logger.item_detail", item_id=item.id))
        return render_template("logger/item_form.html", item=item)

    @bp.route("/items/<int:item_id>/delete", methods=["POST"])
    def delete_item(item_id):
        item = Item.query.filter_by(
            id=item_id, user_id=current_user.id
        ).first_or_404()
        db.session.delete(item)
        db.session.commit()
        return redirect(url_for("logger.dashboard"))

    # ─── API ──────────────────────────────────────────────────────────
    @bp.route("/api/items/<int:item_id>/log", methods=["POST"])
    def api_log(item_id):
        item = Item.query.filter_by(
            id=item_id, user_id=current_user.id
        ).first_or_404()
        data = request.get_json(silent=True) or {}
        amount = data.get("amount")
        item.log(amount=float(amount) if amount is not None else None)
        db.session.commit()
        return jsonify(item.to_dict())

    @bp.route("/api/items/<int:item_id>")
    def api_item(item_id):
        item = Item.query.filter_by(
            id=item_id, user_id=current_user.id
        ).first_or_404()
        return jsonify(item.to_dict())

    @bp.route("/api/items")
    def api_items():
        items = (
            Item.query.filter_by(user_id=current_user.id)
            .order_by(Item.created_at.desc())
            .all()
        )
        return jsonify([i.to_dict() for i in items])
