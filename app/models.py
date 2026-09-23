from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="user")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    bookings = db.relationship("Booking", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Station(db.Model):
    __tablename__ = "stations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)

    departures = db.relationship(
        "Train",
        foreign_keys="Train.source_station_id",
        back_populates="source_station",
    )
    arrivals = db.relationship(
        "Train",
        foreign_keys="Train.destination_station_id",
        back_populates="destination_station",
    )

    def label(self):
        return f"{self.name} ({self.code})"


class Train(db.Model):
    __tablename__ = "trains"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    source_station_id = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=False)
    destination_station_id = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    fare = db.Column(db.Numeric(10, 2), nullable=False)
    seats_total = db.Column(db.Integer, nullable=False, default=120)
    seats_available = db.Column(db.Integer, nullable=False, default=120)
    runs_on = db.Column(db.String(80), nullable=False, default="Daily")
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    source_station = db.relationship(
        "Station",
        foreign_keys=[source_station_id],
        back_populates="departures",
    )
    destination_station = db.relationship(
        "Station",
        foreign_keys=[destination_station_id],
        back_populates="arrivals",
    )
    bookings = db.relationship("Booking", back_populates="train")
    availability_snapshots = db.relationship("AvailabilitySnapshot", back_populates="train")

    @property
    def duration_label(self):
        hours, minutes = divmod(self.duration_minutes, 60)
        return f"{hours}h {minutes:02d}m"

    @property
    def availability_ratio(self):
        if not self.seats_total:
            return 0
        return self.seats_available / self.seats_total


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    pnr = db.Column(db.String(16), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    train_id = db.Column(db.Integer, db.ForeignKey("trains.id"), nullable=False)
    travel_date = db.Column(db.Date, nullable=False, index=True)
    passenger_count = db.Column(db.Integer, nullable=False)
    total_fare = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="CONFIRMED")
    recommendation_reason = db.Column(db.Text)
    qr_token = db.Column(db.String(96), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    canceled_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="bookings")
    train = db.relationship("Train", back_populates="bookings")
    passengers = db.relationship("Passenger", back_populates="booking", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
    history = db.relationship(
        "BookingHistory",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingHistory.created_at",
    )


class Passenger(db.Model):
    __tablename__ = "passengers"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    seat_number = db.Column(db.String(20), nullable=False)

    booking = db.relationship("Booking", back_populates="passengers")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    provider = db.Column(db.String(60), nullable=False, default="DemoPay")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="PAID")
    transaction_ref = db.Column(db.String(64), nullable=False)
    paid_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    booking = db.relationship("Booking", back_populates="payments")


class BookingHistory(db.Model):
    __tablename__ = "booking_history"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    booking = db.relationship("Booking", back_populates="history")


class AvailabilitySnapshot(db.Model):
    __tablename__ = "availability_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column(db.Integer, db.ForeignKey("trains.id"), nullable=False)
    travel_date = db.Column(db.Date, nullable=False, index=True)
    seats_available = db.Column(db.Integer, nullable=False)
    captured_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    train = db.relationship("Train", back_populates="availability_snapshots")
