from datetime import date, time, timedelta

from .extensions import db
from .models import AvailabilitySnapshot, Station, Train, User


def init_db(reset=False):
    if reset:
        db.drop_all()

    db.create_all()

    if Station.query.first() and Train.query.first() and User.query.first():
        return

    seed_stations()
    seed_trains()
    seed_users()
    seed_availability()
    db.session.commit()


def seed_users():
    if not User.query.filter_by(email="admin@example.com").first():
        admin = User(name="Admin User", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(email="demo@example.com").first():
        demo = User(name="Demo Traveller", email="demo@example.com", role="user")
        demo.set_password("demo123")
        db.session.add(demo)


def seed_stations():
    stations = [
        ("NDLS", "New Delhi", "Delhi"),
        ("CSMT", "Chhatrapati Shivaji Maharaj Terminus", "Mumbai"),
        ("HWH", "Howrah Junction", "Kolkata"),
        ("MAS", "MGR Chennai Central", "Chennai"),
        ("SBC", "KSR Bengaluru", "Bengaluru"),
        ("ADI", "Ahmedabad Junction", "Ahmedabad"),
        ("PNBE", "Patna Junction", "Patna"),
        ("BPL", "Bhopal Junction", "Bhopal"),
    ]
    for code, name, city in stations:
        if not Station.query.filter_by(code=code).first():
            db.session.add(Station(code=code, name=name, city=city))
    db.session.flush()


def station(code):
    return Station.query.filter_by(code=code).one()


def seed_trains():
    trains = [
        ("12952", "Mumbai Rajdhani Express", "NDLS", "CSMT", time(16, 55), time(8, 35), 940, 3150, 150, 47, "Daily"),
        ("22222", "CSMT Duronto Express", "NDLS", "CSMT", time(23, 25), time(16, 15), 1010, 2480, 120, 19, "Mon Wed Fri"),
        ("12260", "Sealdah Duronto Express", "NDLS", "HWH", time(19, 40), time(12, 45), 1025, 2620, 135, 71, "Daily"),
        ("12302", "Howrah Rajdhani Express", "NDLS", "HWH", time(16, 50), time(9, 55), 1025, 2890, 130, 28, "Daily"),
        ("12628", "Karnataka Express", "NDLS", "SBC", time(20, 20), time(13, 40), 2480, 1850, 180, 88, "Daily"),
        ("22692", "Bengaluru Rajdhani Express", "NDLS", "SBC", time(20, 45), time(6, 40), 2035, 3420, 115, 16, "Tue Thu Sat"),
        ("12622", "Tamil Nadu Express", "NDLS", "MAS", time(21, 5), time(7, 10), 2045, 2180, 160, 63, "Daily"),
        ("12958", "Swarna Jayanti Rajdhani", "NDLS", "ADI", time(19, 55), time(8, 20), 745, 2310, 110, 35, "Daily"),
        ("19412", "Daulatpur Chowk Express", "ADI", "NDLS", time(9, 40), time(21, 10), 690, 980, 170, 102, "Daily"),
        ("12156", "Shaan-e-Bhopal Express", "NDLS", "BPL", time(20, 40), time(7, 20), 640, 920, 150, 54, "Daily"),
        ("12310", "Rajendra Nagar Tejas", "NDLS", "PNBE", time(17, 10), time(6, 45), 815, 1760, 130, 44, "Daily"),
        ("22691", "Rajdhani Return", "SBC", "NDLS", time(20, 0), time(5, 55), 2035, 3420, 115, 26, "Mon Wed Fri"),
    ]
    for number, name, src, dst, dep, arr, duration, fare, total, available, runs_on in trains:
        if Train.query.filter_by(number=number).first():
            continue
        db.session.add(
            Train(
                number=number,
                name=name,
                source_station=station(src),
                destination_station=station(dst),
                departure_time=dep,
                arrival_time=arr,
                duration_minutes=duration,
                fare=fare,
                seats_total=total,
                seats_available=available,
                runs_on=runs_on,
            )
        )
    db.session.flush()


def seed_availability():
    if AvailabilitySnapshot.query.first():
        return
    for train in Train.query.all():
        for offset, factor in [(1, 0.92), (3, 0.78), (7, 0.64), (14, 0.48)]:
            db.session.add(
                AvailabilitySnapshot(
                    train=train,
                    travel_date=date.today() + timedelta(days=offset),
                    seats_available=max(0, int(train.seats_available * factor)),
                )
            )
