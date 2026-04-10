from flask import Flask, render_template, request, redirect, url_for, session, flash
from tinydb import TinyDB, Query
from werkzeug.security import generate_password_hash, check_password_hash
from threading import Lock

app = Flask(__name__)
app.secret_key = "skrivni_kljuc_za_2_nalogo"

# Baza in zaklepanje
db = TinyDB('db2.json')
users = db.table('users')
User = Query()
db_lock = Lock()

# ==========================================
# OSNOVNE POTI (Greet & Dashboard)
# ==========================================

@app.route("/")
def greet():
    return render_template("greet.html")


# ==========================================
# AVTENTIKACIJA (Login & Register)
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        question = request.form.get("question")
        answer = request.form.get("answer")

        with db_lock:
            if users.get(User.username == username):
                flash("Uporabniško ime že obstaja!")
                return redirect(url_for("/register"))
            
            users.insert({
                "username": username,
                "password": generate_password_hash(password),
                "question": question,
                "answer": answer.lower(),
                "admin": 0  # Privzeto navaden uporabnik
            })
        return redirect(url_for("/login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users.get(User.username == username)
        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["admin"] = user.get("admin", 0)
            return redirect(url_for("/dashboard"))
        
        flash("Napačno uporabniško ime ali geslo!")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("/greet"))

# ==========================================
# POZABLJENO GESLO
# ==========================================

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        user = users.get(User.username == username)
        if user:
            return render_template("reset_question.html", user=user)
        flash("Uporabnik ne obstaja.")
    return render_template("forgot_password.html")

@app.route("/reset_password", methods=["POST"])
def reset_password():
    username = request.form.get("username")
    answer = request.form.get("answer").lower()
    new_password = request.form.get("new_password")

    with db_lock:
        user = users.get(User.username == username)
        if user and user.get("answer") == answer:
            users.update({"password": generate_password_hash(new_password)}, User.username == username)
            flash("Geslo uspešno spremenjeno!")
            return redirect("/login")
        
    flash("Napačen odgovor na varnostno vprašanje.")
    return redirect("/forgot_password")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("/login"))
    return render_template("dashboard.html", uporabnik=session["user"])

if __name__ == "__main__":
    app.run(debug=True)