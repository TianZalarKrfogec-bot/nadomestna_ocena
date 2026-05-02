import os
import uuid
import requests
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func # Dodaj to na vrh med importe, če še nimaš

# --- API KONFIGURACIJA ---
TMDB_API_KEY = "d110c7ceb10af4d2f369309f3a96eda9"

def search_movies(query):
    """Iskanje filmov preko TMDB API."""
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=sl-SI"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('results', [])[:10] # Vrnemo top 10
    except Exception as e:
        print(f"Napaka pri TMDB: {e}")
    return []

def search_books(query):
    """Iskanje knjig preko Open Library (brez ključa)."""
    # Open Library nima slovenščine tako dobro podprte, zato iščemo globalno
    url = f"https://openlibrary.org/search.json?q={query.replace(' ', '+')}"
    headers = {'User-Agent': 'FictionChat/1.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            results = response.json().get('docs', [])
            # Malo očistimo podatke, da dobimo le tiste s slikami in naslovi
            return results[:10]
    except Exception as e:
        print(f"Napaka pri Open Library: {e}")
    return []

def search_anime(query):
    url = f"https://api.jikan.moe/v4/anime?q={query}&limit=10"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('data', [])
    except Exception as e:
        print(f"Napaka pri Anime API: {e}")
    return []

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

class MBTIVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    char_id = db.Column(db.String(50), nullable=False)
    mbti_type = db.Column(db.String(4), nullable=False) # npr. 'INTJ'

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

# --- ISKANJE IN INTERAKCIJA ---

@app.route("/search", methods=["GET"])
def search():
    if "user_id" not in session: return redirect(url_for("login"))
    query = request.args.get("query")
    if not query: return redirect(url_for("dashboard"))
    
    movies = search_movies(query)
    books = search_books(query)
    animes = search_anime(query) # Novo
    
    return render_template("dashboard.html", movies=movies, books=books, animes=animes, query=query, username=session["username"])

@app.route("/view/<media_type>/<media_id>")
def view_media(media_type, media_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Pridobivanje podrobnosti glede na tip
    media_data = {}
    if media_type == "movie":
        url = f"https://api.themoviedb.org/3/movie/{media_id}?api_key={TMDB_API_KEY}&language=sl-SI"
        res = requests.get(url).json()
        media_data = {
            'id': media_id,
            'title': res.get('title'),
            'description': res.get('overview'),
            'image': f"https://image.tmdb.org/t/p/w500{res.get('poster_path')}" if res.get('poster_path') else None,
            'type': 'movie'
        }

    elif media_type == "anime":
        url = f"https://api.jikan.moe/v4/anime/{media_id}"
        res = requests.get(url).json().get('data', {})
        media_data = {
            'id': media_id,
            'title': res.get('title'),
            'description': res.get('synopsis'),
            'image': res.get('images', {}).get('jpg', {}).get('large_image_url'),
            'type': 'anime'
        }

    else: # book
        url = f"https://openlibrary.org/works/{media_id}.json"
        res = requests.get(url).json()
        media_data = {
            'id': media_id,
            'title': res.get('title'),
            'description': res.get('description').get('value') if isinstance(res.get('description'), dict) else res.get('description'),
            'image': f"https://covers.openlibrary.org/b/id/{res.get('covers')[0]}-L.jpg" if res.get('covers') else None,
            'type': 'book'
        }

    # NOVO: Izračun povprečne ocene iz baze
    avg_result = db.session.query(func.avg(Rating.score)).filter(Rating.media_id == media_id).scalar()
    display_avg = round(avg_result, 1) if avg_result else "Ni ocen"

    all_ratings = db.session.query(Rating, User).join(User, Rating.user_id == User.id).filter(Rating.media_id == media_id).order_by(Rating.timestamp.desc()).all()
    is_fav = Favorite.query.filter_by(user_id=session["user_id"], media_id=media_id).first()

    return render_template("view_media.html", 
                           item=media_data, 
                           ratings=all_ratings, 
                           is_fav=is_fav, 
                           avg_rating=display_avg)

@app.route("/rate", methods=["POST"])
def rate():
    if "user_id" not in session: return redirect(url_for("login"))
    
    media_id = request.form.get("media_id")
    media_type = request.form.get("media_type")
    score = request.form.get("score")
    comment = request.form.get("comment")
    
    new_rating = Rating(
        user_id=session["user_id"],
        media_id=media_id,
        media_type=media_type,
        score=int(score) if score else 0,
        comment=comment
    )
    db.session.add(new_rating)
    db.session.commit()
    return redirect(url_for("view_media", media_type=media_type, media_id=media_id))

@app.route("/favorite/<media_type>/<media_id>")
def toggle_favorite(media_type, media_id):
    if "user_id" not in session: return redirect(url_for("login"))
    
    fav = Favorite.query.filter_by(user_id=session["user_id"], media_id=media_id).first()
    if fav:
        db.session.delete(fav)
    else:
        # Za poenostavitev naslov in sliko pošljemo preko query parametrov ali ponovno kličemo API
        title = request.args.get("title")
        poster = request.args.get("poster")
        new_fav = Favorite(user_id=session["user_id"], media_id=media_id, media_title=title, poster_path=poster)
        db.session.add(new_fav)
    
    db.session.commit()
    return redirect(request.referrer)

@app.route("/profile")
def profile():
    if "user_id" not in session: return redirect(url_for("login"))
    user_favs = Favorite.query.filter_by(user_id=session["user_id"]).all()
    user_ratings = Rating.query.filter_by(user_id=session["user_id"]).all()
    return render_template("profile.html", favorites=user_favs, ratings=user_ratings)

@app.route("/user/<username>")
def public_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    user_favs = Favorite.query.filter_by(user_id=user.id).all()
    user_ratings = Rating.query.filter_by(user_id=user.id).all()
    return render_template("public_profile.html", profile_user=user, favorites=user_favs, ratings=user_ratings)

# Iskanje likov (Jikan API)
def search_characters(query):
    url = f"https://api.jikan.moe/v4/characters?q={query}&limit=12"
    try:
        res = requests.get(url)
        return res.json().get('data', [])
    except: return []

@app.route("/characters", methods=["GET"])
def characters_dashboard():
    query = request.args.get("query")
    chars = []
    if query:
        # Kličemo pomožno funkcijo, ki jo že imaš
        chars = search_characters(query) 
    
    # Prepričaj se, da tukaj piše chars=chars (množina)
    return render_template("characters.html", chars=chars, query=query)

@app.route("/view/character/<char_id>")
def view_character(char_id):
    # Pridobivanje podatkov o liku
    res = requests.get(f"https://api.jikan.moe/v4/characters/{char_id}").json().get('data', {})
    char_data = {
        'id': char_id,
        'name': res.get('name'),
        'description': res.get('about'),
        'image': res.get('images', {}).get('jpg', {}).get('image_url'),
        'type': 'character'
    }
    
    # MBTI logika - preštejemo glasove
    votes = db.session.query(MBTIVote.mbti_type, func.count(MBTIVote.mbti_type)).filter_by(char_id=char_id).group_by(MBTIVote.mbti_type).all()
    # Komentarji in priljubljeni (isto kot pri filmih)
    all_ratings = db.session.query(Rating, User).join(User, Rating.user_id == User.id).filter(Rating.media_id == char_id).order_by(Rating.timestamp.desc()).all()
    is_fav = Favorite.query.filter_by(user_id=session["user_id"], media_id=char_id).first()
    
    return render_template("view_character.html", char=char_data, votes=votes, ratings=all_ratings, is_fav=is_fav)

@app.route("/vote_mbti", methods=["POST"])
def vote_mbti():
    char_id = request.form.get("char_id")
    mbti = request.form.get("mbti_type")
    # Preverimo, če je uporabnik že glasoval za tega lika (da ne spama)
    existing = MBTIVote.query.filter_by(user_id=session["user_id"], char_id=char_id).first()
    if existing:
        existing.mbti_type = mbti
    else:
        new_vote = MBTIVote(user_id=session["user_id"], char_id=char_id, mbti_type=mbti)
        db.session.add(new_vote)
    db.session.commit()
    return redirect(url_for('view_character', char_id=char_id))

if __name__ == "__main__":
    app.run(debug=True, port=5001)