from flask import Flask, Blueprint, render_template, request, redirect, url_for, jsonify, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import MySQLdb
import re
app = Flask(__name__)

# Configure MySQL
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345678'
app.config['MYSQL_DB'] = 'museum'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['SECRET_KEY'] = 'your_secret_key'  # Set a strong secret key

mysql = MySQL(app)

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Helper function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Reconnect MySQL if necessary

visitor_info = {}

def get_available_events():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, title, event_date, start_time FROM events WHERE event_date >= CURDATE()")
    events = cur.fetchall()
    cur.close()
    return events

@app.route('/chatbot', methods=['POST'])
def chatbot():
    global visitor_info
    user_message = request.json['message'].strip().lower()
    
    response = ""

    if "book" in user_message or "ticket" in user_message:
        response = "I can help you book a ticket. May I know your name?"
        visitor_info['state'] = 'asking_name'

    elif visitor_info.get('state') == 'asking_name':
        visitor_info['name'] = user_message.title()
        response = f"Thanks, {visitor_info['name']}! Can you please provide your email?"
        visitor_info['state'] = 'asking_email'

    elif visitor_info.get('state') == 'asking_email':
        if re.match(r"[^@]+@[^@]+\.[^@]+", user_message):
            visitor_info['email'] = user_message
            response = "Great! Now, can I have your phone number?"
            visitor_info['state'] = 'asking_phone'
        else:
            response = "Please provide a valid email address."

    elif visitor_info.get('state') == 'asking_phone':
        if re.match(r"^\+?1?\d{9,15}$", user_message):
            visitor_info['phone'] = user_message
            response = "Thank you! How many adults are visiting?"
            visitor_info['state'] = 'asking_adults'
        else:
            response = "Please provide a valid phone number."

    elif visitor_info.get('state') == 'asking_adults':
        try:
            visitor_info['adults'] = int(user_message)
            response = "How many children are visiting?"
            visitor_info['state'] = 'asking_children'
        except ValueError:
            response = "Please enter a valid number of adults."

    elif visitor_info.get('state') == 'asking_children':
        try:
            visitor_info['children'] = int(user_message)
            response = "How many school students are visiting?"
            visitor_info['state'] = 'asking_students'
        except ValueError:
            response = "Please enter a valid number of children."

    elif visitor_info.get('state') == 'asking_students':
        try:
            visitor_info['students'] = int(user_message)
            events = get_available_events()
            if events:
                response = "Here are the upcoming events:\n"
                for event in events:
                    response += f"- {event['id']} {event['title']} on {event['event_date']} at {event['start_time']}\n"
                response += "Please select an event by typing the event ID."
                visitor_info['state'] = 'selecting_event'
                visitor_info['events'] = events
            else:
                response = "No events available at the moment."
                visitor_info['state'] = None
        except ValueError:
            response = "Please enter a valid number of students."

    elif visitor_info.get('state') == 'selecting_event':
        try:
            selected_event = int(user_message)
            event = next((event for event in visitor_info['events'] if event['id'] == selected_event), None)
            if event:
                visitor_info['event_id'] = event['id']
                total_price = (visitor_info['adults'] * 20) + ((visitor_info['children'] + visitor_info['students']) * 15)
                visitor_info['total_amount'] = total_price
                response = (f"You're booking tickets for the event: {event['title']} on {event['event_date']} at {event['start_time']}.\n"
                            f"Total amount: Rs{total_price}. Type 'confirm' to proceed with the booking.")
                visitor_info['state'] = 'confirming_booking'
            else:
                response = "Invalid event ID. Please select a valid event."
        except ValueError:
            response = "Please provide a valid event ID."

    elif visitor_info.get('state') == 'confirming_booking':
        if user_message == 'confirm':
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO visitors (name, email, phone) VALUES (%s, %s, %s)",
                (visitor_info['name'], visitor_info['email'], visitor_info['phone'])
            )
            visitor_id = cur.lastrowid

            cur.execute(
                "INSERT INTO tickets (event_id, visit_date, adults, students, children, total_amount, visitor_id) "
                "VALUES (%s, CURDATE(), %s, %s, %s, %s, %s)",
                (visitor_info['event_id'], visitor_info['adults'], visitor_info['students'], visitor_info['children'],
                 visitor_info['total_amount'], visitor_id)
            )
            mysql.connection.commit()
            cur.close()

            response = "Your ticket has been successfully booked! Use your email and phone number to check your ticket."
            visitor_info.clear()
        else:
            response = "Please type 'confirm' to book the ticket or restart the booking process."

    else:
        response = "Hello! How can I assist you today? You can book a ticket, check event timings, or get more information."

    return jsonify({"message": response})


# app.register_blueprint(chatbot_blueprint)

# Register the blueprint


@app.route('/')
def home():
    return render_template('home.html')
@app.route('/events')
def events():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM events ORDER BY event_date ASC')
    events = cursor.fetchall()
    cursor.close()
    return render_template('events.html', events=events)

# Booking Form Route
@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    if request.method == 'POST':
        # Collect form data
        visitor_name = request.form['visitor_name']
        visitor_email = request.form['visitor_email']
        visitor_phone = request.form['visitor_phone']
        event_id = request.form['event_id']
        visit_date = request.form['visit_date']
        adults = int(request.form['adults'])
        students = int(request.form['students'])
        children = int(request.form['children'])

        # Calculate total amount (example prices: adults $20, students $15, children $10)
        total_amount = adults * 20 + students * 15 + children * 10

        # Insert visitor details into visitors table
        cursor = mysql.connection.cursor()
        cursor.execute(
            'INSERT INTO visitors (name, email, phone) VALUES (%s, %s, %s)',
            (visitor_name, visitor_email, visitor_phone)
        )
        visitor_id = cursor.lastrowid  # Get the inserted visitor's ID
        
        # Insert ticket details into tickets table
        cursor.execute(
            'INSERT INTO tickets (event_id, visit_date, adults, students, children, total_amount, visitor_id) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (event_id, visit_date, adults, students, children, total_amount, visitor_id)
        )
        ticket_id = cursor.lastrowid  # Get the inserted ticket's ID
        mysql.connection.commit()
        cursor.close()

        # Store ticket_id in session to pass to the summary page
        session['ticket_id'] = ticket_id

        # Redirect to the summary page
        return redirect(url_for('ticket_summary'))

    # Fetch available events based on selected visit date (if provided)
    visit_date = request.args.get('visit_date')
    events = []
    if visit_date:
        cursor = mysql.connection.cursor()
        cursor.execute(
            'SELECT * FROM events WHERE event_date = %s',
            [visit_date]
        )
        events = cursor.fetchall()
        cursor.close()

    return render_template('book_ticket.html', events=events, visit_date=visit_date)

@app.route('/ticketchat')
def ticketchat():
    return render_template('ticketchat.html')


@app.route('/ticket_summary', methods=['GET', 'POST'])
def ticket_summary():
    ticket_id = session.get('ticket_id')

    if ticket_id:
        # Fetch ticket and visitor details
        cursor = mysql.connection.cursor()
        cursor.execute(
            'SELECT tickets.*, events.title, visitors.name, visitors.email, visitors.phone '
            'FROM tickets '
            'JOIN events ON tickets.event_id = events.id '
            'JOIN visitors ON tickets.visitor_id = visitors.id '
            'WHERE tickets.id = %s', [ticket_id]
        )
        ticket_details = cursor.fetchone()
        cursor.close()

        if request.method == 'POST':
            # Proceed to payment or confirm booking
            return redirect(url_for('ticket'))

        return render_template('ticket_summary.html', ticket=ticket_details)

    return redirect(url_for('book_ticket'))

@app.route('/ticket')
def ticket():
    ticket_id = session.get('ticket_id')

    if ticket_id:
        # Fetch ticket, event, and visitor details, including start and end times
        cursor = mysql.connection.cursor()
        cursor.execute(
            'SELECT tickets.*, events.title, events.start_time, events.end_time, visitors.name, visitors.email, visitors.phone '
            'FROM tickets '
            'JOIN events ON tickets.event_id = events.id '
            'JOIN visitors ON tickets.visitor_id = visitors.id '
            'WHERE tickets.id = %s', [ticket_id]
        )
        ticket_details = cursor.fetchone()
        cursor.close()

        return render_template('ticket.html', ticket=ticket_details)

    return redirect(url_for('book_ticket'))

@app.route('/check_ticket', methods=['GET', 'POST'])
def check_ticket():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')

        print("Form Data Received:", name, email, phone)  # Debugging Print Statement

        cursor = mysql.connection.cursor()
        cursor.execute(
            'SELECT * FROM visitors WHERE name = %s AND email = %s AND phone = %s',
            (name, email, phone)
        )
        visitor = cursor.fetchone()

        if visitor:
            visitor_id = visitor['id']

            # Fetch tickets for this visitor
            cursor.execute(
                'SELECT tickets.*, events.title, events.start_time, events.end_time '
                'FROM tickets '
                'JOIN events ON tickets.event_id = events.id '
                'WHERE tickets.visitor_id = %s', [visitor_id]
            )
            tickets = cursor.fetchall()
            cursor.close()

            if tickets:
                return render_template('check_ticket.html', ticket=tickets[0])  # Use first ticket for testing
            else:
                error = 'No tickets found for this visitor.'
                return render_template('check_ticket.html', error=error)
        else:
            error = 'No visitor found with the provided details.'
            return render_template('check_ticket.html', error=error)

    return render_template('check_ticket.html')

# Admin Login Route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM admins WHERE username = %s', [username])
        admin = cursor.fetchone()
        cursor.close()

        if admin and check_password_hash(admin['password'], password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.')

    return render_template('admin_login.html')

#@app.route('/admin_dashboard')
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    cursor = mysql.connection.cursor()

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        # Fetch tickets between selected dates
        cursor.execute(
            'SELECT * FROM tickets WHERE visit_date BETWEEN %s AND %s',
            (start_date, end_date)
        )
        tickets = cursor.fetchall()

        # Calculate number of visitors and revenue
        num_visitors = len(set(ticket['visitor_id'] for ticket in tickets))
        total_revenue = sum(ticket['total_amount'] for ticket in tickets)

        # Prepare data for charts (group by month for demo purposes)
        cursor.execute('''
            SELECT 
                DATE_FORMAT(visit_date, '%Y-%m') as month,
                SUM(total_amount) as revenue,
                COUNT(DISTINCT visitor_id) as visitors
            FROM tickets
            GROUP BY month
        ''')
        analytics_data = cursor.fetchall()

        # Separate data for use in charts
        revenue_data = [data['revenue'] for data in analytics_data]
        visitors_data = [data['visitors'] for data in analytics_data]
        labels = [data['month'] for data in analytics_data]

        cursor.close()

        return render_template(
            'admin_dashboard.html',
            tickets=tickets,
            num_visitors=num_visitors,
            revenue=total_revenue,
            revenue_data=revenue_data,
            visitors_data=visitors_data,
            labels=labels
        )
    
    # Fetch all events
    cursor.execute('SELECT * FROM events')
    events = cursor.fetchall()
    cursor.close()

    return render_template('admin_dashboard.html', events=events)


@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        # Handle the photo upload
        photo = request.files['photo']
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_url = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        else:
            photo_url = None  # or a default placeholder

        cursor = mysql.connection.cursor()
        cursor.execute(
            'INSERT INTO events (title, description, photo_url, event_date, start_time, end_time) VALUES (%s, %s, %s, %s, %s, %s)',
            (title, description, photo_url, event_date, start_time, end_time)
        )
        mysql.connection.commit()
        cursor.close()
        flash('Event added successfully.')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_event.html')
@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM events WHERE id = %s', [event_id])
    event = cursor.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        # Handle the photo upload
        photo = request.files['photo']
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_url = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        else:
            photo_url = event['photo_url']  # Keep existing photo if none is uploaded

        cursor.execute(
            'UPDATE events SET title = %s, description = %s, photo_url = %s, event_date = %s, start_time = %s, end_time = %s WHERE id = %s',
            (title, description, photo_url, event_date, start_time, end_time, event_id)
        )
        mysql.connection.commit()
        cursor.close()
        flash('Event updated successfully.')
        return redirect(url_for('admin_dashboard'))

    cursor.close()
    return render_template('edit_event.html', event=event)


@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM events WHERE id = %s', [event_id])
    mysql.connection.commit()
    cursor.close()
    flash('Event deleted successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# Route for the Membership page
@app.route('/membership')
def membership():
    return render_template('membership.html')

# Routes for the Login and Registration pages
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

# Create admin with username 'admin' and password 'admin' (hashed)
def setup_admin():
    with app.app_context():
        try:
            cursor = mysql.connection.cursor()
        except MySQLdb.OperationalError as e:
            mysql.connection.ping(True)
            cursor = mysql.connection.cursor()

        # Ensure table exists
        cursor.execute('CREATE TABLE IF NOT EXISTS admins (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(255) UNIQUE NOT NULL, password VARCHAR(255) NOT NULL)')
        
        # Check if admin already exists
        cursor.execute('SELECT * FROM admins WHERE username = %s', ['admin'])
        admin = cursor.fetchone()

        if not admin:
            hashed_password = generate_password_hash('admin', method='pbkdf2:sha256')
            cursor.execute('INSERT INTO admins (username, password) VALUES (%s, %s)', ('admin', hashed_password))
            mysql.connection.commit()
        
        cursor.close()

# Setup admin
with app.app_context():
    setup_admin()



if __name__ == '__main__':
    app.run(debug=True)
