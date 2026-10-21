
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from functools import wraps
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
import mysql.connector

app = Flask(__name__)
app.secret_key = "college-project-secret-key"


# 1. DATABASE CONNECTION

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Wadawaowao@123",
        database="public_transport"
    )


# Require a logged-in account
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# Require an admin account
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "account_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("user_dashboard"))

        return view(*args, **kwargs)
    return wrapped


# 2. TABLE CONFIGURATION

ENTITIES = {
    "passengers": {
        "table": "Passengers",
        "title": "Passengers",
        "pk": "passenger_id",
        "columns": [
            ("passenger_id", "Passenger ID"),
            ("name", "Name"),
            ("email", "Email"),
            ("phone", "Phone")
        ],
        "fields": [
            ("name", "Name", "text"),
            ("email", "Email", "email"),
            ("phone", "Phone", "text")
        ]
    },

    "routes": {
        "table": "Routes",
        "title": "Routes",
        "pk": "route_id",
        "columns": [
            ("route_id", "Route ID"),
            ("route_name", "Route Name"),
            ("start_point", "Start Point"),
            ("end_point", "End Point")
        ],
        "fields": [
            ("route_name", "Route Name", "text"),
            ("start_point", "Start Point", "text"),
            ("end_point", "End Point", "text")
        ]
    },

    "buses": {
        "table": "Buses",
        "title": "Buses",
        "pk": "bus_id",
        "columns": [
            ("bus_id", "Bus ID"),
            ("route_id", "Route ID"),
            ("bus_number", "Bus Number"),
            ("capacity", "Capacity")
        ],
        "fields": [
            ("route_id", "Route", "route"),
            ("bus_number", "Bus Number", "text"),
            ("capacity", "Capacity", "number")
        ]
    },

    "tickets": {
        "table": "Tickets",
        "title": "Tickets",
        "pk": "ticket_id",
        "columns": [
            ("ticket_id", "Ticket ID"),
            ("passenger_id", "Passenger ID"),
            ("bus_id", "Bus ID"),
            ("travel_date", "Travel Date"),
            ("seat_number", "Seat Number")
        ],
        "fields": [
            ("passenger_id", "Passenger", "passenger"),
            ("bus_id", "Bus", "bus"),
            ("travel_date", "Travel Date", "date"),
            ("seat_number", "Seat Number", "number")
        ]
    }
}


# 3. DROPDOWN OPTIONS FOR FOREIGN KEYS

def get_options(field_type):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        if field_type == "route":
            cursor.execute(
                "SELECT route_id, route_name FROM Routes"
            )

        elif field_type == "passenger":
            cursor.execute(
                "SELECT passenger_id, name FROM Passengers"
            )

        elif field_type == "bus":
            cursor.execute(
                "SELECT bus_id, bus_number FROM Buses"
            )

        else:
            return []

        return cursor.fetchall()

    finally:
        cursor.close()
        db.close()


# 4. HOME PAGE

@app.route("/")
def home():
    return render_template("index.html")


# 5. DISPLAY RECORDS

@app.route("/<entity>")
@admin_required
def list_records(entity):
    if entity not in ENTITIES:
        return "Page not found", 404

    config = ENTITIES[entity]
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            f"SELECT * FROM {config['table']} "
            f"ORDER BY {config['pk']} DESC"
        )
        rows = cursor.fetchall()

        cursor.execute(
            f"SELECT COUNT(*) FROM {config['table']}"
        )
        total = cursor.fetchone()[0]

        return render_template(
            "records.html",
            entity=entity,
            config=config,
            rows=rows,
            total=total
        )

    finally:
        cursor.close()
        db.close()


# 6. ADD A RECORD

@app.route("/<entity>/add", methods=["GET", "POST"])
@admin_required
def add_record(entity):
    if entity not in ENTITIES:
        return "Page not found", 404

    config = ENTITIES[entity]

    if request.method == "POST":
        values = []

        for field, label, field_type in config["fields"]:
            value = request.form.get(field, "").strip()

            if not value:
                flash(f"{label} is required.", "error")
                return redirect(url_for("add_record", entity=entity))

            if field_type == "number":
                try:
                    value = int(value)
                    if value <= 0:
                        raise ValueError
                except ValueError:
                    flash(f"{label} must be a positive number.", "error")
                    return redirect(url_for("add_record", entity=entity))

            values.append(value)

        db = get_db_connection()
        cursor = db.cursor()

        try:
            fields = [field[0] for field in config["fields"]]
            placeholders = ", ".join(["%s"] * len(fields))
            field_names = ", ".join(fields)

            query = (
                f"INSERT INTO {config['table']} "
                f"({field_names}) VALUES ({placeholders})"
            )

            cursor.execute(query, tuple(values))
            db.commit()

            flash(f"{config['title']} record added successfully!", "success")
            return redirect(url_for("list_records", entity=entity))

        except mysql.connector.Error as error:
            db.rollback()
            flash(f"Could not save record: {error.msg}", "error")

        finally:
            cursor.close()
            db.close()

    options = {
        field: get_options(field_type)
        for field, label, field_type in config["fields"]
        if field_type in ("route", "passenger", "bus")
    }

    return render_template(
        "form.html",
        entity=entity,
        config=config,
        mode="Add",
        record={},
        options=options
    )


# 7. EDIT A RECORD

@app.route("/<entity>/edit/<int:record_id>", methods=["GET", "POST"])
@admin_required
def edit_record(entity, record_id):
    if entity not in ENTITIES:
        return "Page not found", 404

    config = ENTITIES[entity]
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            f"SELECT * FROM {config['table']} "
            f"WHERE {config['pk']} = %s",
            (record_id,)
        )
        record = cursor.fetchone()

        if record is None:
            flash("Record not found.", "error")
            return redirect(url_for("list_records", entity=entity))

        if request.method == "POST":
            values = []

            for field, label, field_type in config["fields"]:
                value = request.form.get(field, "").strip()

                if not value:
                    flash(f"{label} is required.", "error")
                    return redirect(
                        url_for(
                            "edit_record",
                            entity=entity,
                            record_id=record_id
                        )
                    )

                if field_type == "number":
                    try:
                        value = int(value)
                        if value <= 0:
                            raise ValueError
                    except ValueError:
                        flash(f"{label} must be a positive number.", "error")
                        return redirect(
                            url_for(
                                "edit_record",
                                entity=entity,
                                record_id=record_id
                            )
                        )

                values.append(value)

            fields = [field[0] for field in config["fields"]]
            assignments = ", ".join(
                f"{field} = %s" for field in fields
            )

            try:
                cursor.execute(
                    f"UPDATE {config['table']} SET {assignments} "
                    f"WHERE {config['pk']} = %s",
                    tuple(values) + (record_id,)
                )
                db.commit()

                flash("Record updated successfully!", "success")
                return redirect(url_for("list_records", entity=entity))

            except mysql.connector.Error as error:
                db.rollback()
                flash(f"Could not update record: {error.msg}", "error")

    finally:
        cursor.close()
        db.close()

    options = {
        field: get_options(field_type)
        for field, label, field_type in config["fields"]
        if field_type in ("route", "passenger", "bus")
    }

    return render_template(
        "form.html",
        entity=entity,
        config=config,
        mode="Edit",
        record=record,
        options=options
    )


# 8. DELETE A RECORD

@app.route("/<entity>/delete/<int:record_id>", methods=["POST"])
@admin_required
def delete_record(entity, record_id):
    if entity not in ENTITIES:
        return "Page not found", 404

    config = ENTITIES[entity]
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            f"DELETE FROM {config['table']} "
            f"WHERE {config['pk']} = %s",
            (record_id,)
        )
        db.commit()

        if cursor.rowcount:
            flash("Record deleted successfully!", "success")
        else:
            flash("Record not found.", "error")

    except mysql.connector.Error as error:
        db.rollback()
        flash(
            "Cannot delete this record. Other records may depend on it. "
            + error.msg,
            "error"
        )

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("list_records", entity=entity))



# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT account_id, email, password_hash,
                       role, passenger_id
                FROM Accounts
                WHERE email = %s
                """,
                (email,)
            )
            account = cursor.fetchone()
        finally:
            cursor.close()
            db.close()

        if account and check_password_hash(
            account["password_hash"], password
        ):
            session.clear()
            session["account_id"] = account["account_id"]
            session["email"] = account["email"]
            session["role"] = account["role"]
            session["passenger_id"] = account["passenger_id"]

            if account["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("user_dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# USER REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not phone:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        db = get_db_connection()
        cursor = db.cursor()

        try:
            # Keep passenger creation and account creation together.
            db.start_transaction()

            cursor.execute(
                """
                INSERT INTO Passengers (name, email, phone)
                VALUES (%s, %s, %s)
                """,
                (name, email, phone)
            )
            passenger_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO Accounts
                    (email, password_hash, role, passenger_id)
                VALUES (%s, %s, 'user', %s)
                """,
                (
                    email,
                    generate_password_hash(password),
                    passenger_id
                )
            )

            db.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        except mysql.connector.Error:
            db.rollback()
            flash(
                "Registration failed. This email may already be registered.",
                "error"
            )

        finally:
            cursor.close()
            db.close()

    return render_template("register.html")


# LOGOUT
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))



# ADMIN DASHBOARD
@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db_connection()
    cursor = db.cursor()

    try:
        counts = {}

        for entity, config in ENTITIES.items():
            cursor.execute(
                f"SELECT COUNT(*) FROM {config['table']}"
            )
            counts[entity] = cursor.fetchone()[0]

        return render_template("admin_dashboard.html", counts=counts)

    finally:
        cursor.close()
        db.close()


# USER DASHBOARD
@app.route("/user")
@login_required
def user_dashboard():
    if session.get("role") != "user":
        return redirect(url_for("admin_dashboard"))

    return render_template("user_dashboard.html")



@app.route("/user/routes")
@login_required
def user_routes():
    if session.get("role") != "user":
        return redirect(url_for("admin_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                r.route_name,
                r.start_point,
                r.end_point,
                b.bus_number,
                b.capacity
            FROM Routes r
            LEFT JOIN Buses b ON r.route_id = b.route_id
            ORDER BY r.route_name, b.bus_number
        """)

        routes = cursor.fetchall()

        return render_template(
            "user_routes.html",
            routes=routes
        )

    finally:
        cursor.close()
        db.close()


# BOOK A TICKET
@app.route("/user/book", methods=["GET", "POST"])
@login_required
def book_ticket():
    if session.get("role") != "user":
        return redirect(url_for("admin_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        if request.method == "POST":
            bus_id = request.form.get("bus_id", "")
            travel_date = request.form.get("travel_date", "")
            seat_number = request.form.get("seat_number", "")

            try:
                bus_id = int(bus_id)
                seat_number = int(seat_number)

                if bus_id <= 0 or seat_number <= 0:
                    raise ValueError

                from datetime import date
                travel_date = date.fromisoformat(travel_date)

                if travel_date < date.today():
                    flash("Travel date cannot be in the past.", "error")
                    return redirect(url_for("book_ticket"))

            except (ValueError, TypeError):
                flash("Please enter valid booking details.", "error")
                return redirect(url_for("book_ticket"))

            cursor.execute(
                "SELECT capacity FROM Buses WHERE bus_id = %s",
                (bus_id,)
            )
            bus = cursor.fetchone()

            if not bus:
                flash("Selected bus does not exist.", "error")
                return redirect(url_for("book_ticket"))

            if seat_number > bus["capacity"]:
                flash("Seat number exceeds bus capacity.", "error")
                return redirect(url_for("book_ticket"))

            try:
                cursor.execute(
                    """
                    INSERT INTO Tickets
                        (passenger_id, bus_id, travel_date, seat_number)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session["passenger_id"],
                        bus_id,
                        travel_date,
                        seat_number
                    )
                )
                db.commit()

                flash("Ticket booked successfully!", "success")
                return redirect(url_for("my_bookings"))

            except mysql.connector.Error as error:
                db.rollback()
                if error.errno == 1062:
                    flash(
                        "That seat is already booked for this bus and date.",
                        "error"
                    )
                else:
                    flash("Booking failed. Please try again.", "error")

        cursor.execute("""
            SELECT
                b.bus_id,
                b.bus_number,
                b.capacity,
                r.route_name,
                r.start_point,
                r.end_point
            FROM Buses b
            JOIN Routes r ON b.route_id = r.route_id
            ORDER BY b.bus_number
        """)

        buses = cursor.fetchall()

        return render_template("book_ticket.html", buses=buses)

    finally:
        cursor.close()
        db.close()


@app.route("/user/bookings")
@login_required
def my_bookings():
    if session.get("role") != "user":
        return redirect(url_for("admin_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                t.ticket_id,
                t.travel_date,
                t.seat_number,
                b.bus_number,
                r.route_name,
                r.start_point,
                r.end_point
            FROM Tickets t
            JOIN Buses b ON t.bus_id = b.bus_id
            JOIN Routes r ON b.route_id = r.route_id
            WHERE t.passenger_id = %s
            ORDER BY t.travel_date DESC, t.ticket_id DESC
        """, (session["passenger_id"],))

        bookings = cursor.fetchall()

        return render_template(
            "my_bookings.html",
            bookings=bookings
        )

    finally:
        cursor.close()
        db.close()


# 9. START SERVER — KEEP THIS AT THE BOTTOM

if __name__ == "__main__":
    app.run(debug=True)
