from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from tinydb import TinyDB, Query
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import uuid
import os
import datetime

app = Flask(__name__)
app.secret_key = "zeloskrivenkljuc_six"

app.config['UPLOAD_FOLDER'] = 'uploads2'

from flask import send_from_directory
@app.route('/uploads2/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 2. ŠELE NATO lahko preverjaš, če mapa obstaja
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Funkcija za preverjanje dovoljenih končnic (dodaj, če nimaš)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/greet")

# Helper funkcija za pridobivanje vseh uporabnikov
def get_all_users():
    return users.all()

# 1. DASHBOARD - Prikaz vseh zapiskov vseh uporabnikov
import datetime

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    all_users = get_all_users()
    posts = []
    
    for user in all_users:
        uname = user.get("username", "Neznanec")
        for note_id, note in user.get("note", {}).items():
            posts.append({
                "username": uname,
                "id": note_id,
                "content": note.get("content", ""),
                "images": note.get("images", []),
                "like": note.get("like", 0),
                "dislike": note.get("dislike", 0),
                "comment": note.get("comment", []),
                "like_users": note.get("like_users", []),
                "dislike_users": note.get("dislike_users", []),
                # Če objava nima timestampa, ji damo zelo star datum
                "timestamp": note.get("timestamp", "1970-01-01T00:00:00")
            })
    
    # REŠITEV: Uporabimo sorted() s parametrom reverse=True
    # To bo zagotovilo, da bodo največji nizi (novejši datumi) na začetku seznama
    sorted_posts = sorted(posts, key=lambda x: x['timestamp'], reverse=True)
    return render_template("dashboard.html", uporabnik=session["user"], posts=sorted_posts)
# 2. LIKE - Všečkanje zapiska (AJAX)
@app.route("/like", methods=["POST"])
def like():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    note_id = request.form.get("id")
    username = session["user"]
    
    with db_lock:
        all_users = users.all()
        for user in all_users:
            if note_id in user.get("note", {}):
                note = user["note"][note_id]
                like_users = note.get("like_users", [])
                dislike_users = note.get("dislike_users", [])
                
                if username in like_users:
                    like_users.remove(username)
                else:
                    like_users.append(username)
                    if username in dislike_users:
                        dislike_users.remove(username)
                
                note["like"] = len(like_users)
                note["dislike"] = len(dislike_users)
                note["like_users"] = like_users
                note["dislike_users"] = dislike_users
                
                users.update({"note": user["note"]}, User.username == user["username"])
                return jsonify({
                    "like": note["like"], 
                    "dislike": note["dislike"], 
                    "likeActive": username in like_users, 
                    "dislikeActive": username in dislike_users
                })
    return "Napaka", 404

# 3. DISLIKE - Nevšečkanje zapiska (AJAX)
@app.route("/dislike", methods=["POST"])
def dislike():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    note_id = request.form.get("id")
    username = session["user"]
    
    with db_lock:
        all_users = users.all()
        for user in all_users:
            if note_id in user.get("note", {}):
                note = user["note"][note_id]
                like_users = note.get("like_users", [])
                dislike_users = note.get("dislike_users", [])
                
                if username in dislike_users:
                    dislike_users.remove(username)
                else:
                    dislike_users.append(username)
                    if username in like_users:
                        like_users.remove(username)
                
                note["like"] = len(like_users)
                note["dislike"] = len(dislike_users)
                note["like_users"] = like_users
                note["dislike_users"] = dislike_users
                
                users.update({"note": user["note"]}, User.username == user["username"])
                return jsonify({
                    "like": note["like"], 
                    "dislike": note["dislike"], 
                    "likeActive": username in like_users, 
                    "dislikeActive": username in dislike_users
                })
    return "Napaka", 404

# 4. COMMENTS - Pregled in dodajanje komentarjev
@app.route("/comments/<id>", methods=["GET", "POST"])
def comments(id):
    if "user" not in session:
        return redirect(url_for("login"))
        
    if request.method == "POST":
        action = request.form.get("action")
        index = int(request.form.get("index", -1))
        
        with db_lock:
            all_users = users.all()
            for user in all_users:
                if id in user.get("note", {}):
                    note = user["note"][id]
                    comment_list = note.get("comment", [])
                    
                    if action == "delete" and 0 <= index < len(comment_list):
                        # Preverimo, če je uporabnik lastnik komentarja pred brisanjem
                        if comment_list[index]["username"] == session["user"]:
                            comment_list.pop(index)
                    else:
                        content = request.form.get("content", "").strip()
                        if content:
                            comment_list.append({"username": session["user"], "content": content})
                    
                    note["comment"] = comment_list
                    users.update({"note": user["note"]}, User.username == user["username"])
                    return "OK"
            return "Zapiska ni mogoče najti", 404

    # GET del: Prikaz komentarjev
    note_owner = None
    comments_list = []
    for user in users.all():
        if id in user.get("note", {}):
            comments_list = user["note"][id].get("comment", [])
            break
            
    return render_template("comments.html", id=id, uporabnik=session["user"], comments=comments_list)

# 5. PROFILE - Prikaz zapiskov samo prijavljenega uporabnika
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    # 1. Pridobimo uporabnika iz baze
    user = users.get(User.username == session["user"])
    if not user:
        return "Uporabnik ni najden", 404

    # 2. Pripravimo seznam objav
    user_notes = []
    # Dobimo slovar zapiskov (če ga ni, vrnemo {})
    all_notes = user.get("note", {})

    for note_id, note in all_notes.items():
        user_notes.append({
            "id": note_id,
            "username": user["username"],
            "content": note.get("content", ""),
            "images": note.get("images", []),
            "timestamp": note.get("timestamp", "2000-01-01T00:00:00"), # Default čas, če ga ni
            "like": note.get("like", 0),
            "dislike": note.get("dislike", 0),
            "comment": note.get("comment", [])
        })

    # 3. ALGORITEM: Razvrstimo po času (novejši zgoraj)
    # x['timestamp'] bo primerjal nize tipa "2024-03-20T12:00:00"
    user_notes.sort(key=lambda x: x['timestamp'], reverse=True)

    # 4. Pošljemo v profile.html
    return render_template("profile.html", uporabnik=session["user"], notes=user_notes)
# Pomožna funkcija za preverjanje dovoljenih končnic slik
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 1. EDIT NOTE - Priprava podatkov za urejanje
@app.route("/edit/<id>")
def edit_note(id):
    if "user" not in session:
        return redirect(url_for("login"))

    # Iskanje zapiska samo za trenutno prijavljenega uporabnika
    user = users.get(User.username == session["user"])
    
    if not user:
        return "Uporabnik ne obstaja", 404

    # Pridobimo zapisek (če ne obstaja, vrnemo prazen niz)
    note = user.get("note", {}).get(id)
    if not note:
        return "Zapisek ne obstaja", 404

    return render_template("editNote.html", id=id, note=note, uporabnik=session["user"])

# 2. CREATE NEW NOTE - Ustvarjanje novega unikatnega zapisa
@app.route("/newNote")
def new_note():
    if "user" not in session:
        return redirect(url_for("login"))

    # Generiramo unikaten ID za nov zapisek
    note_id = str(uuid.uuid4())
    
    with db_lock:
        user = users.get(User.username == session["user"])
        notes = user.get("note", {})
        
        # Osnovna struktura novega zapiska
        notes[note_id] = {
            "content": "", 
            "images": [], 
            "like": 0, 
            "dislike": 0, 
            "comment": [],
            "like_users": [],
            "dislike_users": []
        }
        
        users.update({"note": notes}, User.username == session["user"])
    
    # Preusmerimo na stran za urejanje tega novega zapiska
    return redirect(url_for('edit_note', id=note_id))

# 3. SAVE NOTE - Shranjevanje besedila in slik (AJAX)

@app.route("/saveNote", methods=["POST"])
def save_note():
    if "user" not in session:
        return "Unauthorized", 401

    content = request.form.get("content", "")
    note_id = request.form.get("id", "")

    with db_lock:
        user = users.get(User.username == session["user"])
        if not user:
            return "Uporabnik ni najden", 404
            
        notes = user.get("note", {})

        # 1. Če ni ID-ja, ustvari novo objavo s časovnim žigom
        if not note_id or note_id == "":
            note_id = str(uuid.uuid4())
            notes[note_id] = {
                "id": note_id,
                "username": session["user"],
                "content": content,
                "images": [],
                "timestamp": datetime.datetime.now().isoformat(),
                "like": 0,
                "dislike": 0, 
                "comment": [],
                "like_users": [], 
                "dislike_users": []
            }

        # 2. Posodobi vsebino in shrani slike
        if note_id in notes:
            notes[note_id]["content"] = content
            
            # Shranjevanje slik v mapo uploads2
            if 'images' in request.files:
                uploaded_files = request.files.getlist("images")
                current_imgs = notes[note_id].get("images", [])
                
                for file in uploaded_files:
                    if file and file.filename != "" and allowed_file(file.filename):
                        if len(current_imgs) < 3: # Omejitev na 3 slike
                            ext = file.filename.rsplit(".", 1)[1].lower()
                            fn = f"{uuid.uuid4().hex}.{ext}"
                            
                            # Shranimo v uploads2
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                            current_imgs.append(fn)
                
                notes[note_id]["images"] = current_imgs

            # 3. Shranimo posodobljene zapiske nazaj k uporabniku
            users.update({"note": notes}, User.username == session["user"])
            return "OK", 200

    return "Napaka", 400
@app.route("/deleteNote", methods=["POST"])
def delete_note():
    if "user" not in session:
        return "Unauthorized", 401
    
    note_id = request.form.get("id")
    
    with db_lock:
        user = users.get(User.username == session["user"])
        if user:
            notes = user.get("note", {})
            if note_id in notes:
                # Najprej fizično izbrišemo slike iz mape
                for img in notes[note_id].get("images", []):
                    img_path = os.path.join(app.config['UPLOAD_FOLDER'], img)
                    if os.path.exists(img_path):
                        os.remove(img_path)
                
                # Odstranimo iz baze
                del notes[note_id]
                users.update({"note": notes}, User.username == session["user"])
                return "OK", 200
                
    return "Ni mogoče izbrisati", 400

@app.route("/removeImage", methods=["POST"])
def remove_image():
    if "user" not in session:
        return "Unauthorized", 401

    note_id = request.form.get("id")
    filename = request.form.get("filename")

    with db_lock:
        # Pridobimo trenutnega uporabnika
        user = users.get(User.username == session["user"])
        
        if user and note_id in user.get("note", {}):
            note = user["note"][note_id]
            images = note.get("images", [])
            
            if filename in images:
                # 1. Odstranimo ime datoteke iz seznama v bazi
                images.remove(filename)
                
                # 2. Fizično izbrišemo datoteko iz diska
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
                
                # Posodobimo bazo
                user["note"][note_id]["images"] = images
                users.update({"note": user["note"]}, User.username == session["user"])
                
                return "OK"

    return "Slika ne obstaja", 404

if __name__ == "__main__":
    app.run(debug=True)