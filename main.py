from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
import calendar, sqlite3, heapq, random, pandas as pd, io
import pandas as pd
from datetime import datetime, date, timedelta
from config import Config
from collections import defaultdict

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

# Load years and months for cur and next tabs
def load_date():
    now = datetime.now()
    # months: {cur: tuple[int, str], next:} 
    months = { 
        'cur': (now.month, calendar.month_name[now.month]),
        'next': ((now.month + 1) if (now.month + 1) < 13 else 1, calendar.month_name[(now.month + 1) if (now.month + 1) < 13 else 1])
    }
    # years: {cur: int, next:}
    years = {
        'cur': now.year,
        'next': now.year if now.month < 12 else now.year + 1,
    } 
    return months, years
loaded_date = load_date()

# Returns number of days in month and 
def month_days(years, months, needed_month): 
    # {days_in_month: int, days: {int(day): bool(weekend)}}
    days_in_month = calendar.monthrange(years[needed_month], months[needed_month][0])[1]
    days = {
        day: datetime(years[needed_month], months[needed_month][0], day).weekday() >= 5
        for day in range(1, days_in_month + 1)
    }
    return {'days_in_month': days_in_month, 
            'days': days}

# Transform vacations to interval string 'dd.mm.yyyy(start) - dd.mm.yyyy(end), ...'
def transform_vacations(rows):
    workers = {} #{name: {role: str, shifts: int, places: str, vacations: str}}
    for row in rows:
        name = row['name']
        workers[name] = {
            "role": row["role"],
            "shifts": row["shifts"],
            "places": ", ".join(row['places']),
            "vacations": ""
        }
        vacs = []
        for interv in row['vacations']:
            start_str = datetime.strptime(interv["vacation_start"], "%Y-%m-%d").date().strftime("%d.%m.%y")
            end_str = datetime.strptime(interv["vacation_end"], "%Y-%m-%d").date().strftime("%d.%m.%y")
            vacs.append(f"{start_str} - {end_str}")
        workers[name]['vacations'] = ", ".join(vacs)
    return workers

# Days of vacations for worker for month tab
def list_vacation_days(get_month_workers, user, years, months): 
    # get_month_workers[func], user[str], years[dict], months[dict] 
    # ->  {cur: {'name': days[str]}, next:}  

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
            days.append(cur.day) 
            cur += timedelta(days=1) 
        return days
    
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
            months_vacations[i].setdefault(line['name'], []).extend(vacation_intervals_in_month(vac_start, vac_end,
                                                            month_start, month_end))
    return months_vacations

# Highlite self added rest dates (next month workers table)
def highlite(months_vacations, workers, months_info, months):
    # -> {cur: {name: {exceptions: [list], shifts: int}}, next:...}
    result = {}
    for month in months:
        result[month] = {}
        for name, info in months_info[month].items():
            vacations = months_vacations[month].get(name, [])
            base_shifts = workers[name]['shifts']
            exceptions = info['exceptions']
            true_shifts = info['shifts']
            diff = [e for e in exceptions if e not in vacations]
            shifts = true_shifts if true_shifts != base_shifts else None
            result[month][name] = {'exceptions': diff, 
                                   'shifts': shifts}
    return result

# Parse vacations string to start and end in date format 
def parse_vacations(vacations): # ["date - date", ...] -> [(datetime.date, datetime.date), ...]:
    if not vacations or vacations == ['']:
        return []
    
    res = []
    for vac in vacations:
        try:
            start, end = map(str.strip, vac.split('-'))
            vac_start = datetime.strptime(start, "%d.%m.%y").date()
            vac_end = datetime.strptime(end, "%d.%m.%y").date()
            res.append((vac_start, vac_end))
        except:
            raise ValueError("Invalid date format")    
    return res

# Handle errors
@app.errorhandler(ValueError)
def _(e):
    return jsonify(ok=False, error=str(e)), 400

@app.errorhandler(sqlite3.IntegrityError)
def _(e):
    return jsonify(ok=False, error=str(e)), 409

# ---------------------------------------------------------
# SQLite DATABASE
# ---------------------------------------------------------

# Connect to DB
def db_connect():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
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
            shifts INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_worker
        ON workers (username, name)
    """)
    # cur.execute('''DROP TABLE workers''')
    conn.commit()
    cur.close()
    conn.close()
create_workers_table()

# Create SQL table (vacations) for workers' vacations
def create_vacations_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vacations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            vacation_start DATE NOT NULL,
            vacation_end DATE NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
        )
    """)
    # cur.execute('''DROP TABLE vacations''')
    conn.commit()
    cur.close()
    conn.close()
create_vacations_table()

# Create SQL table (places) for workers' places
def create_places_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            place TEXT NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
            UNIQUE (worker_id, place)
        )
    """)
    # cur.execute('''DROP TABLE places''')
    conn.commit()
    cur.close()
    conn.close()
create_places_table()

# Create SQL table (shifts) for specified month (cur, next) for days and zones
def create_shifts_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            filled TEXT NOT NULL,
            zone TEXT NOT NULL,
            day INTEGER NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
            UNIQUE (worker_id, month, filled, zone, day)
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_shift
        ON shifts (worker_id, month, day, zone)
    """)
    # cur.execute('''DROP TABLE shifts''')
    conn.commit()
    cur.close()
    conn.close()
create_shifts_table()

# Create SQL table (months) for cur and next months with exceptions and shifts
def create_months_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            exceptions TEXT NOT NULL,
            shifts INTEGER NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
            UNIQUE (worker_id)
        )
    """)
    #cur.execute('''DROP TABLE IF EXISTS months''')
    conn.commit()
    cur.close()
    conn.close()
create_months_table()

# ---------------------------------------------------------
# DATABASE ACTIONS
# ---------------------------------------------------------

# Check if login password is correct
def get_password(user):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''SELECT password 
                    FROM users 
                    WHERE username = ?''', 
                (user,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

# Add worker in SQL(workers)
def add_worker(user, name, role, vacations, shifts, places):
    
    vacations = parse_vacations(vacations)

    # Add to SQL(workers)
    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO workers (username, name, role, shifts)
            VALUES (?, ?, ?, ?)
        """, (user, name, role, shifts))
        worker_id = cur.lastrowid
        cur.executemany(
            "INSERT OR IGNORE INTO places (worker_id, place) VALUES (?, ?)",
            [(worker_id, place) for place in places.split(', ')]
        )

        if vacations:
            cur.executemany("""
                INSERT INTO vacations (worker_id, vacation_start, vacation_end)
                VALUES (?, ?, ?)
                """, 
                [(worker_id, v_start, v_end) for v_start, v_end in vacations]) 
        conn.commit()

    except ValueError:
        raise ValueError("Invalid date format")
    except sqlite3.IntegrityError:
        conn.rollback()
        raise 
    finally:
        cur.close()
        conn.close()

# Get all workers from SQL(workers)
def get_workers(user): # [{col_name: param}]
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, role, shifts
        FROM workers
        WHERE username = ?
    """, (user,))
    workers = cur.fetchall()
    rows = []  
    for worker in workers:
        worker_id, name, role, shifts = worker

        cur.execute("""
            SELECT place
            FROM places
            WHERE worker_id = ?
            """, (worker_id,))
        places = [row[0] for row in cur.fetchall()]

        cur.execute("""
            SELECT vacation_start, vacation_end
            FROM vacations
            WHERE worker_id = ?
            ORDER BY vacation_start
        """, (worker_id,))
        vacations = cur.fetchall()

        rows.append({
            'worker_id': worker_id,
            "name": name,
            "role": role,
            "shifts": shifts,
            "places": places,
            "vacations": vacations
        })    
    cur.close()
    conn.close()
    return rows 

# Get worker's vacations and shifts for month from SQL(worker)
def get_month_workers(user, year_month): 
    # year_month[str] -> [{name: str, vacation_start: date, vacation_end: date, shifts: int}]
    year, month = map(int, year_month.split('-'))
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, calendar.monthrange(year, month)[1]).date()
    # Query from SQL 
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, vacation_start, vacation_end, shifts
        FROM workers w
            LEFT JOIN vacations ON w.id = worker_id
        WHERE w.username = ?
            AND (vacation_start BETWEEN ? AND ? 
                OR vacation_end BETWEEN ? AND ?)
        ORDER BY name""", 
        (user, start_date, end_date, start_date, end_date))
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
    vacations = parse_vacations(vacations)

    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE workers 
                SET role = ?, shifts = ?
            WHERE username = ? AND name = ?
        """, (role, shifts, username, name))
        
        cur.execute("""
            SELECT id FROM workers
            WHERE username = ? AND name = ?
        """, (username, name))
        
        row = cur.fetchone()
        worker_id = row[0]

        cur.execute("""
            DELETE FROM places
            WHERE worker_id = ?
        """, (worker_id,) )

        cur.executemany(""" 
            INSERT or IGNORE INTO places(worker_id, place)
            VALUES (?, ?)
        """, [(worker_id, place) for place in places])

        if vacations:
            cur.executemany("""
                UPDATE vacations
                    SET vacation_start = ?, vacation_end = ?
                WHERE worker_id = ?
                """, 
                [(v_start, v_end, worker_id) for v_start, v_end in vacations])
        conn.commit()
    except ValueError:
        raise ValueError("Invalid date format")
    finally:
        cur.close()
        conn.close()

# Get all workers names from SQL(workers)
def get_workers_names(user): # [{name: name[str]}]
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT name
        FROM workers
        WHERE username = ?
        ORDER BY name""", 
        (user,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows 

# Get all shifts from SQL(shifts) for months
def get_shifts(user, months): 
 
    # -> {cur: {day[int]: {zone[str]: [name, filled]}}, next:}
    def transform_shifts(change):
        dic = {}
        for line in change:
            dic.setdefault(line['day'], {})[line['zone']] = [line['name'], line['filled']] 
        return dic

    conn = db_connect()
    cur = conn.cursor()
    tables = {
        'cur': {}, 
        'next': {}
    }
    cur.execute("""
        SELECT name, filled, zone, day
        FROM shifts s
            LEFT JOIN workers w ON s.worker_id = w.id
        WHERE username = ?
            AND month = ?
        """, 
        (user, months['cur'][0]))
    change = cur.fetchall()
    tables['cur'] = transform_shifts(change)
    cur.execute("""
        SELECT name, filled, zone, day
        FROM shifts s
            LEFT JOIN workers w ON s.worker_id = w.id
        WHERE username = ?
            AND month = ?
        """, 
        (user, months['next'][0]))
    change = cur.fetchall()
    tables['next'] = transform_shifts(change)
    cur.close()
    conn.close()
    return tables 

# Delete excessive NOT(cur + next) months from SQL(shifts) 
def delete_excessive_shifts(user, months):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM shifts
        WHERE worker_id IN (
            SELECT id FROM workers WHERE username = ?
            ) 
            AND month NOT IN (?, ?) ''',
        (user, *months))
    conn.commit()
    cur.close()
    conn.close()

# Add self filled names to SQL(shifts)
def add_self_shifts(user, filled_self, month):
    conn = db_connect()
    cur = conn.cursor()
    for day, zones in filled_self['next'].items():
        for zone, name in zones.items():
            cur.execute(''' 
                SELECT id FROM workers
                WHERE username = ? AND name = ?
            ''', (user, name))
            row = cur.fetchone()
            worker_id = row[0]
            cur.execute("""
                INSERT INTO shifts (worker_id, month, filled, zone, day)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (worker_id, month, zone, day)
                DO UPDATE SET
                    worker_id = excluded.worker_id
            """, (worker_id, month, 'self', zone, day))
    conn.commit()
    cur.close()
    conn.close()

# Get self filled names from SQL(shifts) for specified zone
def get_self_shifts(user, month, zone): 
    # [{name: str, day: int}]
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        SELECT name, day
        FROM shifts s
            LEFT JOIN workers w ON w.id = s.worker_id
        WHERE month = ? AND zone = ? AND filled = 'self' AND username = ?
    ''', (month, zone, user))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# Get all exceptions (vacations + added) and shifts from SQL(months)
def get_months_workers_updated(user, months):
    # -> {cur: {name: {'exceptions': str, 'shifts': int}}, next:...}
    result = {}
    conn = db_connect()
    cur = conn.cursor()
    for month in months:
        result[month] = {}
        cur.execute("""
            SELECT name, exceptions, m.shifts
            FROM months m
            LEFT JOIN workers w ON w.id = m.worker_id
            WHERE username=? AND month=?
            ORDER BY name""", 
            (user, months[month][0]))
        rows = cur.fetchall()
        for row in rows:
            excs = list(map(int, [d.strip() for d in row['exceptions'].split(',') if d.strip()]))
            result[month][row['name']] = {'exceptions': excs,
                                        'shifts': row['shifts']}
    cur.close()
    conn.close()
    return result

# Delete user previous data and add edited worker's exceptions and shifts to SQL(months)
def add_months_workers(user, month, data):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM months
        WHERE worker_id IN (
            SELECT id FROM workers WHERE username = ?)
    ''', (user,))
    for name in data.keys():
        exceptions = ', '.join([x.strip() 
                      for x in data[name]['exceptions'].split(',') 
                      if x.strip() != '']) # List[int]
        shifts = data[name]['shifts']
        cur.execute('''
            INSERT INTO months(worker_id, month, exceptions, shifts)
            VALUES (
                (SELECT id FROM workers WHERE name = ?), ?, ?, ?
            )
            ON CONFLICT (worker_id)
            DO UPDATE SET
                exceptions = EXCLUDED.exceptions,
                shifts = EXCLUDED.shifts
        ''', (name, month, exceptions, shifts))
    conn.commit()
    cur.close()
    conn.close()

# Generate cur shifts
def get_places_names(user): 
    # {Zone:{name:{shifts: int, role: str}}}

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT place
        FROM places p
            LEFT JOIN workers w ON p.worker_id = w.id 
        WHERE username = ?
        """, (user, ))
    places = [place['place'] for place in cur.fetchall()]
    zones = {}
    for place in places:
        cur.execute("""
            SELECT name, role, shifts
            FROM places p
                LEFT JOIN workers w ON p.worker_id = w.id 
            WHERE username = ?
                AND place = ?
            """, (user, place))
        rows = cur.fetchall()
        zones[place] = {}
        for row in rows:
            zones[place][row['name']] = {'role': row['role'],
                                        'shifts': row['shifts']}
    cur.close()
    conn.close()
    return zones
    
# Get all workers with exceptions and shifts for generation
def generation_info(user, month): 
    # {name: {exceptions: set(), shifts: int}}
    conn = db_connect()
    cur = conn.cursor()
    info = {}
    cur.execute("""
        SELECT name
        FROM workers
        WHERE username = ?
        ORDER BY name""", 
        (user,))
    names = [r['name'] for r in cur.fetchall()]
    placeholders = ','.join(['?' for _ in names])
    cur.execute(f"""
        SELECT w.name, m.exceptions, m.shifts
        FROM months m
            LEFT JOIN workers w ON w.id = m.worker_id
        WHERE w.name IN ({placeholders})
            AND m.month = ?
        """, (*names, month))
    raw = cur.fetchall()
    for line in raw:
        info[line['name']] = {'exceptions': set(map(int, line['exceptions'].split(','))) if line['exceptions'] else set(), 
                              'shifts': line['shifts']}
    cur.close()
    conn.close()
    return info

# Add generated names to SQL(shifts)
def add_auto_shifts(user, graphic, month):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM shifts
        WHERE worker_id IN (
            SELECT id FROM workers WHERE username = ?)
            AND filled = 'auto'
    ''', (user,))
    for day, zones in graphic.items():
        for zone, name in zones.items():
            if name:
                cur.execute(''' 
                    SELECT id FROM workers
                    WHERE username = ? AND name = ?
                ''', (user, name))
                
                row = cur.fetchone()
                worker_id = row[0]
                cur.execute("""
                    INSERT OR IGNORE INTO shifts (worker_id, month, filled, zone, day)
                    VALUES (?, ?, ?, ?, ?)
                """, (worker_id, month, 'auto', zone, day))
    conn.commit()
    cur.close()
    conn.close()

# Clear all data (self+auto) from SQL(shifts) for specified month
def clear_all(user, month):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM shifts
        WHERE worker_id IN (
            SELECT id FROM workers WHERE username = ?
        )
        AND month = ?''', 
        (user, month))
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
        input_password = request.form["password"].strip()
        real_password = get_password(username)
        

        if real_password and real_password[0] == input_password:
            session["user"] = username
            return redirect(url_for("account"))
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html") 

# Main page 
@app.route("/account", methods=["GET"])
def account():
    if "user" not in session:
        return redirect(url_for("login"))
    else:
        user = session["user"]
    
    # Load workers for template
    rows = get_workers(user)
    workers = transform_vacations(rows)

    # Load date for month tabs
    months, years = loaded_date

    # Get workers' vacations for cur+next month
    months_vacations = list_vacation_days(get_month_workers, user, years, months)

    # Get all exceptions (vacations + added) and shifts from SQL(months)
    months_changes = get_months_workers_updated(user, months) 

    # Get all recent info for tables
    months_updated = {'cur': {}, 'next': {}}
    for name, info in months_changes['next'].items():
        days = info['exceptions']
        vacations_with_exceptions = sorted(set(days + months_vacations['next'][name]
                                               if name in months_vacations['next']
                                               else [])
                                            )
        shifts = months_changes['next'][name]['shifts']
        months_updated.setdefault('next', {}).setdefault(name, {})['exceptions'] = vacations_with_exceptions
        months_updated.setdefault('next', {}).setdefault(name, {}).setdefault('shifts', shifts)
    
    # Delete excessive NOT(cur + next) months from SQL(shifts) 
    needed_months = tuple(val[0] for _, val in months.items())
    delete_excessive_shifts(user, needed_months)

    # Highlite differents between added info and basic
    highlights = highlite(months_vacations, workers, months_updated, months)
    
    # Get days for cur + next months 
    months_days = { 
        # {days_in_month: int, days: [{day: int, weekend: bool}]]
        'cur': month_days(years, months, 'cur'),
        'next': month_days(years, months, 'next')
    }
    shifts_tables = get_shifts(session["user"], months=months)
    
    return render_template(
        "account.html",
        username=session["user"],
        months=months,
        years=years,
        workers=workers,
        months_vacations=months_vacations,
        months_updated=months_updated,
        months_days=months_days,
        highlights=highlights,
        shifts_tables = shifts_tables)

# Add new worker to SQL
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
        ", ".join(places)
    )

    return {"success": True}

# Update worker's info in SQL
@app.route('/account/workers/update', methods=['POST'])
def update_workers():
    if "user" not in session:
        return {"success": False, "error": "Unauthorized"}, 401

    data = request.get_json()
    name = data.get("name")
    role = data.get("role")
    vacations = data.get("vacations", [])
    shifts = data.get("shifts")
    places = data.get("places", [])

    # Update worker with same name for current user
    update_worker(session["user"], 
                  name, role, 
                  vacations, 
                  shifts, 
                  places)

    return {"success": True}

# Delete worker from SQL
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

# Save names filled in next month shifts table to SQL(shifts)
@app.route("/account/shifts/save_next", methods=["POST"])
def add_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    months, _= loaded_date
    filled_self = get_shifts(session["user"], months)
    # User submitted names, update SQL (shifts) with new values
    for zone_day, name in request.form.items():
        zone, day = zone_day.split('_')
        filled_self['next'].setdefault(int(day), {})[zone] = name
    add_self_shifts(session['user'], filled_self, month=months['next'][0])
    return {"success": True}

# Save names with exceptions and shifts from next month workers table to SQL (months) 
@app.route("/account/months/save_next", methods=["POST"])
def save_cur_month_workers():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    data = request.get_json()
    months, _ = loaded_date

    add_months_workers(session["user"], months['next'][0], data)
    return data
    
# Clear all names in next month shifts table 
@app.route("/account/shifts/clear_all_shifts", methods=["POST"])
def clear_all_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    month = request.get_json().get('month')
    months, _ = loaded_date
    clear_all(session['user'], month=months[month][0])
    return 'Shifts deleted'

# Generate shifts table in next month 
@app.route("/account/shifts/generate", methods=["POST"])
def generate_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401 
    month = request.get_json().get('month')
    months, years = loaded_date
    days_in_month = month_days(years, months, month)['days_in_month']
    days = month_days(years, months, month)['days']
    zones_info = get_places_names(session["user"]) # {Zone:{name:{shifts: int, role: str}}}
    workers_info = generation_info(session["user"], month=months[month][0]) # {name: {exceptions: set(), shifts: int}}
    graphic = {}
    
    for day in range(1, days_in_month + 1):
        graphic[day] = {}
        for zone in zones_info.keys():
            graphic[day][zone] = None

    # To add rest days to exceptions 
    worker_unavail = { # {name: set(exceptions)} 
        name: info['exceptions'] 
        for name, info in workers_info.items()
    }

    # All shifts change after booking
    shifts_used = {} 
    for zone, names_dict in zones_info.items():
        
        # Add used shifts and rest days for bookings
        rows = get_self_shifts(session["user"], months[month][0], zone)
        booked = {}
        for book in rows:
            name, day = book['name'], book['day']
            graphic[day][zone] = name
            booked.setdefault(day, {})[zone] = name
            # Add shift as used 
            shifts_used[name] = shifts_used.get(name, 0) + 1 
            # Add rest days
            for delta in [-2, -1, 0, 1, 2]: 
                rest_day = day + delta
                if 1 <= rest_day <= days_in_month:
                    worker_unavail[name].add(rest_day)
    # Make graphic for each zone 
    for zone, names_dict in zones_info.items():
        
        # Make heap for zone
        def zone_heap():
            heap = []
            for name in random.sample(list(names_dict.keys()), len(names_dict)):
                shifts_used.setdefault(name, 0)
                heap.append((shifts_used[name], random.random(), name))
            heapq.heapify(heap)
            return heap

        # Basic heap algo
        def base_algo(heap):
            for day in range(1, days_in_month + 1):
                if graphic[day][zone] is not None:
                    continue 
                skip = []
                assign = False
                while heap:
                    used, _, name = heapq.heappop(heap)

                    # Check
                    if used >= workers_info[name]['shifts']:
                        continue
                    if day in worker_unavail[name]:
                        skip.append((used, random.random(), name))
                        continue

                    graphic.setdefault(day, {zone: None})[zone] = name  # Fill in graphic
                    shifts_used[name] = shifts_used.get(name, 0) + 1 # Add shift as used
                    # Add rest days
                    for delta in (0, 1, 2): 
                        rest_day = day + delta
                        if 1 <= rest_day <= days_in_month:
                            worker_unavail[name].add(rest_day)
                    heapq.heappush(heap, (shifts_used[name], random.random(), name)) # Back to heap
                    assign = True
                    break

                # Push back skipped candidates
                for sk in skip:
                    heapq.heappush(heap, sk)
                if not assign:
                    graphic.setdefault(day, {zone: None})[zone] = None
        
        # Priem heap algo
        def priem_algo(heap):
            for day in range(1, days_in_month + 1):
                if graphic[day][zone] is not None:
                    continue 
                skip = []
                assign = False
                while heap:
                    used, _, name = heapq.heappop(heap)

                    # Check
                    if used >= workers_info[name]['shifts']:
                        continue
                    if (day in worker_unavail[name]
                        or names_dict[name]['role'] == 'Day' and days[day] is False):
                        skip.append((used, random.random(), name))
                        continue

                    graphic.setdefault(day, {zone: None})[zone] = name  # Fill in graphic
                    shifts_used[name] = shifts_used.get(name, 0) + 1 # Add shift as used
                    # Add rest days
                    for delta in (0, 1, 2): 
                        rest_day = day + delta
                        if 1 <= rest_day <= days_in_month:
                            worker_unavail[name].add(rest_day)
                    heapq.heappush(heap, (shifts_used[name], random.random(), name)) # Back to heap
                    assign = True
                    break

                # Push back skipped candidates
                for sk in skip:
                    heapq.heappush(heap, sk)
                if not assign:
                    graphic.setdefault(day, {zone: None})[zone] = None

        if zone not in ('GREEN', 'YELLOW'):
            heap = zone_heap()
            base_algo(heap)

        if zone in ('GREEN', 'YELLOW'):
            heap = zone_heap()
            priem_algo(heap)
    print(worker_unavail)
        
    session['graphic'] = graphic
    return graphic

# Save table to Excel file and to SQL(shifts)
@app.route("/account/shifts/save_excel", methods=["POST"])
def save_excel():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401 
    months, _ = loaded_date
    graphic_dict = session['graphic']
    graphic = pd.DataFrame.from_dict(graphic_dict, orient='index')
    graphic = graphic[['OTVET', 'DIAGNOS', 'EXTR', 'PLAN', 'YELLOW', 'GREEN', 'TORAC']]
    
    # Save to SQL(shifts)
    add_auto_shifts(session['user'], graphic_dict, month=months['next'][0])
    output = io.BytesIO()
    graphic.to_excel(output, index=True)
    output.seek(0)
    return send_file(output, download_name='graphic.xlsx', as_attachment=True, 
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# API to get names of workers from SQL to use in JS
@app.route("/api/names")
def api_names():
    if "user" not in session:
        return {"error": "not authenticated"}, 401

    names = [obj['name'] for obj in get_workers_names(session["user"])]
    return {"names": names}


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)