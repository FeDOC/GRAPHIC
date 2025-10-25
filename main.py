from flask import Flask, render_template, request, session, redirect, url_for
import calendar
from datetime import datetime

people = ["Alice", "Bob", "Charlie", "David", "Eva", "Frank"]

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling

@app.route('/', methods=['GET', 'POST'])
def index():
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
