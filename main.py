from flask import Flask, render_template, request, session, redirect, url_for, flash
import calendar
import sqlite3
from datetime import datetime
from config import Config

people = ["Alice", "Bob", "Charlie", "David", "Eva", "Frank"]

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------
# SQLite DATABASE
# ---------------------------------------------------------

def db_connect():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Dict-like rows
    return conn

# Create SQL table (workers) for workers
def create_workers_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            exceptions TEXT,
            shifts INTEGER NOT NULL,
            places TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
create_workers_table()
    
# Create SQL table (users) for users to login
def create_users_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Add default user
    cur.execute("""
        INSERT OR IGNORE INTO users (username, password)
        VALUES (?, ?)
    """, ("test", "1"))

    conn.commit()
    cur.close()
    conn.close()
create_users_table()

# ---------------------------------------------------------
# DATABASE ACTIONS
# ---------------------------------------------------------

# Add worker in SQL(workers)
def add_worker(user, name, role, exceptions, shifts, places):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO workers (username, name, role, exceptions, shifts, places)
        VALUES (?, ?, ?, ?, ?, ?)""", 
        (user, name, role, exceptions, shifts, places))
    conn.commit()
    cur.close()
    conn.close()

# Get all workers from SQL(workers)
def get_workers(user):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, name, role, exceptions, shifts, places
        FROM workers
        WHERE username = ?
        ORDER BY name""", 
        (user,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# Delete worker by name in SQL workers table for current user 
def delete_worker(username, name):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM workers 
        WHERE username = ? AND name = ?''', 
        (username, name))
    conn.commit()
    cur.close()
    conn.close()

def update_worker(username, name, role, exceptions, shifts, places):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        UPDATE workers
        SET role = ?, exceptions = ?, shifts = ?, places = ?
        WHERE username = ? AND name = ?
    ''', (role, exceptions, shifts, places, username, name))
    conn.commit()
    cur.close()
    conn.close()

# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"].strip()

        conn = db_connect()
        cur = conn.cursor()
        cur.execute('''SELECT password 
                        FROM users 
                        WHERE username = ?''', 
                    (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row and row[0] == password:
            session["user"] = username
            return redirect(url_for("account"))
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html") 

@app.route("/account", methods=["GET"])
def account():
    if "user" not in session:
        return redirect(url_for("login"))

    # Load workers for template
    rows = get_workers(session["user"])
    workers = [dict(row) for row in rows]

    return render_template("account.html",
                           username=session["user"],
                           workers=workers)

@app.route("/account/add", methods=["POST"])
def account_add():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401

    data = request.get_json()

    name = data.get("name")
    role = data.get("role")
    exceptions = data.get("exceptions", [])
    shifts = data.get("shifts")
    places = data.get("places", [])

    add_worker(
        session["user"],
        name,
        role,
        ", ".join(exceptions),
        shifts,
        ", ".join(places))

    return {"success": True}

@app.route('/account/update', methods=['POST'])
def update():
    if "user" not in session:
        return {"success": False, "error": "Unauthorized"}, 401

    data = request.get_json()
    name = data.get("name")
    role = data.get("role")
    exceptions = data.get("exceptions")
    shifts = data.get("shifts")
    places = data.get("places")

    print(data)

    # Update worker with same name for current user
    update_worker(session["user"], name, role, ', '.join(exceptions), shifts, ', '.join(places))

    return {"success": True}

@app.route('/account/delete', methods=['POST'])
def delete():
    if "user" not in session:
        return redirect(url_for('login'))
    
    data = request.get_json()
    name = data.get("name")
    if not name:
        return {"success": False, "error": "Missing name"}, 400

    delete_worker(session["user"], name)
    return {"success": True, "message": "Deleted successfully"}

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create():
    # Retrieve stored year and month (or None)
    year = session.get('year', None) 
    month = session.get('month', None)
    days_in_month = session.get('days_in_month', 0)  # Retrieve stored days (default 0)
    table_rows = session.get('table_rows', [])

    if 'generate_table' in request.form:
        # User enter year and month 
        year = int(request.form['year'])
        month = int(request.form['month'])
        days_in_month = calendar.monthrange(year, month)[1]

        # Generate fresh table data
        table_rows = [
            {'day': day, 'is_weekend': datetime(year, month, day).weekday() >= 5}
            for day in range(1, days_in_month + 1)
        ]

        # Store data in session
        session['year'] = year
        session['month'] = month
        session['days_in_month'] = days_in_month
        session['table_rows'] = table_rows

    elif 'save_names' in request.form:
        # User submitted names, update table_rows with new values
        table_rows = session.get('table_rows', [])  # Load table from session
        
        for row in table_rows:
            for name, text in request.form.items():
                if name.startswith('name_') and name.endswith(f'_{row['day']}'):
                    row[name] = text  # Save entered text into the correct row with key name_ZONE_day
        print(table_rows)
        # Store updated table in session
        session['table_rows'] = table_rows

    return render_template(
        'index.html',
        year=year,
        month=month,
        days_in_month=days_in_month,
        table_rows=table_rows,
    )

# API to get names of workers from SQL to use in JS
@app.route("/api/names")
def api_names():
    if "user" not in session:
        return {"error": "not authenticated"}, 401

    workers = [dict(row) for row in get_workers(session["user"])]
    names = [w["name"] for w in workers]
    return {"names": names}

# Completely resets page
@app.route('/reset', methods=['POST'])
def reset():
    session.clear()  # Clear all session data
    return redirect(url_for('index'))  #

# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
