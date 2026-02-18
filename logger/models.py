from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Import db from the package (single instance shared with the app)
from . import db


def _utcnow():
    return datetime.utcnow()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    items = db.relationship(
        "Item", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Item(db.Model):
    """A trackable goal / habit."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")

    # --- core parameters ---
    frequency = db.Column(
        db.Float, nullable=False, default=1.0
    )  # frequency in days
    alpha = db.Column(db.Float, nullable=False, default=1.0)  # increase per log
    decay_rate = db.Column(
        db.Float, nullable=False, default=0.05
    )  # fraction lost per missed period
    target = db.Column(db.Float, nullable=False, default=100.0)

    # --- live state ---
    current_value = db.Column(db.Float, nullable=False, default=0.0)
    streak = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    logs = db.relationship(
        "LogEntry", backref="item", lazy="dynamic", cascade="all, delete-orphan"
    )

    # ---------- helpers ----------
    @property
    def progress(self) -> float:
        """0‑1 clamped progress toward target."""
        if self.target <= 0:
            return 1.0
        return min(max(self.current_value / self.target, 0.0), 1.0)

    @property
    def frequency_hours(self) -> float:
        return float(self.frequency) * 24

    def apply_decay(self) -> float:
        """Apply time‑based decay since last update.  Returns periods missed."""
        now = datetime.utcnow()
        elapsed_hours = (now - self.updated_at).total_seconds() / 3600
        periods_missed = elapsed_hours / self.frequency_hours

        if periods_missed >= 1.0:
            decay_factor = (1 - self.decay_rate) ** int(periods_missed)
            self.current_value = max(self.current_value * decay_factor, 0.0)
            if periods_missed >= 2:
                self.streak = 0
            self.updated_at = now

        return periods_missed

    def log(self, amount: float | None = None) -> "LogEntry":
        """Record one log entry and bump current_value."""
        self.apply_decay()
        increment = amount if amount is not None else self.alpha
        self.current_value = min(self.current_value + increment, self.target)
        self.streak += 1
        self.updated_at = datetime.utcnow()

        entry = LogEntry(item_id=self.id, amount=increment)
        db.session.add(entry)
        return entry

    def to_dict(self) -> dict:
        self.apply_decay()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency,
            "alpha": self.alpha,
            "decay_rate": self.decay_rate,
            "target": self.target,
            "current_value": round(self.current_value, 2),
            "progress": round(self.progress, 4),
            "streak": self.streak,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class LogEntry(db.Model):
    __tablename__ = "log_entries"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    logged_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
