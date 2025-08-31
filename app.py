from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    # Sales data table
    cursor.execute('''CREATE TABLE IF NOT EXISTS data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customerName TEXT NOT NULL,
                        phoneNumber TEXT NOT NULL,
                        productName TEXT NOT NULL,
                        quantity INTEGER,
                        amount REAL NOT NULL,
                        cashGiven REAL,
                        afterGiven REAL,
                        due REAL,
                        dateCreated TEXT,
                        dateUpdated TEXT)''')
    # Password table
    cursor.execute('''CREATE TABLE IF NOT EXISTS password (
                        id INTEGER PRIMARY KEY,
                        passcode TEXT NOT NULL)''')
    conn.commit()
    conn.close()

init_db()

# ---------- Password Setup ----------
@app.route("/set_password", methods=["GET", "POST"])
def set_password():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM password")
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if len(password) < 4 or len(password) > 8 or not password.isdigit():
            flash("❌ Password must be 4-8 digits only.", "danger")
        else:
            cursor.execute("INSERT INTO password (id, passcode) VALUES (1, ?)", (password,))
            conn.commit()
            conn.close()
            flash("✅ Password set successfully! Please login.", "success")
            return redirect(url_for("login"))

    conn.close()
    return render_template("set_password.html")

# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT passcode FROM password LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:  # No password set
        return redirect(url_for("set_password"))

    if request.method == "POST":
        entered = request.form.get("password", "").strip()
        if entered == row[0]:
            session["logged_in"] = True
            return redirect(url_for("home"))
        else:
            flash("❌ Incorrect password.", "danger")

    return render_template("login.html")

# ---------- Logout ----------
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    flash("🔒 Logged out.", "info")
    return redirect(url_for("login"))

# ---------- Dashboard ----------
@app.route("/", methods=["GET", "POST"])
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    error = None
    query = request.args.get("q", "").lower()
    data = []
    total_due = 0.0

    if request.method == "POST":
        customerName = request.form.get("customerName", "").strip()
        phoneNumber = request.form.get("phoneNumber", "").strip()
        productName = request.form.get("productName", "").strip()
        quantity = int(request.form.get("quantity", 0))
        amount = request.form.get("amount", 0)
        cashGiven = request.form.get("cashGiven", 0)
        afterGiven = request.form.get("afterGiven", 0)

        if not customerName or not phoneNumber or not productName or not amount:
            error = "❌ Please fill all required fields."
        else:
            amount = float(amount)
            cashGiven = float(cashGiven) if cashGiven else 0
            afterGiven = float(afterGiven) if afterGiven else 0
            totalPaid = cashGiven + afterGiven
            due = 0 if totalPaid >= amount else amount - totalPaid
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = sqlite3.connect("data.db")
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO data 
                              (customerName, phoneNumber, productName, quantity, amount, cashGiven, afterGiven, due, dateCreated, dateUpdated) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (customerName, phoneNumber, productName, quantity, amount, cashGiven, afterGiven, due, now, now))
            conn.commit()
            conn.close()
            flash("✅ Record Saved Successfully!", "success")
            return redirect(url_for("home", q=customerName))

    if query:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM data 
                          WHERE LOWER(customerName) LIKE ? OR phoneNumber LIKE ? 
                          ORDER BY id DESC""",
                       ('%' + query + '%', '%' + query + '%'))
        data = cursor.fetchall()
        cursor.execute("""SELECT SUM(due) FROM data 
                          WHERE LOWER(customerName) LIKE ? OR phoneNumber LIKE ?""",
                       ('%' + query + '%', '%' + query + '%'))
        result = cursor.fetchone()
        total_due = result[0] if result and result[0] else 0.0
        conn.close()

    return render_template("index.html", data=data, error=error, query=query, total_due=total_due)

# ---------- Update Route ----------
@app.route("/update/<int:sale_id>", methods=["POST"])
def update_sale(sale_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    afterGiven = float(request.form.get("afterGiven", 0))
    amount = float(request.form.get("amount", 0))

    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT cashGiven FROM data WHERE id=?", (sale_id,))
    row = cursor.fetchone()
    cashGiven = row[0] if row else 0

    totalPaid = cashGiven + afterGiven
    due = 0 if totalPaid >= amount else amount - totalPaid
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""UPDATE data SET 
                        afterGiven=?, due=?, dateUpdated=? 
                      WHERE id=?""",
                   (afterGiven, due, now, sale_id))
    conn.commit()
    conn.close()

    flash("✅ Record Updated Successfully!", "success")
    return redirect(url_for("home"))

# ---------- Autofill API ----------
@app.route("/api/autofill")
def autofill():
    if not session.get("logged_in"):
        return jsonify({})
    name = request.args.get("name", "").strip().lower()
    phone = request.args.get("phone", "").strip()
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()

    if name:
        cursor.execute("SELECT phoneNumber FROM data WHERE LOWER(customerName)=? LIMIT 1", (name,))
        row = cursor.fetchone()
        conn.close()
        return jsonify({"phone": row[0] if row else ""})

    if phone:
        cursor.execute("SELECT customerName FROM data WHERE phoneNumber=? LIMIT 1", (phone,))
        row = cursor.fetchone()
        conn.close()
        return jsonify({"name": row[0] if row else ""})

    conn.close()
    return jsonify({})

if __name__ == "__main__":
    app.run(debug=True)
