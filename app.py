from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, flash
)
import re
from functools import wraps
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Secret key untuk session — WAJIB ada.
# Ganti dengan string acak saat deploy ke server perusahaan.
app.secret_key = "ganti-ini-dengan-string-acak-panjang-saat-deploy"

# Aturan akun (dipakai juga oleh create_user.py)
VALID_ROLES = ("admin", "user")
MIN_PASSWORD_LENGTH = 6
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{3,50}")


def get_database_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="cctv_monitoring"
    )


# =====================================================
# SESI SELALU MENGIKUTI DATABASE
# =====================================================
@app.before_request
def sync_session_with_database():

    if "user_id" not in session or request.endpoint in (None, "static"):
        return None

    try:
        db = get_database_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, full_name, role FROM users WHERE id = %s",
            (session["user_id"],)
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()
    except mysql.connector.Error:
        return None

    if user is None:
        session.clear()
        flash("Your account is no longer available. Please sign in again.", "warning")
        return redirect(url_for("login"))

    for key in ("username", "full_name", "role"):
        if session.get(key) != user[key]:
            session[key] = user[key]

    return None


# =====================================================
# DECORATORS
# =====================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                flash("Anda tidak punya akses ke halaman ini.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =====================================================
# ROUTE: LOGIN
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username dan password wajib diisi.", "danger")
            return render_template("login.html")

        db = get_database_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Selamat datang, {user['full_name']}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Username atau password salah.", "danger")
            return render_template("login.html")

    return render_template("login.html")


# =====================================================
# ROUTE: LOGOUT
# =====================================================
@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah logout.", "success")
    return redirect(url_for("login"))


# =====================================================
# ROUTE: DASHBOARD
# =====================================================
@app.route("/")
@login_required
def home():

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM detections ORDER BY id DESC LIMIT 1")
    detection = cursor.fetchone()

    activities = []
    if detection:
        cursor.execute("""
            SELECT person_id, activity, duration
            FROM activities
            WHERE detection_id = %s
            ORDER BY person_id
        """, (detection["id"],))
        activities = cursor.fetchall()

    cursor.execute("SELECT COUNT(DISTINCT camera_id) AS total FROM detections")
    total_cameras = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        detection=detection,
        activities=activities,
        total_cameras=total_cameras,
        camera_id=detection["camera_id"] if detection else "-",
        active_page="dashboard"
    )


# =====================================================
# ROUTE: HISTORY
# =====================================================
@app.route("/history")
@login_required
def history():

    date_from = request.args.get("date_from", "").strip()
    date_to   = request.args.get("date_to", "").strip()
    camera    = request.args.get("camera", "").strip()
    activity  = request.args.get("activity", "").strip()
    page      = request.args.get("page", 1, type=int)

    if page < 1:
        page = 1

    per_page = 10
    offset = (page - 1) * per_page

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    where_clauses = ["1=1"]
    params = []

    if date_from:
        where_clauses.append("DATE(d.timestamp) >= %s")
        params.append(date_from)

    if date_to:
        where_clauses.append("DATE(d.timestamp) <= %s")
        params.append(date_to)

    if camera:
        where_clauses.append("d.camera_id = %s")
        params.append(camera)

    if activity:
        where_clauses.append("""
            d.id IN (
                SELECT detection_id FROM activities WHERE activity = %s
            )
        """)
        params.append(activity)

    where_sql = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(*) AS total FROM detections d WHERE {where_sql}"
    cursor.execute(count_sql, tuple(params))
    total_rows = cursor.fetchone()["total"]
    total_pages = max(1, (total_rows + per_page - 1) // per_page)

    # Query utama dengan tambahan sub-query 'details'
    data_sql = f"""
        SELECT
            d.id,
            d.camera_id,
            d.timestamp,
            d.person_count,
            GROUP_CONCAT(DISTINCT a.activity ORDER BY a.activity SEPARATOR ', ') AS activities,
            (
                SELECT GROUP_CONCAT(
                    CONCAT(a2.person_id, ':', a2.activity, ':', a2.duration) 
                    SEPARATOR '|'
                )
                FROM activities a2
                WHERE a2.detection_id = d.id
            ) AS details
        FROM detections d
        LEFT JOIN activities a ON a.detection_id = d.id
        WHERE {where_sql}
        GROUP BY d.id, d.camera_id, d.timestamp, d.person_count
        ORDER BY d.id DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute(data_sql, tuple(params) + (per_page, offset))
    rows = cursor.fetchall()

    cursor.execute("SELECT DISTINCT camera_id FROM detections ORDER BY camera_id")
    cameras = [r["camera_id"] for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT activity FROM activities ORDER BY activity")
    activities_list = [r["activity"] for r in cursor.fetchall()]

    cursor.close()
    db.close()

    return render_template(
        "history.html",
        rows=rows,
        cameras=cameras,
        activities_list=activities_list,
        date_from=date_from,
        date_to=date_to,
        camera=camera,
        activity=activity,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        active_page="history"
    )

# =====================================================
# ROUTE: HISTORY DETAIL
# =====================================================
@app.route("/history/detail/<int:detection_id>")
@login_required
def history_detail(detection_id):

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    # 1. Ambil data deteksi utama
    cursor.execute("SELECT * FROM detections WHERE id = %s", (detection_id,))
    detection = cursor.fetchone()

    if not detection:
        cursor.close()
        db.close()
        flash("Detection record not found.", "danger")
        return redirect(url_for("history"))

    # 2. Ambil detail aktivitas per orang
    cursor.execute("""
        SELECT person_id, activity, duration
        FROM activities
        WHERE detection_id = %s
        ORDER BY person_id ASC
    """, (detection_id,))
    activities = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "history_detail.html",
        detection=detection,
        activities=activities,
        active_page="history"
    )
# =====================================================
# ROUTE: STATISTICS
# =====================================================
@app.route("/statistics")
@login_required
def statistics():

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    # 1. Ringkasan
    cursor.execute("""
        SELECT
            COUNT(*) AS total_detections,
            COALESCE(SUM(person_count), 0) AS total_persons
        FROM detections
    """)
    summary = cursor.fetchone()

    total_detections = summary["total_detections"]
    total_persons = int(summary["total_persons"])
    avg_persons = round(total_persons / total_detections, 2) if total_detections > 0 else 0

    # 2. Top activity
    cursor.execute("""
        SELECT activity, COUNT(*) AS jumlah
        FROM activities
        GROUP BY activity
        ORDER BY jumlah DESC
        LIMIT 1
    """)
    top_activity_row = cursor.fetchone()
    top_activity = top_activity_row["activity"] if top_activity_row else "-"
    top_activity_count = top_activity_row["jumlah"] if top_activity_row else 0

    # 3. Tren Harian
    cursor.execute("""
        SELECT
            DATE(timestamp) AS tanggal,
            SUM(person_count) AS total_orang,
            COUNT(*) AS jumlah_deteksi
        FROM detections
        GROUP BY DATE(timestamp)
        ORDER BY tanggal ASC
    """)
    daily_rows = cursor.fetchall()

    daily_labels = [str(r["tanggal"]) if r["tanggal"] else "-" for r in daily_rows]
    daily_persons = [int(r["total_orang"]) if r["total_orang"] else 0 for r in daily_rows]
    daily_detections = [int(r["jumlah_deteksi"]) if r["jumlah_deteksi"] else 0 for r in daily_rows]

    # 4. Pola Per Jam & Peak Hour
    cursor.execute("""
        SELECT
            HOUR(d.timestamp) AS jam,
            COUNT(DISTINCT d.id) AS total_deteksi,
            COALESCE(SUM(d.person_count), 0) AS total_orang,
            COUNT(CASE WHEN a.activity = 'standing' THEN 1 END) AS kejadian_standing,
            COUNT(CASE WHEN a.activity = 'sitting' THEN 1 END) AS kejadian_sitting,
            COUNT(CASE WHEN a.activity = 'walking' THEN 1 END) AS kejadian_walking
        FROM detections d
        LEFT JOIN activities a ON a.detection_id = d.id
        GROUP BY HOUR(d.timestamp)
        ORDER BY jam ASC
    """)
    hourly_rows = cursor.fetchall()
    
    hourly_by_hour = {int(r["jam"]): r for r in hourly_rows if r["jam"] is not None}

    hourly_labels = [f"{hour:02d}:00" for hour in range(24)]
    hourly_persons = [
        int(hourly_by_hour[hour]["total_orang"] or 0) if hour in hourly_by_hour else 0
        for hour in range(24)
    ]
    hourly_detections = [
        int(hourly_by_hour[hour]["total_deteksi"] or 0) if hour in hourly_by_hour else 0
        for hour in range(24)
    ]
    hourly_standing = [
        int(hourly_by_hour[hour]["kejadian_standing"] or 0) if hour in hourly_by_hour else 0
        for hour in range(24)
    ]
    hourly_sitting = [
        int(hourly_by_hour[hour]["kejadian_sitting"] or 0) if hour in hourly_by_hour else 0
        for hour in range(24)
    ]
    hourly_walking = [
        int(hourly_by_hour[hour]["kejadian_walking"] or 0) if hour in hourly_by_hour else 0
        for hour in range(24)
    ]

    # Cari Peak Hour
    peak_hour_label = "-"
    peak_hour_count = 0
    max_detections = -1
    
    for hour in range(24):
        if hour in hourly_by_hour:
            det_count = int(hourly_by_hour[hour]["total_deteksi"] or 0)
            if det_count > max_detections:
                max_detections = det_count
                peak_hour_label = f"{hour:02d}:00 - {hour:02d}:59"
                peak_hour_count = det_count

    # 5. Distribusi Aktivitas
    cursor.execute("""
        SELECT activity, COUNT(*) AS jumlah
        FROM activities
        GROUP BY activity
        ORDER BY jumlah DESC
    """)
    activity_rows = cursor.fetchall()

    activity_labels = [r["activity"] for r in activity_rows if r["activity"]]
    activity_counts = [int(r["jumlah"]) for r in activity_rows]

    cursor.close()
    db.close()

    return render_template(
        "statistics.html",
        total_detections=total_detections,
        total_persons=total_persons,
        avg_persons=avg_persons,
        top_activity=top_activity,
        top_activity_count=top_activity_count,
        daily_labels=daily_labels,
        daily_persons=daily_persons,
        daily_detections=daily_detections,
        hourly_labels=hourly_labels,
        hourly_persons=hourly_persons,
        hourly_detections=hourly_detections,
        hourly_standing=hourly_standing,
        hourly_sitting=hourly_sitting,
        hourly_walking=hourly_walking,
        peak_hour_label=peak_hour_label,
        peak_hour_count=peak_hour_count,
        activity_labels=activity_labels,
        activity_counts=activity_counts,
        activity_rows=activity_rows,
        active_page="statistics"
    )


# =====================================================
# ROUTE: MONITORING
# =====================================================
@app.route("/monitoring")
@login_required
def monitoring():

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT DISTINCT camera_id FROM detections ORDER BY camera_id")
    cameras = [r["camera_id"] for r in cursor.fetchall()]

    selected_camera = request.args.get("camera", "").strip()
    if not selected_camera and cameras:
        selected_camera = cameras[0]

    # --- FITUR BARU: Ambil Riwayat Timeline ---
    timeline_data = []
    if selected_camera:
        cursor.execute("""
            SELECT 
                TIME(d.timestamp) AS time_only,
                a.person_id, 
                a.activity, 
                a.duration
            FROM activities a
            JOIN detections d ON a.detection_id = d.id
            WHERE d.camera_id = %s
            ORDER BY d.timestamp DESC, a.person_id ASC
            LIMIT 10
        """, (selected_camera,))
        timeline_data = cursor.fetchall()
    # -------------------------------------------

    cursor.close()
    db.close()

    return render_template(
        "monitoring.html",
        cameras=cameras,
        selected_camera=selected_camera,
        timeline_data=timeline_data,
        active_page="monitoring"
    )

# =====================================================
# ROUTE: USER MANAGEMENT (khusus Admin)
# =====================================================

@app.route("/users")
@role_required("admin")
def users_list():

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, username, full_name, role, created_at
        FROM users
        ORDER BY id ASC
    """)
    users = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("users.html", users=users, active_page="users")


@app.route("/users/add", methods=["GET", "POST"])
@role_required("admin")
def users_add():

    if request.method == "POST":

        username  = request.form.get("username", "").strip()
        password  = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        role      = request.form.get("role", "").strip()

        errors = []

        if not username:
            errors.append("Username is required.")
        elif not USERNAME_PATTERN.fullmatch(username):
            errors.append("Username must be 3-50 characters: letters, numbers, dot, underscore, or hyphen.")

        if not full_name:
            errors.append("Full name is required.")
        elif len(full_name) > 100:
            errors.append("Full name must be 100 characters or fewer.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

        if role not in VALID_ROLES:
            errors.append("Invalid role.")

        if not errors:
            db = get_database_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            existing = cursor.fetchone()
            cursor.close()
            db.close()

            if existing:
                errors.append(f"Username '{username}' is already taken.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "user_form.html",
                mode="add",
                user={"username": username, "full_name": full_name, "role": role},
                active_page="users"
            )

        db = get_database_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
        """, (username, generate_password_hash(password), full_name, role))

        db.commit()
        cursor.close()
        db.close()

        flash(f"User '{username}' was added.", "success")
        return redirect(url_for("users_list"))

    return render_template(
        "user_form.html",
        mode="add",
        user={"username": "", "full_name": "", "role": "user"},
        active_page="users"
    )


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@role_required("admin")
def users_edit(user_id):

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        db.close()
        flash("User not found.", "danger")
        return redirect(url_for("users_list"))

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        role      = request.form.get("role", "").strip()
        password  = request.form.get("password", "")

        errors = []

        if not full_name:
            errors.append("Full name is required.")
        elif len(full_name) > 100:
            errors.append("Full name must be 100 characters or fewer.")

        if role not in VALID_ROLES:
            errors.append("Invalid role.")

        if password and len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")

        if not errors and user["role"] == "admin" and role != "admin":
            cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
            if cursor.fetchone()["total"] <= 1:
                errors.append("This is the last admin. Make another user an admin first.")

        if errors:
            for err in errors:
                flash(err, "danger")
            cursor.close()
            db.close()
            form_user = dict(user)
            form_user["full_name"] = full_name
            form_user["role"] = role
            return render_template("user_form.html", mode="edit", user=form_user, active_page="users")

        if password:
            cursor.execute("""
                UPDATE users
                SET full_name = %s, role = %s, password_hash = %s
                WHERE id = %s
            """, (full_name, role, generate_password_hash(password), user_id))
        else:
            cursor.execute("""
                UPDATE users
                SET full_name = %s, role = %s
                WHERE id = %s
            """, (full_name, role, user_id))

        db.commit()
        cursor.close()
        db.close()

        flash(f"User '{user['username']}' was updated.", "success")

        if user_id == session.get("user_id") and role != "admin":
            return redirect(url_for("home"))

        return redirect(url_for("users_list"))

    cursor.close()
    db.close()
    return render_template("user_form.html", mode="edit", user=user, active_page="users")


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@role_required("admin")
def users_delete(user_id):

    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("users_list"))

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        db.close()
        flash("User not found.", "danger")
        return redirect(url_for("users_list"))

    if user["role"] == "admin":
        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
        total_admin = cursor.fetchone()["total"]
        if total_admin <= 1:
            cursor.close()
            db.close()
            flash("Cannot delete the last admin.", "danger")
            return redirect(url_for("users_list"))

    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()

    cursor.close()
    db.close()

    flash(f"User '{user['username']}' was deleted.", "success")
    return redirect(url_for("users_list"))


# =====================================================
# ROUTE: AKUN SAYA
# =====================================================
@app.route("/account", methods=["GET", "POST"])
@login_required
def account():

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, username, full_name, role, password_hash
        FROM users
        WHERE id = %s
    """, (session["user_id"],))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        db.close()
        session.clear()
        return redirect(url_for("login"))

    profile = {
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"]
    }

    if request.method == "POST":

        current_password = request.form.get("current_password", "")
        new_password     = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []

        if not check_password_hash(user["password_hash"], current_password):
            errors.append("Current password is incorrect.")

        if len(new_password) < MIN_PASSWORD_LENGTH:
            errors.append(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")
        elif new_password != confirm_password:
            errors.append("New password and confirmation do not match.")
        elif new_password == current_password:
            errors.append("New password must be different from the current password.")

        if errors:
            for err in errors:
                flash(err, "danger")
            cursor.close()
            db.close()
            return render_template("account.html", user=profile, active_page="account")

        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (generate_password_hash(new_password), user["id"])
        )
        db.commit()
        cursor.close()
        db.close()

        flash("Your password has been changed.", "success")
        return redirect(url_for("account"))

    cursor.close()
    db.close()
    return render_template("account.html", user=profile, active_page="account")


# =====================================================
# API: LATEST DATA
# =====================================================
@app.route("/api/latest")
@login_required
def api_latest():

    camera = request.args.get("camera", "").strip()

    db = get_database_connection()
    cursor = db.cursor(dictionary=True)

    if camera:
        cursor.execute("SELECT * FROM detections WHERE camera_id = %s ORDER BY id DESC LIMIT 1", (camera,))
    else:
        cursor.execute("SELECT * FROM detections ORDER BY id DESC LIMIT 1")

    detection = cursor.fetchone()

    activities = []
    if detection:
        cursor.execute("""
            SELECT person_id, activity, duration
            FROM activities
            WHERE detection_id = %s
            ORDER BY person_id
        """, (detection["id"],))
        activities = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify({
        "has_data": detection is not None,
        "camera_id": detection["camera_id"] if detection else None,
        "timestamp": str(detection["timestamp"]) if detection else None,
        "person_count": detection["person_count"] if detection else 0,
        "activities": activities
    })


# =====================================================
# ROUTE: API PENERIMA DATA AI ENGINE
# =====================================================
@app.route("/api/detection", methods=["POST"])
def receive_detection():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Request harus menggunakan JSON yang valid."}), 400

    required_fields = ["camera_id", "timestamp", "person_count", "activities"]
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({"status": "error", "message": "Field wajib belum lengkap.", "missing_fields": missing_fields}), 400

    camera_id = data["camera_id"]
    timestamp_text = data["timestamp"]
    person_count = data["person_count"]
    activities = data["activities"]

    if not isinstance(camera_id, str) or not camera_id.strip() or len(camera_id.strip()) > 50:
        return jsonify({"status": "error", "message": "camera_id harus berupa teks 1-50 karakter."}), 400

    if not isinstance(timestamp_text, str):
        return jsonify({"status": "error", "message": "timestamp harus berupa teks."}), 400

    try:
        timestamp_value = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"status": "error", "message": "Format timestamp harus YYYY-MM-DD HH:MM:SS."}), 400

    if type(person_count) is not int or person_count < 0:
        return jsonify({"status": "error", "message": "person_count harus bilangan bulat >= 0."}), 400

    if not isinstance(activities, list):
        return jsonify({"status": "error", "message": "activities harus berupa daftar JSON."}), 400

    for index, person in enumerate(activities):
        if not isinstance(person, dict):
            return jsonify({"status": "error", "message": f"Aktivitas ke-{index + 1} tidak valid."}), 400

        required_activity_fields = ["person_id", "activity", "duration"]
        missing_activity_fields = [field for field in required_activity_fields if field not in person]

        if missing_activity_fields:
            return jsonify({"status": "error", "message": f"Field aktivitas ke-{index + 1} belum lengkap.", "missing_fields": missing_activity_fields}), 400

        if type(person["person_id"]) is not int or person["person_id"] < 1:
            return jsonify({"status": "error", "message": "person_id harus bilangan bulat positif."}), 400

        if not isinstance(person["activity"], str) or not person["activity"].strip() or len(person["activity"].strip()) > 50:
            return jsonify({"status": "error", "message": "activity harus berupa teks 1-50 karakter."}), 400

        if type(person["duration"]) is not int or person["duration"] < 0:
            return jsonify({"status": "error", "message": "duration harus bilangan bulat >= 0."}), 400

    db = None
    cursor = None

    try:
        db = get_database_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO detections (camera_id, timestamp, person_count)
            VALUES (%s, %s, %s)
        """, (camera_id.strip(), timestamp_value, person_count))

        detection_id = cursor.lastrowid

        if activities:
            sql_activity = """
                INSERT INTO activities (detection_id, person_id, activity, duration)
                VALUES (%s, %s, %s, %s)
            """
            activity_values = [
                (detection_id, person["person_id"], person["activity"].strip(), person["duration"])
                for person in activities
            ]
            cursor.executemany(sql_activity, activity_values)

        db.commit()

        return jsonify({
            "status": "success",
            "message": "Data deteksi dan aktivitas berhasil disimpan.",
            "detection_id": detection_id
        }), 201

    except mysql.connector.Error:
        if db is not None:
            try:
                db.rollback()
            except mysql.connector.Error:
                pass
        return jsonify({"status": "error", "message": "Data gagal disimpan ke database."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if db is not None and db.is_connected():
            db.close()

if __name__ == "__main__":
    app.run(debug=True)