from io import BytesIO


def generate_ticket_pdf(booking):
    try:
        import qrcode
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "PDF ticket generation requires reportlab and qrcode. Install requirements.txt first."
        ) from exc

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    qr_payload = {
        "pnr": booking.pnr,
        "train": booking.train.number,
        "travel_date": booking.travel_date.isoformat(),
        "token": booking.qr_token,
    }
    qr_img = qrcode.make(str(qr_payload))
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.rect(0, height - 42 * mm, width, 42 * mm, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(22 * mm, height - 20 * mm, "Train Ticket")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(22 * mm, height - 28 * mm, "AI-Powered Train Ticket Booking Assistant")

    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(22 * mm, height - 58 * mm, f"PNR {booking.pnr}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(22 * mm, height - 65 * mm, f"Status: {booking.status}")
    pdf.drawString(22 * mm, height - 72 * mm, f"Issued to: {booking.user.name} ({booking.user.email})")

    train = booking.train
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(22 * mm, height - 90 * mm, f"{train.number} - {train.name}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        22 * mm,
        height - 98 * mm,
        f"{train.source_station.label()} to {train.destination_station.label()}",
    )
    pdf.drawString(
        22 * mm,
        height - 106 * mm,
        f"Travel date: {booking.travel_date.strftime('%d %b %Y')}",
    )
    pdf.drawString(
        22 * mm,
        height - 114 * mm,
        f"Departure: {train.departure_time.strftime('%H:%M')}  Arrival: {train.arrival_time.strftime('%H:%M')}  Duration: {train.duration_label}",
    )

    pdf.drawImage(ImageReader(qr_buffer), width - 62 * mm, height - 92 * mm, 36 * mm, 36 * mm)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - 24 * mm, height - 96 * mm, "Scan to verify ticket")

    y = height - 136 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(22 * mm, y, "Passengers")
    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(22 * mm, y, "Name")
    pdf.drawString(92 * mm, y, "Age")
    pdf.drawString(112 * mm, y, "Gender")
    pdf.drawString(142 * mm, y, "Seat")
    pdf.line(22 * mm, y - 2 * mm, width - 22 * mm, y - 2 * mm)

    pdf.setFont("Helvetica", 9)
    for passenger in booking.passengers:
        y -= 8 * mm
        pdf.drawString(22 * mm, y, passenger.name[:36])
        pdf.drawString(92 * mm, y, str(passenger.age))
        pdf.drawString(112 * mm, y, passenger.gender)
        pdf.drawString(142 * mm, y, passenger.seat_number)

    y -= 16 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(22 * mm, y, f"Total fare: Rs. {float(booking.total_fare):,.2f}")
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(22 * mm, y, "Carry a valid photo ID during travel. This is a project demo ticket.")

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(22 * mm, 18 * mm, f"Verification token: {booking.qr_token}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

