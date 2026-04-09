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

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # 1. Poberemo samo nujne podatke
        username = request.form.get("username")
        password = request.form.get("password")

        # Preverimo, če sta polji prazni
        if not username or not password:
            return render_template("register.html", error="Vpišite ime in geslo!")

        # 2. Preverimo, če uporabnik že obstaja
        if users.search(User.username == username):
            return render_template("register.html", error="Uporabniško ime je že zasedeno.")

        # 3. Hashiramo geslo
        hashed_password = generate_password_hash(password)

        # 4. Shranimo v bazo (brez varnostnih vprašanj)
        with db_lock:
            users.insert({
                "username": username,
                "password": hashed_password,
                "admin": 0
            })

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # 1. Poberemo podatke iz obrazca (name="username" in name="password")
        username = request.form.get("username")
        password = request.form.get("password")

        # 2. Poiščemo uporabnika v TinyDB
        user = users.get(User.username == username)

        # 3. Preverimo: ali uporabnik sploh obstaja IN ali je geslo pravilno?
        if user and check_password_hash(user["password"], password):
            # Če je vse v redu, ga "vpišemo" v sejo (session)
            session["user"] = username
            session["admin"] = user.get("admin", 0)
            
            # Preusmerimo ga na glavno stran (dashboard)
            return redirect("/dashboard")
        
        # Če podatki niso pravilni, mu pokažemo napako
        return render_template("login.html", error="Napačno uporabniško ime ali geslo!")

    # Če je metoda GET, samo prikažemo stran za prijavo
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return "se delam na temu"


app.run(debug = True)