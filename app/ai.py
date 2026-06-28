from datetime import date

from .models import AvailabilitySnapshot, Booking


PREFERENCE_WEIGHTS = {
    "balanced": {"time": 0.34, "fare": 0.28, "availability": 0.30, "comfort": 0.08},
    "fastest": {"time": 0.58, "fare": 0.16, "availability": 0.18, "comfort": 0.08},
    "cheapest": {"time": 0.18, "fare": 0.55, "availability": 0.20, "comfort": 0.07},
    "availability": {"time": 0.16, "fare": 0.16, "availability": 0.60, "comfort": 0.08},
}


def normalize(value, low, high, inverse=False):
    if high == low:
        return 1.0
    score = (value - low) / (high - low)
    score = max(0.0, min(1.0, score))
    return 1.0 - score if inverse else score


def predict_availability(train, travel_date, passenger_count=1):
    confirmed = Booking.query.filter_by(
        train_id=train.id,
        travel_date=travel_date,
        status="CONFIRMED",
    ).count()
    days_until = max((travel_date - date.today()).days, 0)
    projected_seats = ml_projected_seats(train, travel_date)
    method = "ml"

    if projected_seats is None:
        method = "heuristic"
        urgency_pressure = max(0, 10 - days_until) * 0.025
        demand_pressure = confirmed / max(train.seats_total, 1)
        projected_seats = int(
            train.seats_available - (urgency_pressure + demand_pressure) * train.seats_total * 0.4
        )

    projected_seats = max(0, min(train.seats_total, projected_seats))

    if projected_seats >= passenger_count * 3 and projected_seats / max(train.seats_total, 1) >= 0.35:
        label = "High"
    elif projected_seats >= passenger_count:
        label = "Medium"
    else:
        label = "Low"

    return {
        "label": label,
        "projected_seats": projected_seats,
        "booked_today": confirmed,
        "method": method,
    }


def ml_projected_seats(train, travel_date):
    snapshots = (
        AvailabilitySnapshot.query.filter_by(train_id=train.id)
        .order_by(AvailabilitySnapshot.travel_date.asc())
        .all()
    )
    if len(snapshots) < 2:
        return None

    try:
        import numpy as np
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return None

    base_day = date.today()
    x_values = np.array([(snapshot.travel_date - base_day).days for snapshot in snapshots]).reshape(-1, 1)
    y_values = np.array([snapshot.seats_available for snapshot in snapshots])
    target = np.array([[(travel_date - base_day).days]])
    model = LinearRegression()
    model.fit(x_values, y_values)
    return int(round(model.predict(target)[0]))


def recommend_trains(trains, travel_date, preference="balanced", passenger_count=1):
    trains = list(trains)
    if not trains:
        return []

    weights = PREFERENCE_WEIGHTS.get(preference, PREFERENCE_WEIGHTS["balanced"])
    min_duration = min(train.duration_minutes for train in trains)
    max_duration = max(train.duration_minutes for train in trains)
    min_fare = min(float(train.fare) for train in trains)
    max_fare = max(float(train.fare) for train in trains)

    scored = []
    for train in trains:
        time_score = normalize(train.duration_minutes, min_duration, max_duration, inverse=True)
        fare_score = normalize(float(train.fare), min_fare, max_fare, inverse=True)
        availability_score = min(1.0, train.seats_available / max(train.seats_total, 1))
        comfort_score = 1.0 if train.runs_on.lower() == "daily" else 0.72
        trend = predict_availability(train, travel_date, passenger_count)

        score = (
            time_score * weights["time"]
            + fare_score * weights["fare"]
            + availability_score * weights["availability"]
            + comfort_score * weights["comfort"]
        )
        if train.seats_available < passenger_count:
            score *= 0.45
        if trend["label"] == "Low":
            score *= 0.8

        reasons = []
        if time_score >= 0.72:
            reasons.append("shorter travel time")
        if fare_score >= 0.72:
            reasons.append("lower fare")
        if availability_score >= 0.45:
            reasons.append("healthy seat availability")
        if trend["label"] == "High":
            reasons.append("strong availability trend")
        if not reasons:
            reasons.append("best overall match for the selected route")

        scored.append(
            {
                "train": train,
                "score": round(score * 100, 1),
                "trend": trend,
                "reasons": reasons,
                "is_recommended": False,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    if scored:
        scored[0]["is_recommended"] = True
    return scored


def explain_recommendation(item):
    reasons = ", ".join(item["reasons"])
    return f"AI score {item['score']}/100 based on {reasons}."


def chatbot_reply(message):
    text = (message or "").strip().lower()
    if not text:
        return "Ask me about fares, PNR, cancellations, availability, or how to book a train."
    if "pnr" in text:
        return "Use the PNR status box with your 10-character PNR to check confirmation, passengers, train, and travel date."
    if "cancel" in text or "refund" in text:
        return "Open My Bookings, choose a confirmed ticket, and select Cancel. Demo payments are marked refundable in the booking history."
    if "book" in text or "ticket" in text:
        return "Search by route and date, review the AI recommendation, then open Book to enter passenger details and generate your PDF ticket."
    if "fare" in text or "price" in text:
        return "Fare is calculated from the train base fare, passenger count, and a small demand factor for near-date travel."
    if "available" in text or "seat" in text:
        return "Availability is shown live from the train record and adjusted after every booking or cancellation."
    if "admin" in text:
        return "Admins can manage stations, trains, fares, seat availability, bookings, and analytics from the dashboard."
    return "I can help with booking steps, PNR status, cancellations, fares, seat availability, and route suggestions."
