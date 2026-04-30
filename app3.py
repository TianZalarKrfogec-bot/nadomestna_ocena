import os
import uuid
import requests
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Osnovna konfiguracija v skladu z tvojo sliko ogrodja
app = Flask(__name__, 
            template_folder='templates3', 
            static_folder='static3')

app.secret_key = "skrivnost_naloge_tri_mbti"

# POPRAVEK POTI: Pridobimo pot do trenutne mape in določimo ime datoteke baze
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELI (Vse v isti datoteki za lažje iskanje) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    security_question = db.Column(db.String(100), nullable=False) # Dodano
    security_answer = db.Column(db.String(200), nullable=False)   # Dodano
    ratings = db.relationship('Rating', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.String(100), nullable=False)
    media_type = db.Column(db.String(20)) # 'movie', 'series', 'book'
    score = db.Column(db.Integer)
    comment = db.Column(db.Text)
    character_name = db.Column(db.String(100))
    mbti_vote = db.Column(db.String(4))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.String(100), nullable=False)
    media_title = db.Column(db.String(200))
    poster_path = db.Column(db.String(300))

# Ustvarimo bazo in tabele ob zagonu
with app.app_context():
    db.create_all()

# --- POTI (ROUTES) ---

# --- AVTENTIKACIJA IN OSNOVNE STRANI ---

@app.route("/")
def home():
    # Če je uporabnik prijavljen, naj gre na dashboard, sicer na pozdravno stran
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("greet"))

@app.route("/greet")
def greet():
    # Osnovna vstopna stran za neprijavljene
    return render_template("greet.html")

# --- POSODOBLJENA REGISTRACIJA ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        security_question = request.form.get("security_question")
        security_answer = request.form.get("security_answer").lower()
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="Uporabniško ime že obstaja!")
            
        hashed_pw = generate_password_hash(password)
        hashed_ans = generate_password_hash(security_answer)
        
        new_user = User(username=username, password=hashed_pw, 
                        security_question=security_question, security_answer=hashed_ans)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for("login"))
        
    return render_template("register.html")

# --- NOVA POT ZA POZABLJENO GESLO ---
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")
        user = User.query.filter_by(username=username).first()

        # Faza 2: Preverjanje odgovora in nastavljanje novega gesla
        if "security_answer" in request.form:
            answer = request.form.get("security_answer").lower()
            new_password = request.form.get("new_password")
            
            if user and check_password_hash(user.security_answer, answer):
                user.password = generate_password_hash(new_password)
                db.session.commit()
                return render_template("login.html", error="Geslo uspešno spremenjeno! Lahko se prijaviš.", error_color="success")
            else:
                return render_template("forgot_password.html", user=user, error="Napačen odgovor!")

        # Faza 1: Iskanje uporabnika in prikaz vprašanja
        if user:
            return render_template("forgot_password.html", user=user)
        else:
            return render_template("forgot_password.html", error="Uporabnik ne obstaja.")

    return render_template("forgot_password.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # SQL iskanje uporabnika
        user = User.query.filter_by(username=username).first()
        
        # Preverjanje gesla
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("dashboard"))
            
        return render_template("login.html", error="Napačno uporabniško ime ali geslo!")
        
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("greet"))

# --- GLAVNI DEL APLIKACIJE ---

@app.route("/dashboard")
def dashboard():
    # Zaščita strani - če ni seje, pojdi na login
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    return render_template("dashboard.html", username=session["username"])

if __name__ == "__main__":
    app.run(debug=True, port=5001)