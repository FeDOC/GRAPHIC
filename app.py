from flask import Flask, render_template, request, session
import calendar
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session handling

@app.route('/', methods=['GET', 'POST'])
def index():
    year = session.get('year')  # Retrieve stored year (if any)
    month = session.get('month')  # Retrieve stored month (if any)
    days_in_month = session.get('days_in_month', 0)  # Retrieve stored days (default 0)
    table_rows = session.get('table_rows', [])

    if 'generate_table' in request.form:
        # User entered a new year and month
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
            for column_name, name in request.form.items():
                if column_name.startswith('name_') and column_name.endswith(f'_{row["day"]}'):
                    row[column_name] = name  # Save entered name into the correct row

        # Store updated table in session
        session['table_rows'] = table_rows

    return render_template(
        'index.html',
        year=year,
        month=month,
        days_in_month=days_in_month,
        table_rows=table_rows
    )

if __name__ == '__main__':
    app.run(debug=True)
