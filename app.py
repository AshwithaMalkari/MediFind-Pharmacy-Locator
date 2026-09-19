import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- Basic Flask setup ---
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "dev-secret-change-me"
app.permanent_session_lifetime = timedelta(days=7)

# --- Database config (SQLite) ---
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medifind.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password:str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password:str) -> bool:
        return check_password_hash(self.password_hash, password)

class Pharmacy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250))
    latitude = db.Column(db.Float)   # optional
    longitude = db.Column(db.Float)  # optional
    phone = db.Column(db.String(30))

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)           # e.g., "Dolo 650"
    generic_name = db.Column(db.String(150), nullable=False)   # e.g., "Paracetamol"
    strength = db.Column(db.String(50))                        # e.g., "650 mg"
    form = db.Column(db.String(50))                            # e.g., "Tablet"

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock_qty = db.Column(db.Integer, default=0)

    pharmacy = db.relationship(Pharmacy, backref="inventories")
    medicine = db.relationship(Medicine, backref="inventories")

# --- Utilities ---
def login_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper

# --- Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","").strip()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["user_name"] = user.name or email
            session.permanent = True
            flash("Welcome back!", "success")
            return redirect(url_for("home"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    return render_template("home.html", user_name=session.get("user_name"))

@app.route("/search")
@login_required
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        like = f"%{q.lower()}%"
        medicines = Medicine.query.filter(
            db.or_(db.func.lower(Medicine.name).like(like),
                   db.func.lower(Medicine.generic_name).like(like))
        ).all()

        for med in medicines:
            invs = Inventory.query.filter_by(medicine_id=med.id).all()
            if invs:
                min_price = min(i.price for i in invs)
                store_count = len({i.pharmacy_id for i in invs})
            else:
                min_price = None
                store_count = 0
            results.append({
                "medicine": med,
                "min_price": min_price,
                "store_count": store_count
            })

    return render_template("results.html", q=q, results=results)

@app.route("/medicine/<int:med_id>")
@login_required
def medicine_detail(med_id):
    med = Medicine.query.get_or_404(med_id)
    invs = (
        db.session.query(Inventory, Pharmacy)
        .join(Pharmacy, Inventory.pharmacy_id == Pharmacy.id)
        .filter(Inventory.medicine_id == med_id)
        .order_by(Inventory.price.asc())
        .all()
    )

    # If not available, suggest alternatives with same generic_name
    alternatives = []
    if not invs:
        alternatives = Medicine.query.filter(
            db.and_(Medicine.generic_name == med.generic_name,
                    Medicine.id != med.id)
        ).all()

    return render_template("medicine_detail.html", med=med, invs=invs, alternatives=alternatives)

@app.route("/image-search", methods=["POST"])
@login_required
def image_search():
    file = request.files.get("photo")
    if not file or file.filename == "":
        flash("Please select an image first.", "warning")
        return redirect(url_for("home"))

    # Save upload
    save_dir = os.path.join(app.static_folder, "uploads")
    os.makedirs(save_dir, exist_ok=True)
    fp = os.path.join(save_dir, file.filename)
    file.save(fp)

    # Try OCR (best effort, optional dependency)
    extracted = ""
    try:
        import pytesseract
        from PIL import Image

        # Try to auto-locate tesseract on Windows default path
        if os.name == "nt":
            possible = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(possible):
                pytesseract.pytesseract.tesseract_cmd = possible

        img = Image.open(fp)
        text = pytesseract.image_to_string(img)
        extracted = (text or "").strip().splitlines()[0] if text else ""
    except Exception as e:
        extracted = ""

    if extracted:
        flash(f"Image text detected: {extracted}", "info")
        return redirect(url_for("search", q=extracted))
    else:
        flash("Could not read text from image. Try a clearer photo or type the name.", "warning")
        return redirect(url_for("home"))

# Convenience route to serve uploaded files (for dev only)
@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(os.path.join(app.static_folder, "uploads"), filename)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
