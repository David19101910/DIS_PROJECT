"""
app.py — DarkFleet Flask webapplication
"""

import re
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = "darkfleet_secret_2026"
bcrypt = Bcrypt(app)

DB_CONFIG = {
    "dbname": "darkfleet",
    "user": "postgres",
    "password": "Ostenfeld35",
    "host":   "localhost",
    "port": 5432,
}

# Regex for validation (course requirement)
MMSI_RE = re.compile(r"^\d{9}$")
IMO_RE  = re.compile(r"^IMO\d{7}$", re.IGNORECASE)

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def validate_search(query):
    """Detect search type using regex matching."""
    q = query.strip()
    if MMSI_RE.match(q):
        return "mmsi", q
    if IMO_RE.match(q):
        return "imo", q.upper()
    return "name", q

# Front page
@app.route("/")
def index():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT vessel_id, mmsi, name, current_flag, total_score, risk_level
        FROM suspicion_score
        WHERE total_score > 0
        ORDER BY total_score DESC
        LIMIT 10
    """)
    top_vessels = cur.fetchall()

    cur.execute("""
        SELECT v.name, v.mmsi, p.latitude, p.longitude, p.speed_knots, p.recorded_at
        FROM position p
        JOIN vessel v ON v.id = p.vessel_id
        ORDER BY p.recorded_at DESC
        LIMIT 8
    """)
    live_positions = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM vessel")
    vessel_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM position")
    position_count = cur.fetchone()[0]

    cur.close()
    conn.close()
    return render_template("index.html",
        top_vessels=top_vessels,
        live_positions=live_positions,
        vessel_count=vessel_count,
        position_count=position_count
    )

# Search
@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("index"))

    search_type, clean_q = validate_search(q)

    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    if search_type == "mmsi":
        cur.execute("""
            SELECT v.id, v.mmsi, v.name, v.current_flag, v.imo_number,
                   ss.total_score, ss.risk_level
            FROM vessel v
            LEFT JOIN suspicion_score ss ON ss.vessel_id = v.id
            WHERE v.mmsi = %s
        """, (clean_q,))
    elif search_type == "imo":
        cur.execute("""
            SELECT v.id, v.mmsi, v.name, v.current_flag, v.imo_number,
                   ss.total_score, ss.risk_level
            FROM vessel v
            LEFT JOIN suspicion_score ss ON ss.vessel_id = v.id
            WHERE v.imo_number ILIKE %s
        """, (clean_q,))
    else:
        cur.execute("""
            SELECT v.id, v.mmsi, v.name, v.current_flag, v.imo_number,
                   ss.total_score, ss.risk_level
            FROM vessel v
            LEFT JOIN suspicion_score ss ON ss.vessel_id = v.id
            WHERE v.name ILIKE %s
            ORDER BY ss.total_score DESC NULLS LAST
            LIMIT 50
        """, (f"%{clean_q}%",))

    results = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("search.html", results=results, query=q,
                           search_type=search_type, count=len(results))

# Vessel details
@app.route("/vessel/<int:vessel_id>")
def vessel(vessel_id):
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT v.*, ss.total_score, ss.risk_level,
               vt.name AS type_name
        FROM vessel v
        LEFT JOIN suspicion_score ss ON ss.vessel_id = v.id
        LEFT JOIN vessel_type vt ON vt.id = v.vessel_type_id
        WHERE v.id = %s
    """, (vessel_id,))
    v = cur.fetchone()
    if not v:
        cur.close(); conn.close()
        return "Vessel not found", 404

    cur.execute("""
        SELECT latitude, longitude, speed_knots, heading, recorded_at
        FROM position
        WHERE vessel_id = %s
        ORDER BY recorded_at DESC
        LIMIT 20
    """, (vessel_id,))
    positions = cur.fetchall()

    cur.execute("""
        SELECT gap_start, gap_end, gap_hours, last_lat, last_lon,
               reappear_lat, reappear_lon
        FROM ais_gap
        WHERE vessel_id = %s
        ORDER BY gap_start DESC
        LIMIT 10
    """, (vessel_id,))
    gaps = cur.fetchall()

    cur.execute("""
        SELECT flag_from, flag_to, changed_at
        FROM flag_change
        WHERE vessel_id = %s
        ORDER BY changed_at DESC
    """, (vessel_id,))
    flag_changes = cur.fetchall()

    cur.execute("""
        SELECT se.entity_name, se.list_source, se.reason, se.listed_since
        FROM sanction_entry se
        JOIN vessel_sanction vs ON vs.sanction_entry_id = se.id
        WHERE vs.vessel_id = %s
    """, (vessel_id,))
    sanctions = cur.fetchall()

    cur.execute("""
        SELECT rule_name, weight, description, detected_at
        FROM suspicion_event
        WHERE vessel_id = %s
        ORDER BY detected_at DESC
    """, (vessel_id,))
    events = cur.fetchall()

    is_favorite = False
    if "username" in session:
        cur.execute("""
            SELECT 1 FROM favorites
            WHERE username = %s AND vessel_id = %s
        """, (session["username"], vessel_id))
        is_favorite = cur.fetchone() is not None

    cur.close()
    conn.close()

    return render_template("vessel.html",
        v=v, positions=positions, gaps=gaps,
        flag_changes=flag_changes, sanctions=sanctions,
        events=events, is_favorite=is_favorite
    )

# Favorites
@app.route("/favorite/add/<int:vessel_id>", methods=["POST"])
def add_favorite(vessel_id):
    if "username" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO favorites (username, vessel_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (session["username"], vessel_id))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for("vessel", vessel_id=vessel_id))

@app.route("/favorite/remove/<int:vessel_id>", methods=["POST"])
def remove_favorite(vessel_id):
    if "username" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        DELETE FROM favorites
        WHERE username = %s AND vessel_id = %s
    """, (session["username"], vessel_id))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for("vessel", vessel_id=vessel_id))

# Profile
@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT v.id, v.name, v.mmsi, v.current_flag,
               ss.total_score, ss.risk_level, f.saved_at
        FROM favorites f
        JOIN vessel v ON v.id = f.vessel_id
        LEFT JOIN suspicion_score ss ON ss.vessel_id = v.id
        WHERE f.username = %s
        ORDER BY f.saved_at DESC
    """, (session["username"],))
    favorites = cur.fetchall()
    cur.close(); conn.close()
    return render_template("profile.html", favorites=favorites)

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and bcrypt.check_password_hash(user["password"], password):
            session["username"] = username
            return redirect(url_for("profile"))
        flash("Incorrect username or password")
    return render_template("login.html")

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields")
            return render_template("register.html")

        pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        conn = get_db()
        cur  = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (username, password)
                VALUES (%s, %s)
            """, (username, pw_hash))
            conn.commit()
            session["username"] = username
            return redirect(url_for("profile"))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash("Username already taken")
        finally:
            cur.close(); conn.close()

    return render_template("register.html")

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Update password
@app.route("/profile/update", methods=["POST"])
def update_password():
    if "username" not in session:
        return redirect(url_for("login"))
    new_password = request.form.get("new_password", "")
    if not new_password:
        flash("Please enter a new password")
        return redirect(url_for("profile"))
    pw_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE users SET password = %s WHERE username = %s
    """, (pw_hash, session["username"]))
    conn.commit()
    cur.close(); conn.close()
    flash("Password updated!")
    return redirect(url_for("profile"))

if __name__ == "__main__":
    app.run(debug=True)