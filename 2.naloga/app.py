from flask import Flask, render_template, request, redirect, session, url_for
from tinydb import TinyDB, Query
from werkzeug.security import generate_password_hash, check_password_hash
import threading

app = Flask(__name__)
app.secret_key = "zeloskrivenkljuc_six"

# Uporabimo db2.json za 2. nalogo, da ne mešamo podatkov
db = TinyDB("db2.json")
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
        # Če uporabnik nastavlja varnostna vprašanja po prvi prijavi
        if session.get("need_security"):
            question = request.form.get("security_question")
            answer = request.form.get("security_answer", "").lower()
            
            with db_lock:
                users.update(
                    {"security_question": question, "security_answer": generate_password_hash(answer)}, 
                    User.username == session["user"]
                )
            session.pop("need_security", None)
            return redirect("/dashboard")

        # Standardna registracija
        username = request.form.get("username")
        password = request.form.get("password")
        question = request.form.get("security_question")
        answer = request.form.get("security_answer", "").lower()

        if users.search(User.username == username):
            return render_template("register.html", error="Uporabniško ime že obstaja")

        with db_lock:
            users.insert({
                "username": username, 
                "password": generate_password_hash(password), 
                "note": {}, # Ohranimo prazne zapiske za 2. nalogo
                "security_question": question, 
                "security_answer": generate_password_hash(answer)
            })
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users.get(User.username == username)

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            # Admin statusa več ne shranjujemo

            if not user.get("security_question"):
                session["need_security"] = True
                return redirect(url_for("register"))

            return redirect("/dashboard")
        
        return render_template("login.html", error="Napačno uporabniško ime ali geslo")

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        user = users.get(User.username == username)

        # 1. FAZA: Preverjanje odgovora in nastavljanje novega gesla
        if "security_answer" in request.form:
            answer = request.form.get("security_answer", "").lower()
            new_password = request.form.get("new_password")
            
            # Preverimo hashiran odgovor v bazi
            if user and check_password_hash(user["security_answer"], answer):
                with db_lock:
                    users.update(
                        {"password": generate_password_hash(new_password)},
                        User.username == username
                    )
                # Usmerimo na login s potrditvijo
                return render_template("login.html", error="Geslo uspešno spremenjeno. Zdaj se lahko prijaviš.")
            else:
                # Če je odgovor napačen, vrnemo uporabnika nazaj k vprašanju
                return render_template("forgot_password.html", user=user, error="Napačen odgovor na varnostno vprašanje!")

        # 2. FAZA: Iskanje uporabnika, da mu prikažemo vprašanje
        if user:
            return render_template("forgot_password.html", user=user)
        else:
            return render_template("forgot_password.html", error="Uporabnik s tem imenom ne obstaja.")

    # Osnovni prikaz strani (vnos uporabniškega imena)
    return render_template("forgot_password.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html", uporabnik=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/greet")

if __name__ == "__main__":
    app.run(debug=True)