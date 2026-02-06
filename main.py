from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import calendar
import sqlite3
from datetime import datetime, date, timedelta
from config import Config
from collections import defaultdict
import heapq 

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
loaded_date = load_date()

def month_days(years, months, current_month):
    days_in_month = calendar.monthrange(years[current_month], months[current_month][0])[1]
    days = [
        {'day': day, 'is_weekend': datetime(years[current_month], months[current_month][0], day).weekday() >= 5}
        for day in range(1, days_in_month + 1)]
    return {'days_in_month': days_in_month, 
            'days': days}

# Transform vacations to interval string 'dd.mm.yyyy(start) - dd.mm.yyyy(end), ...'
def transform_vacations(rows):
    workers = {} #{name: {role: str, shifts: int, places: str, vacations: str}}
    vacations_dict = defaultdict(list)
    places_dict = defaultdict(list)
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

@app.errorhandler(ValueError)
def _(e):
    return jsonify(ok=False, error=str(e)), 400

@app.errorhandler(sqlite3.IntegrityError)
def _(e):
    return jsonify(ok=False, error=str(e)), 409

# ---------------------------------------------------------
# SQLite DATABASE
# ---------------------------------------------------------

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

# Create SQL table (shifts) for dates and zones for names for specified month (prev, cur, next)
def create_shifts_table():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            filled TEXT NOT NULL,
            zone TEXT NOT NULL,
            day INTEGER NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
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
            month TEXT NOT NULL,
            exceptions TEXT NOT NULL,
            shifts INTEGER NOT NULL,
            FOREIGN KEY (worker_id)
                REFERENCES workers(id)
                ON DELETE CASCADE
            UNIQUE (worker_id)
        )
    """)
    # cur.execute('''DROP TABLE IF EXISTS months''')
    conn.commit()
    cur.close()
    conn.close()
create_months_table()


# ---------------------------------------------------------
# DATABASE ACTIONS
# ---------------------------------------------------------

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
                SET role = ?, shifts = ?, places = ?
            WHERE username = ? AND name = ?
        """, (role, shifts, places, username, name))
        
        cur.execute("""
            SELECT id FROM workers
            WHERE username = ? AND name = ?
        """, (username, name))
        
        row = cur.fetchone()
        worker_id = row[0]

        cur.executemany(""" 
            UPDATE places 
                SET place = ?
            WHERE worker_id = ?
        """, [(place, worker_id) for place in places])

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
def get_shifts(user): 

    # [{name: name[str], filled: [self/auto], zone: [str], day: [int]}, {}] 
    # -> {day[int]: {zone[str]: [name, filled]}}
    def transform_shifts(change):
        dic = {}
        for line in change:
            dic.setdefault(line['day'], {})[line['zone']] = [line['name'], line['filled']] 
        return dic

    conn = db_connect()
    cur = conn.cursor()
    tables = {
        'prev': [], 
        'cur': [], 
        'next': []
    }
    cur.execute("""
        SELECT name, filled, zone, day
        FROM shifts s
            LEFT JOIN workers w ON s.worker_id = w.id
        WHERE username = ?
            AND month = 'prev'
        """, 
        (user,))
    change = cur.fetchall()
    tables['prev'] = transform_shifts(change)
    cur.execute("""
        SELECT name, filled, zone, day
        FROM shifts s
            LEFT JOIN workers w ON s.worker_id = w.id 
        WHERE username = ?
            AND month = 'cur'
        """, 
        (user,))
    change = cur.fetchall()
    tables['cur'] = transform_shifts(change)
    cur.execute("""
        SELECT name, filled, zone, day
        FROM shifts s
            LEFT JOIN workers w ON s.worker_id = w.id
        WHERE username = ?
            AND month = 'prev'
        """, 
        (user,))
    change = cur.fetchall()
    tables['next'] = transform_shifts(change)
    cur.close()
    conn.close()
    return tables 

# Add self filled names to SQL(shifts)
def add_self_shifts(user, filled_self, month):
    conn = db_connect()
    cur = conn.cursor()
    for day, zones in filled_self.items():
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
def get_self_shifts(user, month, zone): # [{name: str, day: int}]
    conn = db_connect()
    cur = conn.cursor()
    cur.execute('''
        SELECT name, day
        FROM shifts s
            LEFT JOIN workers w ON w.id = s.worker_id
        WHERE month = ? AND zone = ? AND filled = 'self' AND username = ?
    ''', (month, zone, user))
    rows = cur.fetchall()
    print(rows)
    cur.close()
    conn.close()
    return rows

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
def get_places_names(user): # {Zone:{name:{shifts: int, role: str}}}
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
def generation_info(user, month): # {name: {exceptions: set(), shifts: int}}
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
def add_auto_shifts(user, filled_self, month):
    pass

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
    
    # Load workers for template
    rows = get_workers(session["user"])
    workers = transform_vacations(rows)

    # Load date for month tabs
    months, years = loaded_date

    months_vacations = list_vacation_days(get_month_workers, user, years, months)
    
    month_shift_table = {
        'prev': month_days(years, months, 'prev'), # {days_in_month: int, days: [{day: int, weekend: bool}]]
        'cur': month_days(years, months, 'cur'),
        'next': month_days(years, months, 'next')}
    
    shifts_tables = get_shifts(session["user"])
    return render_template(
        "account.html",
        username=session["user"],
        months=months,
        years=years,
        workers=workers,
        months_vacations=months_vacations,
        month_shift_table=month_shift_table,
        shifts_tables = shifts_tables)

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
    vacations = data.get("vacations", [])
    shifts = data.get("shifts")
    places = data.get("places", [])

    # Update worker with same name for current user
    update_worker(session["user"], 
                  name, role, 
                  vacations, 
                  shifts, 
                  ', '.join(places))

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

# Save names filled in cur table to SQL(shifts)
@app.route("/account/shifts/save_cur", methods=["POST"])
def add_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    filled_self = get_shifts(session["user"])['cur']
    # User submitted names, update SQL (shifts) with new values
    for zone_day, name in request.form.items():
        zone, day = zone_day.split('_')
        filled_self.setdefault(int(day), {})[zone] = name
    add_self_shifts(session['user'], filled_self, 'cur')
    return {"success": True}

# Save names with exceptions and shifts from cur month to SQL (months) 
@app.route("/account/months/save_cur", methods=["POST"])
def save_cur_month_workers():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    data = request.get_json()
    add_months_workers(session["user"], 'cur', data)
    return data

# Clear generated names in cur month 
@app.route("/account/shifts/clear_cur_generated", methods=["POST"])
def clear_cur_generated():
    pass

# Clear all names in cur month 
@app.route("/account/shifts/clear_cur_all", methods=["POST"])
def clear_cur_all():
    pass

# Generate shifts table in cur month 
@app.route("/account/shifts/generate_cur", methods=["POST"])
def generate_cur_shifts():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}, 401
    
    graphic = {}
    months, years = loaded_date
    days_in_month = month_days(years, months, 'cur')['days_in_month']
    zones_info = get_places_names(session["user"]) # {Zone:{name:{shifts: int, role: str}}}
    workers_info = generation_info(session["user"], 'cur') # {name: {exceptions: set(), shifts: int}}
    zones_candidates = {zone: zones_info[zone] for zone in zones_info.keys()} # {zone: [names]}
    worker_unavail = {
        name: workers_info[name]['exceptions'] 
        for name in zones_candidates['OTVET']
    }

    # Make booking
    for zone in zones_info.keys():    
        rows = get_self_shifts(session["user"], 'cur', zone)
        for book in rows:
            name, day = book['name'], book['day']
            graphic[day] = {zone: name}
            for delta in [-2, -1, 0, 1, 2]: # add rest days  
                rest_day = day + delta
                if 1 <= rest_day <= days_in_month:
                    worker_unavail[name].add(rest_day)
    print(worker_unavail)

    # # Making heap for otvet
    # zone_heap = []
    # for name in zones_candidates['OTVET']:
    #     zone_heap.append((0, 1, name)) # (shifts_used, next_available_day, name)
    # heapq.heapify(zone_heap)
    # shifts_used_otvet = {}
    # next_available_otvet = {}
    
    # # Algo for otvet
    # for day in range(1, days_in_month + 1):
    #     skip = []
    #     assign = False
    #     if day in graphic and 'OTVET' in graphic[day]:
    #         continue 
    #     while zone_heap:
    #         used, avail, name = heapq.heappop(zone_heap)

    #         # Check
    #         if used >= workers_info[name]['shifts']:
    #             continue
    #         if day < avail:
    #             skip.append((used, avail, name))
    #             continue
    #         if day in workers_info[name]['exceptions']:
    #             skip.append((used, avail, name))
    #             continue

    #         graphic.setdefault(day, {'OTV': None})['OTV'] = name  
    #         shifts_used_otvet[name] = shifts_used_otvet.get(name, 0) + 1 
    #         next_available_otvet[name] = next_available_otvet.get(name, day) + 3
    #         heapq.heappush(zone_heap, 
    #                        (shifts_used_otvet[name], next_available_otvet[name], name))
    #         assign = True
    #         break
        
    #     # Push back skipped candidates
    #     for sk in skip:
    #         heapq.heappush(zone_heap, sk)
    #     if not assign:
    #         graphic.setdefault(day, {'OTV': None})['OTV'] = None
    return graphic

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
