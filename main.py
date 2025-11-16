from flask import Flask, render_template, request, session, redirect, url_for, flash
import calendar
import psycopg2
from datetime import datetime
from config import Config

people = ["Alice", "Bob", "Charlie", "David", "Eva", "Frank"]

app = Flask(__name__)
app.config.from_object(Config)

def db_connect():
    conn = psycopg2.connect(
        host = app.config['DB_HOST'],
        port = app.config['DB_PORT'],
        user = app.config['DB_USER'],
        password = app.config['DB_PASSWORD'],
        dbname = app.config['DB_NAME']
    )
    return conn

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"].strip()

        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row and row[0] == password:
            session["user"] = username
            return redirect(url_for("account"))
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html") 

@app.route("/account")
def account():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("account.html", username=session["user"])

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
        print(request.form)
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
        people=people
    )

# Completely resets page
@app.route('/reset', methods=['POST'])
def reset():
    session.clear()  # Clear all session data
    return redirect(url_for('index'))  #

if __name__ == '__main__':
    app.run(debug=True)
