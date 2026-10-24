import os, sqlite3, uuid
from datetime import datetime
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, send_from_directory, render_template_string, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "uploads")
DB_PATH = os.path.join(BASE_DIR, "storage", "campus_resources.db")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "jpg", "jpeg", "png", "zip"}
MAX_CONTENT_LENGTH = 15 * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect_db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','staff','admin'))
        );
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            stored_name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(uploaded_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
        """)
        # Demo accounts are created only when the database is first initialized.
        if not con.execute("SELECT id FROM users LIMIT 1").fetchone():
            con.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                        ("student", generate_password_hash("student123"), "student"))
            con.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                        ("staff", generate_password_hash("staff123"), "staff"))
            con.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                        ("admin", generate_password_hash("admin123"), "admin"))

def log_action(action, details=""):
    with connect_db() as con:
        con.execute("INSERT INTO audit_logs(username,action,details,created_at) VALUES(?,?,?,?)",
                    (session.get("username", "anonymous"), action, details,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def staff_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") not in ("staff", "admin"):
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

STYLE = """
<style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f3f6fb;color:#1d2b45}
header{background:#142746;color:white;padding:18px 5%;display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}
header a{color:white;text-decoration:none;margin-left:14px}.wrap{max-width:1050px;margin:28px auto;padding:0 18px}
.card{background:white;border-radius:12px;padding:22px;margin-bottom:18px;box-shadow:0 3px 14px #10284a12}
h1,h2{margin-top:0}.muted{color:#65738b}.btn{background:#087f8c;color:white;border:0;border-radius:7px;padding:10px 14px;text-decoration:none;cursor:pointer;display:inline-block}
input,select,textarea{width:100%;padding:10px;border:1px solid #ccd5e2;border-radius:7px;margin:6px 0 14px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px;border-bottom:1px solid #e4e9f0}th{background:#edf3f8}
.notice{padding:10px;background:#e2f6f3;border-radius:7px;margin-bottom:10px}.danger{background:#ffeded}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.stat{font-size:26px;font-weight:bold;color:#087f8c}
</style>
"""
NAV = """<header><strong>Campus Resource Sharing</strong><nav>
<a href="{{ url_for('dashboard') }}">Dashboard</a>
<a href="{{ url_for('upload') }}">Upload</a>
<a href="{{ url_for('logout') }}">Logout</a>
</nav></header>"""

LOGIN = STYLE + """
<div class="wrap"><div class="card" style="max-width:470px;margin:55px auto">
<h1>Campus Resource Sharing</h1><p class="muted">Sign in to access shared college resources.</p>
{% for msg in get_flashed_messages() %}<div class="notice">{{msg}}</div>{% endfor %}
<form method="post"><label>Username</label><input name="username" required>
<label>Password</label><input type="password" name="password" required>
<button class="btn">Login</button></form>
<hr><p class="muted">Demo accounts: student / student123; staff / staff123; admin / admin123</p>
</div></div>
"""

DASHBOARD = STYLE + NAV + """
<div class="wrap">
{% for msg in get_flashed_messages() %}<div class="notice">{{msg}}</div>{% endfor %}
<h1>Resource Dashboard</h1><p class="muted">Signed in as {{username}} ({{role}})</p>
<div class="grid">
<div class="card"><div class="muted">Available resources</div><div class="stat">{{count}}</div></div>
<div class="card"><div class="muted">Your role</div><div class="stat" style="font-size:20px">{{role|title}}</div></div>
<div class="card"><div class="muted">Service status</div><div class="stat" style="font-size:20px">Online</div></div>
</div>
<div class="card"><h2>Search resources</h2>
<form method="get"><input name="q" value="{{q}}" placeholder="Search by title, category or description">
<button class="btn">Search</button> <a class="btn" href="{{url_for('dashboard')}}">Clear</a></form>
<table><tr><th>Title</th><th>Category</th><th>Uploaded by</th><th>Date</th><th>Action</th></tr>
{% for r in resources %}<tr><td>{{r['title']}}<br><span class="muted">{{r['description'] or ''}}</span></td>
<td>{{r['category']}}</td><td>{{r['username']}}</td><td>{{r['created_at']}}</td>
<td><a class="btn" href="{{url_for('download_resource', resource_id=r['id'])}}">Download</a>
{% if role == 'admin' %}<a href="{{url_for('delete_resource',resource_id=r['id'])}}" onclick="return confirm('Delete this resource?')">Delete</a>{% endif %}</td></tr>
{% else %}<tr><td colspan="5">No resources found. Upload the first resource.</td></tr>{% endfor %}
</table></div>
{% if role in ['staff','admin'] %}<div class="card"><h2>Staff tools</h2><p>Staff and administrators can upload resources. Administrators can also delete resources.</p><a class="btn" href="{{url_for('upload')}}">Upload a resource</a></div>{% endif %}
</div>
"""

UPLOAD = STYLE + NAV + """
<div class="wrap"><div class="card"><h1>Upload a resource</h1>
{% for msg in get_flashed_messages() %}<div class="notice">{{msg}}</div>{% endfor %}
{% if role not in ['staff','admin'] %}<div class="notice danger">Only staff and admins can upload. Student accounts can search and download.</div>
{% else %}
<form method="post" enctype="multipart/form-data">
<label>Resource title</label><input name="title" required maxlength="120">
<label>Category</label><select name="category" required><option>Study Material</option><option>Project Document</option><option>Lab Manual</option><option>Notice</option><option>Other</option></select>
<label>Description</label><textarea name="description" rows="3" maxlength="500"></textarea>
<label>Choose file (max 15 MB)</label><input type="file" name="file" required>
<button class="btn">Upload resource</button></form>
{% endif %}</div></div>
"""

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with connect_db() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], username=user["username"], role=user["role"])
            log_action("login", "Successful login")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template_string(LOGIN)

@app.route("/logout")
def logout():
    if "user_id" in session:
        log_action("logout", "User logged out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    q = request.args.get("q", "").strip()
    with connect_db() as con:
        count = con.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        if q:
            like = f"%{q}%"
            resources = con.execute("""
                SELECT r.*,u.username FROM resources r JOIN users u ON u.id=r.uploaded_by
                WHERE r.title LIKE ? OR r.category LIKE ? OR r.description LIKE ?
                ORDER BY r.id DESC""", (like, like, like)).fetchall()
        else:
            resources = con.execute("""
                SELECT r.*,u.username FROM resources r JOIN users u ON u.id=r.uploaded_by
                ORDER BY r.id DESC""").fetchall()
    return render_template_string(DASHBOARD, resources=resources, count=count, q=q,
                                  username=session["username"], role=session["role"])

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if session.get("role") not in ("staff", "admin"):
            abort(403)
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        file = request.files.get("file")
        if not title or not category or not file or not file.filename:
            flash("Please complete all required fields.")
            return redirect(url_for("upload"))
        if not allowed_file(file.filename):
            flash("File type not allowed.")
            return redirect(url_for("upload"))
        original = secure_filename(file.filename)
        stored = f"{uuid.uuid4().hex}_{original}"
        path = os.path.join(UPLOAD_DIR, stored)
        file.save(path)
        with connect_db() as con:
            con.execute("""INSERT INTO resources(title,category,description,stored_name,original_name,uploaded_by,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (title, category, description, stored, original, session["user_id"],
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        log_action("upload", title)
        flash("Resource uploaded successfully.")
        return redirect(url_for("dashboard"))
    return render_template_string(UPLOAD, role=session["role"])

@app.route("/download/<int:resource_id>")
@login_required
def download_resource(resource_id):
    with connect_db() as con:
        resource = con.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    if not resource:
        abort(404)
    path = os.path.join(UPLOAD_DIR, resource["stored_name"])
    if not os.path.isfile(path):
        log_action("download_failed", f"Missing file for resource {resource_id}")
        flash("This file is currently unavailable.")
        return redirect(url_for("dashboard"))
    log_action("download", resource["title"])
    return send_from_directory(UPLOAD_DIR, resource["stored_name"],
                               as_attachment=True, download_name=resource["original_name"])

@app.route("/delete/<int:resource_id>")
@login_required
@staff_required
def delete_resource(resource_id):
    if session.get("role") != "admin":
        abort(403)
    with connect_db() as con:
        resource = con.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
        if resource:
            con.execute("DELETE FROM resources WHERE id=?", (resource_id,))
    if resource:
        path = os.path.join(UPLOAD_DIR, resource["stored_name"])
        if os.path.isfile(path):
            os.remove(path)
        log_action("delete", resource["title"])
        flash("Resource deleted.")
    return redirect(url_for("dashboard"))

@app.route("/health")
def health():
    try:
        with connect_db() as con:
            con.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "connected"}, 200
    except sqlite3.Error:
        return {"status": "error", "database": "unavailable"}, 503

@app.errorhandler(403)
def forbidden(_):
    return render_template_string(STYLE + '<div class="wrap card"><h1>403 - Access denied</h1><p>You do not have permission for this operation.</p><a href="/">Return to dashboard</a></div>'), 403

@app.errorhandler(404)
def not_found(_):
    return render_template_string(STYLE + '<div class="wrap card"><h1>404 - Not found</h1><p>The requested resource was not found.</p><a href="/">Return to dashboard</a></div>'), 404

@app.errorhandler(413)
def too_large(_):
    return render_template_string(STYLE + '<div class="wrap card"><h1>File too large</h1><p>Maximum upload size is 15 MB.</p><a href="/upload">Try again</a></div>'), 413

init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
