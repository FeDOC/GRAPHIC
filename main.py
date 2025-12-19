from flask import Flask, render_template, request, session, redirect, url_for, flash
import calendar
import sqlite3
from datetime import datetime, date, timedelta
from config import Config
from collections import defaultdict

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------
# COMMON FUNCTIONS
# ---------------------------------------------------------
def load_date():
    now = datetime.now()
        # month: dict[key: tuple[int, str]] 
    months = { 
        'prev': ((now.month - 1) if (now.month - 1) > 0 else 12, calendar.month_name[(now.month - 1) if (now.month - 1) > 0 else 12]),
        'cur': (now.month, calendar.month_name[now.month]),
        'next': ((now.month + 1) if (now.month + 1) < 13 else 1, calendar.month_name[(now.month + 1) if (now.month + 1) < 13 else 1])
    }
        # years: dict[key: int]
    years = {
        'prev': now.year if now.month > 1 else now.year - 1,
        'cur': now.year,
        'next': now.year if now.month < 12 else now.year + 1,
    } 
    return months, years

# ---------------------------------------------------------
# SQLite DATABASE
# ---------------------------------------------------------

def db_connect():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Dict-like rows
    return conn

# Create SQL table (users) for users to login
def create_users_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )""")

    # Add default user
    cur.execute("""
        INSERT OR IGNORE INTO users (username, password)
        VALUES (?, ?)
    """, ("test", "1"))

    conn.commit()
    cur.close()
    conn.close()
create_users_table()

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
            vacation_start DATE,
            vacation_end DATE,
            shifts INTEGER NOT NULL,
            places TEXT NOT NULL
        )
    """)
    # cur.execute('''DROP TABLE workers''')
    conn.commit()
    cur.close()
    conn.close()
create_workers_table()
    
# Create SQL table (months) for exceptions and N of shifts for specified month
def create_months_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            month TEXT NOT NULL,
            exceptions TEXT,
            shifts INTEGER NOT NULL
            )''')
    conn.commit()
    cur.close()
    conn.close()
create_months_table()

# ---------------------------------------------------------
# DATABASE ACTIONS
# ---------------------------------------------------------

# Add worker in SQL(workers)
def add_worker(user, name, role, vacations, shifts, places):

    # Parse vacations string to start and end in date format 
    def parse_vacations(vacations): # ["date - date", ...] -> [(datetime.date, datetime.date), ...]:
        vacs = [list(map(lambda x: x.strip(), vac.split('-'))) for vac in vacations]
        res = []
        for vac in vacs:
            start, end = vac
            vac_start = datetime.strptime(start, "%d.%m.%y").date()
            vac_end = datetime.strptime(end, "%d.%m.%y").date()
            res.append((vac_start, vac_end))
        return res
    vacations = parse_vacations(vacations)

    # Define month bounds
    def month_bounds(year, month):
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end
    
    # Define vacations days for month  
    def vacation_intervals_in_month(vac_start, vac_end, month_start, month_end):
        if not vac_start:
            return None
        if vac_end < month_start or vac_start > month_end:
            return None
        start = max(vac_start, month_start)
        end = min(vac_end, month_end)
        days = [] 
        cur = start 
        while cur <= end: 
            days.append(f'{cur.day}') 
            cur += timedelta(days=1) 
        return ", ".join(days)


    # Add to SQL(workers, months)
    conn = db_connect()
    cur = conn.cursor()
    for vacation_start, vacation_end in vacations:
        # Add to workers
        cur.execute("""
            INSERT INTO workers (username, name, role, vacation_start, vacation_end, shifts, places)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", 
            (user, name, role, vacation_start, vacation_end, shifts, places))
        
        # Add to months
        months, years = load_date()
        for i in months:
            month, year = months[i][0], years[i]
            table_month = f'{year}-{month:02d}' ## YYYY-MM
            month_start, month_end = month_bounds(year, month)
            exceptions = vacation_intervals_in_month(
                vacation_start,
                vacation_end,
                month_start,
                month_end
            )
            cur.execute("""
                INSERT INTO months
                (username, name, month, exceptions, shifts)
                VALUES (?, ?, ?, ?, ?)""", 
                (user, name, table_month, exceptions, shifts))
    conn.commit()
    cur.close()
    conn.close()

# Get all workers from SQL(workers)
def get_workers(user): # {col_name: param}
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, name, role, vacation_start, vacation_end, shifts, places
        FROM workers
        WHERE username = ?
        ORDER BY name""", 
        (user,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows 

# Get workers with exceptions from SQL(months)
def get_month_workers(user, month): # {col_name: param}
    # Query from SQL 
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, exceptions, shifts
        FROM months
        WHERE username = ?
            AND month = ?
        ORDER BY name""", 
        (user, month))
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

# Update worker in worker tab
def update_worker(username, name, role, vacations, shifts, places):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        UPDATE workers
        SET role = ?, vacations = ?, shifts = ?, places = ?
        WHERE username = ? AND name = ?
    ''', (role, vacations, shifts, places, username, name))
    conn.commit()
    cur.close()
    conn.close()

# Update worker in month tab
def update_months(username, name, month, exceptions, shifts):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        UPDATE months
        SET exceptions = ?, shifts = ?
        WHERE username = ? AND name = ? and month = ?
    ''', (exceptions, shifts, username, name, month))
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
    else:
        user = session["user"]

    # Transform vacations to interval string 'dd.mm.yyyy(start) - dd.mm.yyyy(end), ...'
    def tranform_vacations(rows):
        workers = {} 
        vacations_dict = defaultdict(list)
        for row in rows:
            name = row['name']
            if name not in workers:
                workers[name] = {
                    "role": row["role"],
                    "shifts": row["shifts"],
                    "places": row["places"],
                    "vacations": ""
                }

            if row["vacation_start"] and row["vacation_end"]:
                start_str = datetime.strptime(row["vacation_start"], "%Y-%m-%d").date().strftime("%d.%m.%y")
                end_str = datetime.strptime(row["vacation_end"], "%Y-%m-%d").date().strftime("%d.%m.%y")
                vacations_dict[name].append(f"{start_str} - {end_str}")
        for name, vac_list in vacations_dict.items():
            workers[name]["vacations"] = ", ".join(vac_list)
        return workers
    
    # Load workers for template
    rows = get_workers(session["user"])
    workers = tranform_vacations(rows)

    # Load date for month tabs
    months, years = load_date()
    month_keys = [f'{years[i]}-{months[i][0]:02d}' for i in months]

    months_workers = {
        'prev': get_month_workers(user, month_keys[0]),
        'cur':get_month_workers(user, month_keys[1]),
        'next':get_month_workers(user, month_keys[2]),}

    return render_template("account.html",
                            username=session["user"],
                            months=months,
                            years = years,
                            workers=workers,
                            months_workers = months_workers)

@app.route("/account/workers/add", methods=["POST"])
def account_add():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401

    data = request.get_json()

    name = data.get("name")
    role = data.get("role")
    vacations = data.get("vacations", []) 
    shifts = data.get("shifts")
    places = data.get("places", [])

    add_worker(
        session["user"],
        name,
        role,
        vacations, # ["date - date", ...]
        shifts,
        ", ".join(places))

    return {"success": True}

@app.route('/account/workers/update', methods=['POST'])
def update_workers():
    if "user" not in session:
        return {"success": False, "error": "Unauthorized"}, 401

    data = request.get_json()
    name = data.get("name")
    role = data.get("role")
    vacations = data.get("vacations")
    shifts = data.get("shifts")
    places = data.get("places")

    # Update worker with same name for current user
    update_worker(session["user"], name, role, ', '.join(vacations), shifts, ', '.join(places))

    return {"success": True}

@app.route('/account/workers/delete', methods=['POST'])
def delete():
    if "user" not in session:
        return redirect(url_for('login'))
    
    data = request.get_json()
    name = data.get("name")
    if not name:
        return {"success": False, "error": "Missing name"}, 400

    delete_worker(session["user"], name)
    return {"success": True, "message": "Deleted successfully"}

# Update rows in month tab
# @app.route('/account/months/update', methods=['POST'])
# def update_month():
#     if "user" not in session:
#         return {"success": False, "error": "Unauthorized"}, 401

#     data = request.get_json()
#     name = data.get("name")
#     exceptions = data.get("exceptions")
#     shifts = data.get("shifts")

#     # Update worker exceptions and shifts number for current month, name=const)
#     update_months(session["user"], name, ', '.join(exceptions), shifts, month)

#     return {"success": True}

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
