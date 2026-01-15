from flask import Flask, render_template, request, session, redirect, url_for, flash
import calendar
import sqlite3
from datetime import datetime, date, timedelta
from config import Config
from collections import defaultdict

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

# Load years and months for prev, cur, next tabs
def load_date():
    now = datetime.now()
    # months: {prev: tuple[int, str], cur:, next:} 
    months = { 
        'prev': ((now.month - 1) if (now.month - 1) > 0 else 12, calendar.month_name[(now.month - 1) if (now.month - 1) > 0 else 12]),
        'cur': (now.month, calendar.month_name[now.month]),
        'next': ((now.month + 1) if (now.month + 1) < 13 else 1, calendar.month_name[(now.month + 1) if (now.month + 1) < 13 else 1])
    }
    # years: {prev: int, cur:, next:}
    years = {
        'prev': now.year if now.month > 1 else now.year - 1,
        'cur': now.year,
        'next': now.year if now.month < 12 else now.year + 1,
    } 
    return months, years

def month_days(years, months, current_month):
    days_in_month = calendar.monthrange(years[current_month], months[current_month][0])[1]
    days = [
        {'day': day, 'is_weekend': datetime(years[current_month], months[current_month][0], day).weekday() >= 5}
        for day in range(1, days_in_month + 1)]
    return {'days_in_month': days_in_month, 
            'days': days}

# Transform vacations to interval string 'dd.mm.yyyy(start) - dd.mm.yyyy(end), ...'
def tranform_vacations(rows):
    workers = {} #{name: {role: str, shifts: int, places: str, vacations: str}}
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

# Days of vacations for worker for month tab
def list_vacation_days(get_month_workers, user, years, months): 
    # month_bounds[func], get_month_workers[func], user[str], years[dict], months[dict] 
    # ->  {prev: {name: days[str]}, cur:, next:}  

    # Define month bounds
    def month_bounds(year, month):
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, end
    
    # Define vacations days for month  
    def vacation_intervals_in_month(vac_start, vac_end, month_start, month_end): # type(args) = date
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
    
    year_month = {}
    months_vacations = {}
    for i in months:
        year_month[i] = f'{years[i]}-{months[i][0]:02d}'
        raw = get_month_workers(user, year_month[i])
        month_start, month_end = month_bounds(years[i], months[i][0])
        months_vacations[i] = {}
        for line in raw:
            vac_start = date.fromisoformat(line['vacation_start'])
            vac_end = date.fromisoformat(line['vacation_end'])
            months_vacations[i] = {line['name']: vacation_intervals_in_month(vac_start, vac_end,
                                                            month_start, month_end)}
    return months_vacations

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
        if vacations == ['']:
            return [('', '')]
        vacs = [list(map(lambda x: x.strip(), vac.split('-'))) for vac in vacations]
        res = []
        for vac in vacs:
            start, end = vac
            vac_start = datetime.strptime(start, "%d.%m.%y").date()
            vac_end = datetime.strptime(end, "%d.%m.%y").date()
            res.append((vac_start, vac_end))
        return res
    
    vacations = parse_vacations(vacations)

    # Add to SQL(workers)
    conn = db_connect()
    cur = conn.cursor()
    for vacation_start, vacation_end in vacations:
        # Add to workers
        cur.execute("""
            INSERT INTO workers (username, name, role, vacation_start, vacation_end, shifts, places)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", 
            (user, name, role, vacation_start, vacation_end, shifts, places))
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

# Get worker's vacations and shifts for month from SQL(worker)
def get_month_workers(user, year_month): 
    # year_month[str] -> [{name: str, vacation_start: date, vacation_end: date, shifts: int}]

    # Query from SQL 
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, vacation_start, vacation_end, shifts
        FROM workers
        WHERE username = ?
            AND (strftime('%Y-%m', vacation_start) = ? 
                OR strftime('%Y-%m', vacation_end) = ?)
        ORDER BY name""", 
        (user, year_month, year_month))
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

@app.route("/account", methods=["GET", 'POST'])
def account():
    if "user" not in session:
        return redirect(url_for("login"))
    else:
        user = session["user"]
    
    # Load workers for template
    rows = get_workers(session["user"])
    workers = tranform_vacations(rows)

    # Load date for month tabs
    months, years = load_date()

    months_vacations = list_vacation_days(get_month_workers, user, years, months)
    
    month_shift_table = {
        'prev': month_days(years, months, 'prev'), # {days_in_month: int, days: [{day: int, weekend: bool}]]
        'cur': month_days(years, months, 'cur'),
        'next': month_days(years, months, 'next')}
    
    return render_template(
        "account.html",
        username=session["user"],
        months=months,
        years=years,
        workers=workers,
        months_vacations=months_vacations,
        month_shift_table=month_shift_table)

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
'''
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
'''

@app.route("/account/shifts/save", methods=["POST"])
def add_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    print(request.form)
    return {"success": True}
        # User submitted names, update table_rows with new values
        #cur_table_rows = session.get('cur_table_rows', [])  # Load table from session
        
        # for row in cur_table_rows:
        #     for name, text in request.form.items():
        #         if name.startswith('name_') and name.endswith(f'_{row['day']}'):
        #             row[name] = text  # Save entered text into the correct row with key name_ZONE_day
        # # Store updated table in session
        # session['table_rows'] = table_rows

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create():
    days_in_month = session.get('days_in_month', 0)
    table_rows = session.get('table_rows', [])

    if 'save_names' in request.form:
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
