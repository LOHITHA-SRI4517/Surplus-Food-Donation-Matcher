
from datetime import datetime, timezone, timedelta
from functools import wraps
import os
import sqlite3
import uuid
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort, make_response, send_from_directory
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import get_db, init_db, log_event
from services.safety_agent import check_food_safety
from services.workflow import can_create_pickup


app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "foodbridge-local-demo-key-change-before-deployment"
)

UPLOAD_FOLDER = Path(app.root_path) / "pickup_evidence"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

IST = timezone(timedelta(hours=5, minutes=30))
VALID_ROLES = ("restaurant", "ngo", "reviewer")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_local_datetime(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed


def home_for_role(role=None):
    role = role or session.get("role")

    if role in ("restaurant", "ngo"):
        return url_for("dashboard")
    if role == "reviewer":
        return url_for("reviewer_dashboard")

    return url_for("login")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                abort(403)

            return view(*args, **kwargs)
        return wrapped_view
    return decorator


def get_donation(db, donation_id):
    donation = db.execute(
        "SELECT * FROM donations WHERE id = ?",
        (donation_id,)
    ).fetchone()

    if donation is None:
        abort(404)

    return donation


def ensure_restaurant_owns(donation):
    if session.get("role") != "restaurant":
        abort(403)

    if donation["restaurant"] != session.get("restaurant_name"):
        abort(403)


def ensure_matched_ngo(donation):
    if session.get("role") != "ngo":
        abort(403)

    if donation["matched_ngo_id"] != session.get("ngo_id"):
        abort(403)


def get_visible_donations(db):
    role = session.get("role")

    evidence_fields = """
        p.evidence_filename AS evidence_filename,
        p.collected_at AS collected_at,
        p.collected_by AS collected_by,
        p.collection_notes AS collection_notes
    """

    if role == "restaurant":
        return db.execute(
            f"""
            SELECT d.*, n.name AS ngo_name, {evidence_fields}
            FROM donations d
            LEFT JOIN ngos n ON n.id = d.matched_ngo_id
            LEFT JOIN pickups p ON p.donation_id = d.id
            WHERE d.restaurant = ?
            ORDER BY d.id DESC
            """,
            (session.get("restaurant_name"),)
        ).fetchall()

    if role == "ngo":
        return db.execute(
            f"""
            SELECT d.*, n.name AS ngo_name, {evidence_fields}
            FROM donations d
            LEFT JOIN ngos n ON n.id = d.matched_ngo_id
            LEFT JOIN pickups p ON p.donation_id = d.id
            WHERE d.matched_ngo_id = ?
            ORDER BY d.id DESC
            """,
            (session.get("ngo_id"),)
        ).fetchall()

    if role == "reviewer":
        return db.execute(
            f"""
            SELECT d.*, n.name AS ngo_name, {evidence_fields}
            FROM donations d
            LEFT JOIN ngos n ON n.id = d.matched_ngo_id
            LEFT JOIN pickups p ON p.donation_id = d.id
            ORDER BY d.id DESC
            """
        ).fetchall()

    abort(403)


def get_summary(db, donations):
    donation_ids = [row["id"] for row in donations]

    if not donation_ids:
        return {
            "total": 0,
            "eligible": 0,
            "approval": 0,
            "pickups": 0,
        }

    placeholders = ",".join("?" for _ in donation_ids)

    eligible = db.execute(
        f"""
        SELECT COUNT(*) FROM donations
        WHERE id IN ({placeholders})
        AND matched_ngo_id IS NOT NULL
        """,
        donation_ids
    ).fetchone()[0]

    approval = db.execute(
        f"""
        SELECT COUNT(*) FROM donations
        WHERE id IN ({placeholders})
        AND status = 'AWAITING_HUMAN_APPROVAL'
        """,
        donation_ids
    ).fetchone()[0]

    pickups = db.execute(
        f"""
        SELECT COUNT(*) FROM pickups
        WHERE donation_id IN ({placeholders})
        AND status = 'COLLECTED'
        """,
        donation_ids
    ).fetchone()[0]

    return {
        "total": len(donations),
        "eligible": eligible,
        "approval": approval,
        "pickups": pickups,
    }


def render_role_dashboard():
    with get_db() as db:
        donations = get_visible_donations(db)
        summary = get_summary(db, donations)

        ngos = db.execute(
            "SELECT * FROM ngos ORDER BY name"
        ).fetchall()

        donation_ids = [d["id"] for d in donations]

        if donation_ids:
            placeholders = ",".join("?" for _ in donation_ids)
            recent_events = db.execute(
                f"""
                SELECT e.*, d.food_name
                FROM events e
                JOIN donations d ON d.id = e.donation_id
                WHERE e.donation_id IN ({placeholders})
                ORDER BY e.id DESC
                LIMIT 20
                """,
                donation_ids
            ).fetchall()
        else:
            recent_events = []

    return render_template(
        "dashboard.html",
        donations=donations,
        ngos=ngos,
        summary=summary,
        recent_events=recent_events,
    )


def allowed_evidence_extension(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def image_signature_is_valid(file_storage, extension):
    file_storage.stream.seek(0)
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)

    if extension in ("jpg", "jpeg"):
        return header.startswith(b"\xff\xd8\xff")

    if extension == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")

    if extension == "webp":
        return (
            len(header) >= 12
            and header[:4] == b"RIFF"
            and header[8:12] == b"WEBP"
        )

    return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(home_for_role())

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        organization_name = request.form.get(
            "organization_name", ""
        ).strip()
        city = request.form.get("city", "").strip()
        categories = request.form.get("categories", "").strip()
        capacity_text = request.form.get("capacity", "").strip()

        reviewer_code = request.form.get("reviewer_code", "").strip()
        expected_reviewer_code = os.environ.get(
            "REVIEWER_SIGNUP_CODE", ""
        )

        if role not in VALID_ROLES:
            flash("Please select a valid account type.", "error")
            return redirect(url_for("signup"))

        if len(username) < 4 or len(username) > 50:
            flash(
                "Username must contain 4 to 50 characters.",
                "error"
            )
            return redirect(url_for("signup"))

        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "error"
            )
            return redirect(url_for("signup"))

        if role == "reviewer":
            if not expected_reviewer_code:
                flash(
                    "Reviewer registration is not configured. "
                    "Please contact the project administrator.",
                    "error"
                )
                return redirect(url_for("signup"))

            if (
                not reviewer_code
                or reviewer_code != expected_reviewer_code
            ):
                flash("Invalid reviewer registration code.", "error")
                return redirect(url_for("signup"))

        else:
            if not all([organization_name, city]):
                flash(
                    "Please enter your organization name and city.",
                    "error"
                )
                return redirect(url_for("signup"))

        capacity = None

        if role == "ngo":
            if not categories or not capacity_text:
                flash(
                    "NGO food categories and capacity are required.",
                    "error"
                )
                return redirect(url_for("signup"))

            try:
                capacity = int(capacity_text)
                if capacity <= 0:
                    raise ValueError
            except ValueError:
                flash(
                    "Capacity must be a positive whole number.",
                    "error"
                )
                return redirect(url_for("signup"))

        try:
            with get_db() as db:
                existing_user = db.execute(
                    "SELECT id FROM users WHERE username = ?",
                    (username,)
                ).fetchone()

                if existing_user:
                    flash("Username already exists.", "error")
                    return redirect(url_for("signup"))

                password_hash = generate_password_hash(password)

                if role == "restaurant":
                    db.execute(
                        """
                        INSERT INTO users
                            (username, password_hash, role,
                             restaurant_name, ngo_id)
                        VALUES (?, ?, 'restaurant', ?, NULL)
                        """,
                        (username, password_hash, organization_name)
                    )

                elif role == "ngo":
                    ngo_code = "NGO-" + username

                    db.execute(
                        """
                        INSERT INTO ngos
                            (code, name, city, categories, capacity, available)
                        VALUES (?, ?, ?, ?, ?, 1)
                        """,
                        (
                            ngo_code,
                            organization_name,
                            city,
                            categories,
                            capacity
                        )
                    )

                    ngo = db.execute(
                        "SELECT id FROM ngos WHERE code = ?",
                        (ngo_code,)
                    ).fetchone()

                    db.execute(
                        """
                        INSERT INTO users
                            (username, password_hash, role,
                             restaurant_name, ngo_id)
                        VALUES (?, ?, 'ngo', NULL, ?)
                        """,
                        (username, password_hash, ngo["id"])
                    )

                elif role == "reviewer":
                    db.execute(
                        """
                        INSERT INTO users
                            (username, password_hash, role,
                             restaurant_name, ngo_id)
                        VALUES (?, ?, 'reviewer', NULL, NULL)
                        """,
                        (username, password_hash)
                    )

        except sqlite3.IntegrityError:
            flash(
                "Username or NGO code already exists. "
                "Please try another username.",
                "error"
            )
            return redirect(url_for("signup"))

        flash(
            "Account created successfully! Please log in.",
            "success"
        )
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(home_for_role())

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "").strip().lower()

        if selected_role not in VALID_ROLES:
            flash("Please select a valid role.", "error")
            return redirect(url_for("login"))

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()

        if (
            user
            and check_password_hash(user["password_hash"], password)
            and user["role"] == selected_role
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["restaurant_name"] = user["restaurant_name"]
            session["ngo_id"] = user["ngo_id"]

            flash("Login successful!", "success")
            return redirect(home_for_role(user["role"]))

        flash(
            "Invalid username, password, or selected role.",
            "error"
        )

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
@role_required("restaurant", "ngo")
def dashboard():
    return render_role_dashboard()


@app.route("/reviewer")
@login_required
@role_required("reviewer")
def reviewer_dashboard():
    return render_role_dashboard()


@app.route("/donations")
@login_required
@role_required("restaurant")
def donations_page():
    with get_db() as db:
        donations = get_visible_donations(db)

    return render_template("donations.html", donations=donations)


@app.route("/donate", methods=["POST"])
@role_required("restaurant")
def donate():
    restaurant = session.get("restaurant_name")
    food_name = request.form.get("food_name", "").strip()
    category = request.form.get("category", "").strip()
    city = request.form.get("city", "").strip()
    dropoff_location = request.form.get(
        "dropoff_location", ""
    ).strip()
    ngo_id_text = request.form.get("ngo_id", "").strip()

    try:
        ngo_id = int(ngo_id_text)
        quantity = int(request.form.get("quantity", "0"))
        prepared_at = parse_local_datetime(
            request.form.get("prepared_at", "")
        )
        pickup_deadline = parse_local_datetime(
            request.form.get("pickup_deadline", "")
        )
    except (ValueError, TypeError):
        flash(
            "Please select an NGO and enter valid quantity and date/time values.",
            "error"
        )
        return redirect(home_for_role())

    now = datetime.now(IST)

    if not all([
        restaurant, food_name, category, city, dropoff_location
    ]):
        flash("Please complete all donation fields.", "error")
        return redirect(home_for_role())

    if quantity <= 0:
        flash("Quantity must be greater than zero.", "error")
        return redirect(home_for_role())

    if prepared_at > now:
        flash("Preparation time cannot be in the future.", "error")
        return redirect(home_for_role())

    if pickup_deadline <= now:
        flash("Pickup deadline must be in the future.", "error")
        return redirect(home_for_role())

    if pickup_deadline <= prepared_at:
        flash(
            "Pickup deadline must be after preparation time.",
            "error"
        )
        return redirect(home_for_role())

    with get_db() as db:
        ngo = db.execute(
            """
            SELECT id, name, city, categories, capacity, available
            FROM ngos
            WHERE id = ?
            """,
            (ngo_id,)
        ).fetchone()

        if ngo is None:
            flash("Selected NGO does not exist.", "error")
            return redirect(home_for_role())

        if not ngo["available"]:
            flash(
                "This NGO is currently unavailable. Please select another NGO.",
                "error"
            )
            return redirect(home_for_role())

        if ngo["capacity"] < quantity:
            flash(
                f"{ngo['name']} does not have enough capacity for "
                f"{quantity} servings/items.",
                "error"
            )
            return redirect(home_for_role())

        supported_categories = [
            item.strip().casefold()
            for item in (ngo["categories"] or "").split(",")
        ]

        if category.casefold() not in supported_categories:
            flash(
                f"{ngo['name']} does not support the {category} category.",
                "error"
            )
            return redirect(home_for_role())

        safety_result = check_food_safety(
            category=category,
            prepared_at=prepared_at.isoformat(),
            now=now.astimezone(timezone.utc),
        )

        if isinstance(safety_result, dict):
            safety_ok = safety_result.get("safe", False)
            safety_reason = safety_result.get(
                "reason", "Food did not pass the safety check."
            )
        else:
            safety_ok = bool(safety_result)
            safety_reason = "Food did not pass the safety check."

        status = (
            "AWAITING_HUMAN_APPROVAL"
            if safety_ok else "SAFETY_REJECTED"
        )

        cursor = db.execute(
            """
            INSERT INTO donations
            (
                restaurant, food_name, category, quantity, city,
                prepared_at, pickup_deadline, dropoff_location,
                status, matched_ngo_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                restaurant, food_name, category, quantity, city,
                prepared_at.isoformat(),
                pickup_deadline.isoformat(),
                dropoff_location, status, ngo_id, utc_now()
            )
        )

        donation_id = cursor.lastrowid

        log_event(
            db, donation_id, "DONATION_REGISTERED",
            f"Donation registered by {restaurant}."
        )

        if not safety_ok:
            log_event(
                db, donation_id, "SAFETY_REJECTED", safety_reason
            )
            flash(
                f"Donation rejected by the safety check: {safety_reason}",
                "error"
            )
            return redirect(home_for_role())

        log_event(
            db, donation_id, "SAFETY_VERIFIED",
            "Donation passed the configured initial time-window check."
        )

        log_event(
            db, donation_id, "NGO_MATCHED",
            f"Restaurant selected {ngo['name']}. Awaiting human review."
        )

    flash(
        f"Donation registered and assigned to {ngo['name']}. "
        "Waiting for human approval.",
        "success"
    )
    return redirect(home_for_role())


@app.route("/approve/<int:donation_id>", methods=["POST"])
@role_required("reviewer")
def approve(donation_id):
    with get_db() as db:
        donation = get_donation(db, donation_id)

        if donation["status"] != "AWAITING_HUMAN_APPROVAL":
            flash(
                "This donation is not waiting for human approval.",
                "error"
            )
            return redirect(home_for_role())

        if donation["matched_ngo_id"] is None:
            flash(
                "Cannot approve a donation without an NGO match.",
                "error"
            )
            return redirect(home_for_role())

        db.execute(
            """
            INSERT INTO approvals (donation_id, approved_by, approved_at)
            VALUES (?, ?, ?)
            """,
            (donation_id, session["username"], utc_now())
        )

        db.execute(
            "UPDATE donations SET status = ? WHERE id = ?",
            ("AWAITING_NGO_ACCEPTANCE", donation_id)
        )

        db.execute(
            """
            INSERT OR IGNORE INTO pickups
                (donation_id, status, location, location_confirmed, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                donation_id, "NGO_PENDING",
                donation["dropoff_location"], utc_now()
            )
        )

        log_event(
            db, donation_id, "HUMAN_APPROVED",
            f"Approved by reviewer {session['username']}."
        )
        log_event(
            db, donation_id, "AWAITING_NGO_ACCEPTANCE",
            "Waiting for the matched NGO to respond."
        )

    flash("Donation approved and sent to the matched NGO.", "success")
    return redirect(home_for_role())


@app.route("/ngo/<int:donation_id>/<action>", methods=["POST"])
@role_required("ngo")
def ngo_action(donation_id, action):
    if action not in ("accept", "reject"):
        abort(400)

    with get_db() as db:
        donation = get_donation(db, donation_id)
        ensure_matched_ngo(donation)

        if donation["status"] != "AWAITING_NGO_ACCEPTANCE":
            flash(
                "This donation is not awaiting NGO acceptance.",
                "error"
            )
            return redirect(home_for_role())

        if action == "reject":
            db.execute(
                "UPDATE donations SET status = ? WHERE id = ?",
                ("NGO_REJECTED", donation_id)
            )
            db.execute(
                "UPDATE pickups SET status = ? WHERE donation_id = ?",
                ("CANCELLED", donation_id)
            )
            log_event(
                db, donation_id, "NGO_REJECTED",
                f"Rejected by matched NGO {session['username']}."
            )
            flash("Donation rejected.", "success")

        else:
            db.execute(
                "UPDATE donations SET status = ? WHERE id = ?",
                ("NGO_ACCEPTED", donation_id)
            )

            pickup = db.execute(
                "SELECT * FROM pickups WHERE donation_id = ?",
                (donation_id,)
            ).fetchone()

            if pickup is None:
                db.execute(
                    """
                    INSERT INTO pickups
                        (donation_id, status, location, location_confirmed, created_at)
                    VALUES (?, ?, ?, 0, ?)
                    """,
                    (
                        donation_id,
                        "BLOCKED_LOCATION_RECONFIRMATION",
                        donation["dropoff_location"],
                        utc_now()
                    )
                )
            elif pickup["location_confirmed"]:
                db.execute(
                    "UPDATE pickups SET status = ? WHERE donation_id = ?",
                    ("READY_FOR_COLLECTION", donation_id)
                )
            else:
                db.execute(
                    "UPDATE pickups SET status = ? WHERE donation_id = ?",
                    ("BLOCKED_LOCATION_RECONFIRMATION", donation_id)
                )

            log_event(
                db, donation_id, "NGO_ACCEPTED",
                f"Accepted by matched NGO {session['username']}."
            )
            log_event(
                db, donation_id, "PICKUP_STATUS_UPDATED",
                "Pickup readiness depends on location confirmation."
            )
            flash(
                "Donation accepted. Confirm the pickup location before collection.",
                "success"
            )

    return redirect(home_for_role())


@app.route("/location/<int:donation_id>", methods=["POST"])
@role_required("restaurant")
def update_location(donation_id):
    new_location = request.form.get(
        "dropoff_location", ""
    ).strip()

    if not new_location:
        flash("Location cannot be empty.", "error")
        return redirect(home_for_role())

    with get_db() as db:
        donation = get_donation(db, donation_id)
        ensure_restaurant_owns(donation)

        if donation["status"] in (
            "COLLECTED", "NGO_REJECTED", "SAFETY_REJECTED"
        ):
            flash(
                "Location cannot be changed at this stage.",
                "error"
            )
            return redirect(home_for_role())

        db.execute(
            "UPDATE donations SET dropoff_location = ? WHERE id = ?",
            (new_location, donation_id)
        )

        pickup = db.execute(
            "SELECT * FROM pickups WHERE donation_id = ?",
            (donation_id,)
        ).fetchone()

        if pickup:
            db.execute(
                """
                UPDATE pickups
                SET location = ?, location_confirmed = 0, status = ?
                WHERE donation_id = ?
                """,
                (
                    new_location,
                    "BLOCKED_LOCATION_RECONFIRMATION",
                    donation_id
                )
            )

        log_event(
            db, donation_id, "LOCATION_UPDATED",
            "Restaurant changed the pickup location. NGO reconfirmation is required."
        )

    flash(
        "Location updated. The NGO must reconfirm before pickup.",
        "success"
    )
    return redirect(home_for_role())


@app.route("/location/<int:donation_id>/confirm", methods=["POST"])
@role_required("ngo")
def confirm_location(donation_id):
    with get_db() as db:
        donation = get_donation(db, donation_id)
        ensure_matched_ngo(donation)

        if donation["status"] not in (
            "NGO_ACCEPTED", "AWAITING_NGO_ACCEPTANCE"
        ):
            flash(
                "Location cannot be confirmed at this stage.",
                "error"
            )
            return redirect(home_for_role())

        pickup = db.execute(
            "SELECT * FROM pickups WHERE donation_id = ?",
            (donation_id,)
        ).fetchone()

        new_status = (
            "READY_FOR_COLLECTION"
            if donation["status"] == "NGO_ACCEPTED"
            else "NGO_PENDING"
        )

        if pickup is None:
            db.execute(
                """
                INSERT INTO pickups
                    (donation_id, status, location, location_confirmed, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    donation_id, new_status,
                    donation["dropoff_location"], utc_now()
                )
            )
        else:
            db.execute(
                """
                UPDATE pickups
                SET location = ?, location_confirmed = 1, status = ?
                WHERE donation_id = ?
                """,
                (
                    donation["dropoff_location"],
                    new_status,
                    donation_id
                )
            )

        log_event(
            db, donation_id, "LOCATION_CONFIRMED",
            f"Pickup location confirmed by matched NGO {session['username']}."
        )

    flash("Pickup location confirmed.", "success")
    return redirect(home_for_role())


@app.route("/pickup/<int:donation_id>/collect", methods=["POST"])
@role_required("ngo")
def collect_pickup(donation_id):
    evidence_file = request.files.get("evidence")
    notes = request.form.get("evidence_notes", "").strip()

    if len(notes) > 500:
        flash("Evidence notes must be 500 characters or fewer.", "error")
        return redirect(home_for_role())

    if evidence_file is None or not evidence_file.filename:
        flash(
            "Upload a pickup evidence photo before marking collected.",
            "error"
        )
        return redirect(home_for_role())

    original_filename = secure_filename(evidence_file.filename)

    if (
        not original_filename
        or not allowed_evidence_extension(original_filename)
    ):
        flash(
            "Upload a JPG, JPEG, PNG, or WEBP image.",
            "error"
        )
        return redirect(home_for_role())

    extension = original_filename.rsplit(".", 1)[1].lower()

    if not image_signature_is_valid(evidence_file, extension):
        flash(
            "The uploaded file does not appear to be a valid supported image.",
            "error"
        )
        return redirect(home_for_role())

    with get_db() as db:
        donation = get_donation(db, donation_id)
        ensure_matched_ngo(donation)

        pickup = db.execute(
            "SELECT * FROM pickups WHERE donation_id = ?",
            (donation_id,)
        ).fetchone()

        if pickup is None:
            flash("Pickup record does not exist.", "error")
            return redirect(home_for_role())

        allowed = can_create_pickup(
            "APPROVED"
            if donation["status"] == "NGO_ACCEPTED"
            else donation["status"],
            donation["status"] == "NGO_ACCEPTED",
            bool(pickup["location_confirmed"]),
        )

        if (
            not allowed
            or pickup["status"] != "READY_FOR_COLLECTION"
            or donation["status"] != "NGO_ACCEPTED"
            or not pickup["location_confirmed"]
        ):
            flash(
                "Pickup is blocked. Ensure NGO acceptance and location confirmation.",
                "error"
            )
            return redirect(home_for_role())

        stored_filename = f"{uuid.uuid4().hex}.{extension}"
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        stored_path = UPLOAD_FOLDER / stored_filename

        try:
            evidence_file.save(str(stored_path))
            collected_at = utc_now()
            collected_by = session["username"]

            db.execute(
                """
                UPDATE pickups
                SET status = ?,
                    evidence_filename = ?,
                    collected_at = ?,
                    collected_by = ?,
                    collection_notes = ?
                WHERE donation_id = ?
                """,
                (
                    "COLLECTED",
                    stored_filename,
                    collected_at,
                    collected_by,
                    notes or None,
                    donation_id
                )
            )

            db.execute(
                "UPDATE donations SET status = ? WHERE id = ?",
                ("COLLECTED", donation_id)
            )

            log_event(
                db, donation_id, "COLLECTED",
                f"Collection recorded by matched NGO {collected_by}; "
                f"evidence photo uploaded at {collected_at}."
            )

            if notes:
                log_event(
                    db, donation_id, "COLLECTION_NOTES",
                    f"NGO collection note: {notes}"
                )

        except Exception:
            if stored_path.exists():
                stored_path.unlink()
            raise

    flash(
        "Pickup marked as collected. Evidence photo and collection details saved.",
        "success"
    )
    return redirect(home_for_role())


@app.route("/pickup/<int:donation_id>/evidence")
@login_required
def view_pickup_evidence(donation_id):
    with get_db() as db:
        donation = get_donation(db, donation_id)
        role = session.get("role")

        if role == "restaurant":
            ensure_restaurant_owns(donation)
        elif role == "ngo":
            ensure_matched_ngo(donation)
        elif role != "reviewer":
            abort(403)

        pickup = db.execute(
            """
            SELECT evidence_filename
            FROM pickups
            WHERE donation_id = ?
            """,
            (donation_id,)
        ).fetchone()

        if pickup is None or not pickup["evidence_filename"]:
            abort(404)

        filename = pickup["evidence_filename"]

    if filename.lower().endswith((".jpg", ".jpeg")):
        mimetype = "image/jpeg"
    elif filename.lower().endswith(".png"):
        mimetype = "image/png"
    else:
        mimetype = "image/webp"

    response = send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        mimetype=mimetype,
        as_attachment=False
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/tests")
@login_required
def tests_page():
    return render_template("test_cases.html")


@app.errorhandler(403)
def forbidden(_error):
    response = make_response(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Restricted | FoodBridge</title>
            <style>
                body {
                    margin: 0; min-height: 100vh; display: grid;
                    place-items: center; padding: 20px;
                    font-family: Arial, sans-serif;
                    background: #ecfdf5; color: #166534;
                }
                main {
                    max-width: 520px; padding: 32px; text-align: center;
                    background: white; border-radius: 18px;
                    box-shadow: 0 12px 40px #0001;
                }
                a {
                    display: inline-block; padding: 12px 20px;
                    background: #16a34a; color: white;
                    border-radius: 8px; text-decoration: none;
                }
            </style>
        </head>
        <body>
            <main>
                <h1>Access Restricted</h1>
                <p>This page is not available for your account role.</p>
                <a href="/login">Login to Your Account</a>
            </main>
        </body>
        </html>
        """,
        403
    )
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


@app.errorhandler(404)
def not_found(_error):
    return "Page not found.", 404


@app.errorhandler(413)
def upload_too_large(_error):
    flash("Photo is too large. Maximum upload size is 5 MB.", "error")
    return redirect(home_for_role())


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
