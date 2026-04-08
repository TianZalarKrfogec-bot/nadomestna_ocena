from flask import Flask, render_template, request, redirect, session, url_for
from tinydb import TinyDB, Query
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import threading

app = Flask(__name__)
app.secret_key = "zeloskrivenkljuc"

db = TinyDB("db.json")
all_data = db.all()
users = db.table("users")

db_lock = threading.Lock()

User = Query()

@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/greet")

@app.route("/greet")
def greet():
    return render_template("greet.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return "se delam na temu"


app.run(debug = True)