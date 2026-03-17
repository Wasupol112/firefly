from flask import Flask, render_template, request, redirect
from flask import send_from_directory
from flask import session
from firefly_model import count_fireflies_still, count_fireflies_pan 
import os
import re
import shutil
import psycopg2

# ================= DATABASE =================

def connect_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def init_db():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        fullname TEXT,
        email TEXT UNIQUE
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

def register_user(username, password, fullname, email):
    conn = connect_db()
    cur = conn.cursor()

    # เช็ค username ซ้ำ
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return "username"

    # เช็ค email ซ้ำ
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return "email"

    # insert
    cur.execute(
        "INSERT INTO users (username, password, fullname, email) VALUES (%s, %s, %s, %s)",
        (username, password, fullname, email)
    )

    conn.commit()
    cur.close()
    conn.close()

    return "success"

def login_user(username, password):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (username, password)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return user is not None

# ============================================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
ALLOWED_EXTENSIONS = {"mp4","avi","mov","mkv"}
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
app.secret_key = "firefly_secret"

# 🔥 สร้าง table อัตโนมัติ
init_db()

# หน้า home
@app.route("/")
def home():
    return render_template("index.html")

# หน้า register
@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        fullname = request.form["fullname"]
        email = request.form["email"]

        # password length
        if len(password) < 8:
            return render_template("signup.html", error="Password must be at least 8 characters")

        # email format
        email_pattern = r"[^@]+@[^@]+\.[^@]+"
        if not re.match(email_pattern, email):
            return render_template("signup.html", error="Invalid email format")

        result = register_user(username, password, fullname, email)

        if result == "username":
            return render_template("signup.html", error="Username already exists")

        if result == "email":
            return render_template("signup.html", error="Email already registered")

        return redirect("/login")

    return render_template("signup.html")

# หน้า login
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if login_user(username, password):
            session["user"] = username
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Wrong username or password")

    return render_template("login.html")

# หน้า dashboard
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/upload", methods=["GET","POST"])
def upload():
    if "user" not in session:
        return redirect("/login")
        
    if request.method == "POST":
        video = request.files["video"]
        model_type = request.form.get("model_type") 

        if video and allowed_file(video.filename):
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], video.filename)
            video.save(input_path)
            
            if model_type == "pan":
                result = count_fireflies_pan(input_path)
                if isinstance(result, tuple):
                    firefly_count = result[0]
                    output_path = result[1]
                else:
                    firefly_count = result
                    output_path = input_path
            else:
                result = count_fireflies_still(input_path)
                if isinstance(result, tuple):
                    firefly_count = result[0]
                    output_path = result[1]
                else:
                    firefly_count = result
                    output_path = input_path

            filename = os.path.basename(output_path)
            processed_path = os.path.join(app.config["PROCESSED_FOLDER"], filename)
            shutil.copy(output_path, processed_path)

            return render_template(
                "result.html",
                video=filename,
                count=firefly_count,
                model_used=model_type
            )

        else:
            return render_template("upload.html", error="Only video files allowed")
            
    return render_template("upload.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route('/processed/<filename>')
def processed_video(filename):
    return send_from_directory("processed", filename)

@app.route("/activity")
def activity():
    return render_template("activity.html")

@app.route("/learning")
def learning():
    return render_template("learning.html")

@app.route("/map")
def map():
    return render_template("map.html")

@app.route("/schedule")
def schedule():
    return render_template("schedule.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
