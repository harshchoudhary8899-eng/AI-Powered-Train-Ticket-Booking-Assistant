from datetime import date, datetime
from decimal import Decimal
from functools import wraps
import secrets
import string

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_

from .ai import chatbot_reply, explain_recommendation, recommend_trains
from .extensions import db
from .models import Booking, BookingHistory, Passenger, Payment, Station, Train, User, utcnow
from .tickets import generate_ticket_pdf

main_bp = Blueprint("main", __name__)


@main_bp.app_template_filter("currency")
def currency(value):
    return f"Rs. {float(value or 0):,.2f}"


@main_bp.app_context_processor
def inject_common_values():
    return {"today_iso": date.today().isoformat()}


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access is required for that page.", "danger")
            return redirect(url_for("main.index"))
        return view(*args, **kwargs)

    return wrapped


def parse_iso_date(raw_value, fallback=None):
    if not raw_value:
        return fallback
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


def parse_time(raw_value):
    return datetime.strptime(raw_value, "%H:%M").time()


def generate_pnr():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        pnr = "".join(secrets.choice(alphabet) for _ in range(10))
        if not Booking.query.filter_by(pnr=pnr).first():
            return pnr


def calculate_fare(train, passenger_count, travel_date):
    base = Decimal(train.fare) * Decimal(passenger_count)
    days_until = max((travel_date - date.today()).days, 0)
    demand_factor = Decimal("1.00")
    if days_until <= 1:
        demand_factor = Decimal("1.12")
    elif days_until <= 3:
        demand_factor = Decimal("1.07")
    return (base * demand_factor).quantize(Decimal("0.01"))


def can_view_booking(booking):
    return current_user.is_authenticated and (current_user.is_admin or booking.user_id == current_user.id)


@main_bp.route("/")
def index():
    stations = Station.query.order_by(Station.city.asc(), Station.name.asc()).all()
    popular_trains = Train.query.filter_by(status="ACTIVE").order_by(Train.seats_available.desc()).limit(5).all()
    recent_bookings = []
    if current_user.is_authenticated:
        recent_bookings = (
            Booking.query.filter_by(user_id=current_user.id)
            .order_by(Booking.created_at.desc())
            .limit(3)
            .all()
        )
    return render_template(
        "index.html",
        stations=stations,
        popular_trains=popular_trains,
        recent_bookings=recent_bookings,
    )


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Use at least 6 characters for the password.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome. Your account is ready.", "success")
            return redirect(url_for("main.index"))

    return render_template("auth/register.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            flash("Signed in successfully.", "success")
            return redirect(request.args.get("next") or url_for("main.index"))
        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        return redirect(
            url_for(
                "main.search",
                source_id=request.form.get("source_id"),
                destination_id=request.form.get("destination_id"),
                travel_date=request.form.get("travel_date"),
                passengers=request.form.get("passengers", 1),
                preference=request.form.get("preference", "balanced"),
            )
        )

    stations = Station.query.order_by(Station.city.asc(), Station.name.asc()).all()
    source_id = request.args.get("source_id", type=int)
    destination_id = request.args.get("destination_id", type=int)
    travel_date = parse_iso_date(request.args.get("travel_date"), date.today())
    passenger_count = max(1, min(request.args.get("passengers", 1, type=int), 6))
    preference = request.args.get("preference", "balanced")

    results = []
    alternate_results = []
    route_searched = source_id and destination_id

    if route_searched:
        if source_id == destination_id:
            flash("Source and destination must be different.", "warning")
        else:
            direct_trains = (
                Train.query.filter_by(
                    source_station_id=source_id,
                    destination_station_id=destination_id,
                    status="ACTIVE",
                )
                .order_by(Train.departure_time.asc())
                .all()
            )
            results = recommend_trains(direct_trains, travel_date, preference, passenger_count)

            needs_alternates = not results or all(
                item["train"].seats_available < passenger_count for item in results
            )
            if needs_alternates:
                alternate_trains = (
                    Train.query.filter(
                        Train.status == "ACTIVE",
                        Train.id.notin_([item["train"].id for item in results] or [0]),
                        or_(
                            Train.source_station_id == source_id,
                            Train.destination_station_id == destination_id,
                        ),
                    )
                    .order_by(Train.seats_available.desc())
                    .limit(6)
                    .all()
                )
                alternate_results = recommend_trains(
                    alternate_trains,
                    travel_date,
                    preference,
                    passenger_count,
                )

    return render_template(
        "search.html",
        stations=stations,
        results=results,
        alternate_results=alternate_results,
        source_id=source_id,
        destination_id=destination_id,
        selected_date=travel_date.isoformat(),
        passenger_count=passenger_count,
        preference=preference,
        route_searched=route_searched,
    )


@main_bp.route("/book/<int:train_id>", methods=["GET", "POST"])
@login_required
def book_train(train_id):
    train = Train.query.get_or_404(train_id)
    travel_date = parse_iso_date(request.values.get("travel_date"), date.today())
    passenger_count = max(1, min(request.values.get("passengers", 1, type=int), 6))
    recommendation_reason = request.values.get("recommendation_reason", "")

    if request.method == "POST":
        passenger_count = max(1, min(request.form.get("passenger_count", 1, type=int), 6))
        travel_date = parse_iso_date(request.form.get("travel_date"), date.today())
        names = [value.strip() for value in request.form.getlist("passenger_name")]
        ages = request.form.getlist("passenger_age")
        genders = request.form.getlist("passenger_gender")

        if train.seats_available < passenger_count:
            flash("Not enough seats are available for that train.", "danger")
        elif len(names) != passenger_count or any(not name for name in names):
            flash("Passenger names are required.", "danger")
        else:
            booking = Booking(
                pnr=generate_pnr(),
                user=current_user,
                train=train,
                travel_date=travel_date,
                passenger_count=passenger_count,
                total_fare=calculate_fare(train, passenger_count, travel_date),
                recommendation_reason=request.form.get("recommendation_reason") or "",
                qr_token=secrets.token_urlsafe(32),
            )
            db.session.add(booking)
            db.session.flush()

            first_seat_index = train.seats_total - train.seats_available + 1
            for index in range(passenger_count):
                try:
                    age = max(1, min(int(ages[index]), 120))
                except (ValueError, IndexError):
                    age = 18
                gender = genders[index] if index < len(genders) and genders[index] else "Other"
                passenger = Passenger(
                    booking=booking,
                    name=names[index],
                    age=age,
                    gender=gender,
                    seat_number=f"{train.number[-2:]}-{first_seat_index + index:03d}",
                )
                db.session.add(passenger)

            train.seats_available -= passenger_count
            db.session.add(
                Payment(
                    booking=booking,
                    amount=booking.total_fare,
                    transaction_ref=f"PAY-{secrets.token_hex(6).upper()}",
                )
            )
            db.session.add(
                BookingHistory(
                    booking=booking,
                    action="CREATED",
                    notes=f"Ticket confirmed for {passenger_count} passenger(s).",
                )
            )
            db.session.commit()
            flash(f"Booking confirmed. Your PNR is {booking.pnr}.", "success")
            return redirect(url_for("main.booking_detail", booking_id=booking.id))

    total_fare = calculate_fare(train, passenger_count, travel_date)
    return render_template(
        "book.html",
        train=train,
        travel_date=travel_date,
        passenger_count=passenger_count,
        total_fare=total_fare,
        recommendation_reason=recommendation_reason,
    )


@main_bp.route("/bookings")
@login_required
def bookings():
    user_bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("bookings.html", bookings=user_bookings)


@main_bp.route("/bookings/<int:booking_id>")
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not can_view_booking(booking):
        flash("You do not have access to that booking.", "danger")
        return redirect(url_for("main.bookings"))
    return render_template("booking_detail.html", booking=booking)


@main_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not can_view_booking(booking):
        flash("You do not have access to that booking.", "danger")
        return redirect(url_for("main.bookings"))
    if booking.status != "CONFIRMED":
        flash("Only confirmed tickets can be cancelled.", "warning")
        return redirect(url_for("main.booking_detail", booking_id=booking.id))

    booking.status = "CANCELED"
    booking.canceled_at = utcnow()
    booking.train.seats_available = min(
        booking.train.seats_total,
        booking.train.seats_available + booking.passenger_count,
    )
    for payment in booking.payments:
        payment.status = "REFUNDED"
    db.session.add(
        BookingHistory(
            booking=booking,
            action="CANCELED",
            notes="Ticket cancelled and demo payment marked refunded.",
        )
    )
    db.session.commit()
    flash("Booking cancelled successfully.", "info")
    return redirect(url_for("main.booking_detail", booking_id=booking.id))


@main_bp.route("/bookings/<int:booking_id>/ticket.pdf")
@login_required
def ticket_pdf(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if not can_view_booking(booking):
        flash("You do not have access to that ticket.", "danger")
        return redirect(url_for("main.bookings"))
    try:
        pdf_buffer = generate_ticket_pdf(booking)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("main.booking_detail", booking_id=booking.id))

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"ticket-{booking.pnr}.pdf",
    )


@main_bp.route("/pnr", methods=["GET", "POST"])
def pnr_status():
    pnr = request.values.get("pnr", "").strip().upper()
    booking = None
    if pnr:
        booking = Booking.query.filter_by(pnr=pnr).first()
        if not booking:
            flash("No booking found for that PNR.", "warning")
    return render_template("pnr.html", pnr=pnr, booking=booking)


@main_bp.route("/api/pnr/<pnr>")
def api_pnr_status(pnr):
    booking = Booking.query.filter_by(pnr=pnr.strip().upper()).first_or_404()
    return jsonify(
        {
            "pnr": booking.pnr,
            "status": booking.status,
            "train": f"{booking.train.number} - {booking.train.name}",
            "route": f"{booking.train.source_station.code} to {booking.train.destination_station.code}",
            "travel_date": booking.travel_date.isoformat(),
            "passengers": [
                {
                    "name": passenger.name,
                    "seat": passenger.seat_number,
                }
                for passenger in booking.passengers
            ],
        }
    )


@main_bp.route("/chat")
def chat():
    return render_template("chat.html")


@main_bp.route("/api/chat", methods=["POST"])
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") or request.form.get("message", "")
    return jsonify({"reply": chatbot_reply(message)})


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    revenue = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status == "PAID")
        .scalar()
    )
    stats = {
        "users": User.query.count(),
        "trains": Train.query.count(),
        "confirmed": Booking.query.filter_by(status="CONFIRMED").count(),
        "canceled": Booking.query.filter_by(status="CANCELED").count(),
        "revenue": revenue,
    }
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(6).all()
    low_inventory = (
        Train.query.filter(Train.status == "ACTIVE")
        .order_by((Train.seats_available * 1.0 / Train.seats_total).asc())
        .limit(6)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_bookings=recent_bookings,
        low_inventory=low_inventory,
    )


@main_bp.route("/admin/stations", methods=["GET", "POST"])
@admin_required
def admin_stations():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        city = request.form.get("city", "").strip()
        if not code or not name or not city:
            flash("Station code, name, and city are required.", "danger")
        elif Station.query.filter_by(code=code).first():
            flash("A station with that code already exists.", "warning")
        else:
            db.session.add(Station(code=code, name=name, city=city))
            db.session.commit()
            flash("Station added.", "success")
            return redirect(url_for("main.admin_stations"))

    stations = Station.query.order_by(Station.city.asc(), Station.name.asc()).all()
    return render_template("admin/stations.html", stations=stations)


@main_bp.route("/admin/trains", methods=["GET", "POST"])
@admin_required
def admin_trains():
    stations = Station.query.order_by(Station.city.asc(), Station.name.asc()).all()
    if request.method == "POST":
        try:
            train = Train(
                number=request.form.get("number", "").strip(),
                name=request.form.get("name", "").strip(),
                source_station_id=request.form.get("source_station_id", type=int),
                destination_station_id=request.form.get("destination_station_id", type=int),
                departure_time=parse_time(request.form.get("departure_time", "00:00")),
                arrival_time=parse_time(request.form.get("arrival_time", "00:00")),
                duration_minutes=request.form.get("duration_minutes", type=int),
                fare=Decimal(request.form.get("fare", "0")),
                seats_total=request.form.get("seats_total", type=int),
                seats_available=request.form.get("seats_available", type=int),
                runs_on=request.form.get("runs_on", "Daily").strip() or "Daily",
                status=request.form.get("status", "ACTIVE"),
            )
            if not train.number or not train.name or train.source_station_id == train.destination_station_id:
                raise ValueError("Train number, name, and a valid route are required.")
            if Train.query.filter_by(number=train.number).first():
                raise ValueError("A train with that number already exists.")
            db.session.add(train)
            db.session.commit()
            flash("Train added.", "success")
            return redirect(url_for("main.admin_trains"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Could not add train: {exc}", "danger")

    trains = Train.query.order_by(Train.number.asc()).all()
    return render_template("admin/trains.html", trains=trains, stations=stations)


@main_bp.route("/admin/trains/<int:train_id>/update", methods=["POST"])
@admin_required
def admin_update_train(train_id):
    train = Train.query.get_or_404(train_id)
    try:
        train.fare = Decimal(request.form.get("fare", train.fare))
        train.seats_total = request.form.get("seats_total", train.seats_total, type=int)
        train.seats_available = request.form.get("seats_available", train.seats_available, type=int)
        train.runs_on = request.form.get("runs_on", train.runs_on).strip() or train.runs_on
        train.status = request.form.get("status", train.status)
        train.seats_available = max(0, min(train.seats_available, train.seats_total))
        db.session.commit()
        flash("Train updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not update train: {exc}", "danger")
    return redirect(url_for("main.admin_trains"))


@main_bp.route("/admin/bookings")
@admin_required
def admin_bookings():
    status = request.args.get("status", "")
    query = Booking.query.order_by(Booking.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    return render_template("admin/bookings.html", bookings=query.all(), status=status)


@main_bp.route("/recommendation-reason")
def recommendation_reason():
    train_id = request.args.get("train_id", type=int)
    travel_date = parse_iso_date(request.args.get("travel_date"), date.today())
    preference = request.args.get("preference", "balanced")
    passengers = request.args.get("passengers", 1, type=int)
    train = Train.query.get_or_404(train_id)
    item = recommend_trains([train], travel_date, preference, passengers)[0]
    return jsonify({"reason": explain_recommendation(item)})

