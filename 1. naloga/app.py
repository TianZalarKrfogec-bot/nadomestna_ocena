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

def setup_system_accounts():
    with db_lock:
        # 1. Preveri/Ustvari GLAVNEGA ADMINA (nivo 2)
        if not users.get(User.username == "admin"):
            users.insert({
                "username": "admin",
                "password": generate_password_hash("admin123"), # Geslo: admin123
                "admin": 2,
                "note": {},
                "security_question": "Sistem",
                "security_answer": "Sistem"
            })
            print("Ustvarjen privzeti račun: admin / admin123")

        # 2. Preveri/Ustvari MODERATORJA (nivo 1)
        if not users.get(User.username == "moderator"):
            users.insert({
                "username": "moderator",
                "password": generate_password_hash("mod123"), # Geslo: mod123
                "admin": 1,
                "note": {},
                "security_question": "Sistem",
                "security_answer": "Sistem"
            })
            print("Ustvarjen privzeti račun: moderator / mod123")

# Pokličemo funkcijo takoj po definiciji baze
setup_system_accounts()

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
        # DODATEK: Če se je obstoječ uporabnik ravnokar prijavil in nima vprašanj
        if session.get("need_security"):
            question = request.form["security_question"]
            answer = request.form["security_answer"].lower()
            
            with db_lock:
                users.update(
                    {"security_question": question, "security_answer": generate_password_hash(answer)}, 
                    User.username == session["user"]
                )
            session.pop("need_security", None)
            return redirect("/dashboard")

        # STANDARDNA REGISTRACIJA: Za nove uporabnike
        username = request.form["username"] # shranimo spremenljivke iz registracije
        password = request.form["password"]

        # Preverimo, če uporabnik že obstaja
        if users.search(User.username == username):
            return render_template("register.html", error="Uporabniško ime že obstaja")

        # Vpis novega uporabnika v bazo (vključno z varnostnimi vprašanji)
        users.insert({
            "username": username, 
            "password": generate_password_hash(password), 
            "admin": 0, 
            "note": {}, 
            "security_question": request.form["security_question"], 
            "security_answer": generate_password_hash(request.form["security_answer"].lower())
        })
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # 1. Poberemo podatke iz obrazca
        username = request.form["username"]
        password = request.form["password"]

        # 2. Poiščemo uporabnika v bazi (TinyDB)
        user = users.get(User.username == username)

        # 3. Preverimo obstoj in geslo
        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["admin"] = user.get("admin", 0)

            # --- DODATEK ZA VARNOSTNA VPRAŠANJA ---
            # Če uporabnik v bazi nima polja security_question, 
            # ga preusmerimo na /register, da ga nastavi.
            if not user.get("security_question"):
                session["need_security"] = True
                return redirect(url_for("register"))
            # --------------------------------------

            return redirect(url_for("home")) # ali "dashboard"
        
        # Če podatki niso pravilni
        return render_template("login.html", error="Napačno uporabniško ime ali geslo")

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        user = users.get(User.username == username)

        # Če uporabnik vpiše odgovor in novo geslo
        if "security_answer" in request.form:
            answer = request.form.get("security_answer").lower()
            new_password = request.form.get("new_password")
            
            # Preverimo hashiran odgovor v bazi
            if user and check_password_hash(user["security_answer"], answer):
                with db_lock:
                    users.update(
                        {"password": generate_password_hash(new_password)},
                        User.username == username
                    )
                return render_template("login.html", error="Geslo uspešno spremenjeno. Zdaj se lahko prijaviš.")
            else:
                return render_template("forgot_password.html", user=user, error="Napačen odgovor!")

        # Če uporabnik samo vpiše ime, da dobi vprašanje
        if user:
            return render_template("forgot_password.html", user=user)
        else:
            return render_template("forgot_password.html", error="Uporabnik ne obstaja.")

    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    # Pobrišemo vse podatke iz seje
    session.clear()
    return redirect("/greet")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    
    # Pridobimo podatke uporabnika
    user = users.get(User.username == session["user"])
    notes = user.get("note", {}) # Varno pridobivanje zapiskov
    
    return render_template(
        "dashboard.html", 
        uporabnik=session["user"], 
        notes=notes, 
        admin=session.get("admin", 0) # Pošljemo admin status v HTML
    )

# ==========================================
# USTVARJANJE IN UREJANJE
# ==========================================

@app.route("/newNote")
def newNote():
    if "user" not in session:
        return redirect("/login")

    id = str(uuid.uuid4()) # Ustvarimo unikaten ID
    with db_lock:
        user = users.get(User.username == session["user"])
        notes = user.get("note", {})
        notes[id] = {"title": "", "content": ""} # Inicializacija praznega zapiska
        users.update({"note": notes}, User.username == session["user"])
        
    return redirect(url_for('editNote', id=id))

@app.route("/dashboard/<id>")
def editNote(id):
    if "user" not in session:
        return redirect("/login")
    
    # Preverimo, če admin gleda tuj zapisek
    target_user = request.args.get("user")
    if target_user and session.get("admin", 0) in (1, 2):
        user = users.get(User.username == target_user)
    else:
        user = users.get(User.username == session["user"])
        target_user = None
    
    if not user:
        return "Uporabnik ne obstaja", 404
    
    note = user.get("note", {}).get(id, {"title": "", "content": ""})
    return render_template("edit_note.html", id=id, note=note, uporabnik=session["user"], target_user=target_user)

# ==========================================
# SHRANJEVANJE IN BRISANJE
# ==========================================

@app.route("/saveNote", methods=["POST"])
def saveNote():
    title = request.form["title"]
    content = request.form["content"]
    id = request.form["id"]
    target_user = request.form.get("user", "")

    with db_lock:
        # Logika za admina ali navadnega uporabnika
        if target_user and session.get("admin", 0) in (1, 2):
            user = users.get(User.username == target_user)
            if user:
                user["note"][id] = {"title": title, "content": content}
                users.update({"note": user["note"]}, User.username == target_user)
        else:
            user = users.get(User.username == session["user"])
            if user:
                notes = user.get("note", {})
                notes[id] = {"title": title, "content": content}
                users.update({"note": notes}, User.username == session["user"])
    return "OK"

@app.route("/deleteNote", methods=["POST"])
def deleteNote():
    id = request.form["id"]
    target_user = request.form.get("user", "")

    with db_lock:
        # Admin lahko briše tuj zapisek
        if target_user and session.get("admin", 0) in (1, 2):
            user = users.get(User.username == target_user)
            if user and id in user["note"]:
                del user["note"][id]
                users.update({"note": user["note"]}, User.username == target_user)
        else:
            user = users.get(User.username == session["user"])
            if user:
                notes = user.get("note", {})
                if id in notes:
                    del notes[id]
                users.update({"note": notes}, User.username == session["user"])
    return "OK"

# 1. Glavna Admin stran - Seznam vseh uporabnikov
@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect("/login")
    
    # Preverimo status iz seje (ki se napolni ob prijavi)
    current_admin_level = session.get("admin", 0)
    
    if current_admin_level not in (1, 2):
        return "Nimate dostopa!", 403
        
    all_users = users.all()
    return render_template("admin.html", users=all_users, uporabnik=session["user"])
# 2. Podroben pogled zapiskov določenega uporabnika
@app.route("/admin/user/<username>")
def admin_user_notes(username):
    # Varnostna preverjanja
    if "user" not in session:
        return redirect("/login")
    if session.get("admin", 0) not in (1, 2):
        return redirect("/dashboard")
    
    # Poiščemo tarčnega uporabnika v bazi
    user = users.get(User.username == username)
    if not user:
        return "Uporabnik ne obstaja", 404
    
    # Pridobimo zapiske in nivo admina
    notes = user.get("note", {})
    return render_template(
        "admin_notes.html", 
        uporabnik=session["user"], 
        target_user=username, 
        notes=notes, 
        admin=session.get("admin", 0),
        target_admin=user.get("admin", 0) # Za select menu
    )

# 3. AJAX funkcija za posodobitev vloge (Navaden/Moderator/Admin)
@app.route("/admin/updateRole", methods=["POST"])
def update_user_role():
    # Preverimo, če ima tisti, ki pošilja, sploh pravico to delati
    if session.get("admin", 0) != 2: # Samo glavni admin (2) lahko menja vloge
        return "Nimate pooblastil", 403

    username = request.form["username"]
    new_role = int(request.form["role"]) #
    
    with db_lock:
        user = users.get(User.username == username)
        if user:
            users.update({"admin": new_role}, User.username == username)
            return "OK"
            
    return "Uporabnik ni najden", 404

app.run(debug = True)