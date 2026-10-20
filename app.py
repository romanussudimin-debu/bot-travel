from datetime import datetime
from io import StringIO
import csv
import os
import secrets
import hmac
from dotenv import load_dotenv
import mysql.connector
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, Response, session, abort
)
load_dotenv()
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "FLASK_SECRET_KEY belum diatur. "
        "Jalankan perintah export FLASK_SECRET_KEY di Terminal."
    )

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "travel_db",
}


def db():
    return mysql.connector.connect(**DB_CONFIG)


def get_booking(booking_id):
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT * FROM booking WHERE id = %s",
            (booking_id,)
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def parse_booking(form):
    nama = form.get("nama_pelanggan", "").strip()
    paket = form.get("nama_paket", "").strip()

    try:
        tanggal = datetime.strptime(
            form.get("tanggal_keberangkatan", ""), "%Y-%m-%d"
        ).date()
        peserta = int(form.get("jumlah_peserta", ""))
        harga = int(form.get("harga_per_orang", ""))
    except (ValueError, TypeError):
        raise ValueError(
            "Tanggal, jumlah peserta, atau harga tidak valid."
        )

    if not nama or not paket:
        raise ValueError(
            "Nama pelanggan dan paket wisata wajib diisi."
        )

    if len(nama) > 100:
        raise ValueError("Nama pelanggan maksimal 100 karakter.")

    if len(paket) > 150:
        raise ValueError("Nama paket maksimal 150 karakter.")

    if peserta < 1 or peserta > 1000:
        raise ValueError(
            "Jumlah peserta harus antara 1 dan 1000 orang."
        )

    if harga < 0 or harga > 1_000_000_000:
        raise ValueError("Harga per orang tidak valid.")

    total = peserta * harga

    if total > 2_147_483_647:
        raise ValueError(
            "Total biaya terlalu besar untuk disimpan."
        )

    return nama, tanggal, paket, peserta, harga, total


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": csrf_token}


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        saved_token = session.get("_csrf_token", "")
        submitted_token = request.form.get("_csrf_token", "")

        if (
            not saved_token
            or not submitted_token
            or not hmac.compare_digest(
                saved_token, submitted_token
            )
        ):
            abort(400)


@app.errorhandler(400)
def bad_request(error):
    return (
        "Permintaan tidak valid atau token keamanan tidak cocok. "
        "Muat ulang halaman lalu coba lagi.",
        400,
    )


@app.errorhandler(404)
def not_found(error):
    return "Halaman atau booking tidak ditemukan.", 404


@app.errorhandler(mysql.connector.Error)
def database_error(error):
    app.logger.exception("Terjadi kesalahan database")
    return (
        "Terjadi gangguan saat mengakses database. "
        "Periksa layanan database lalu coba lagi.",
        503,
    )


@app.route("/", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        try:
            data = parse_booking(request.form)
            conn = db()
            cur = conn.cursor()

            try:
                cur.execute(
                    """
                    INSERT INTO booking (
                        nama_pelanggan,
                        tanggal_keberangkatan,
                        nama_paket,
                        jumlah_peserta,
                        harga_per_orang,
                        total_biaya
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    data,
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()

            flash("Booking berhasil disimpan.", "success")
            return redirect(url_for("dashboard"))

        except ValueError as error:
            flash(str(error), "error")

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    conditions = []
    params = []

    if q:
        conditions.append(
            "(nama_pelanggan LIKE %s "
            "OR nama_paket LIKE %s "
            "OR CAST(id AS CHAR) LIKE %s)"
        )
        params.extend([f"%{q}%"] * 3)

    if status in ("LUNAS", "BELUM LUNAS"):
        conditions.append("status_pembayaran = %s")
        params.append(status)

    sqlwhere = (
        " WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    conn = db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                COUNT(*) AS jumlah_booking,
                COALESCE(SUM(total_biaya), 0) AS total_pendapatan
            FROM booking
            """
        )
        stats = cur.fetchone()

        cur.execute(
            "SELECT COUNT(*) AS jumlah_lunas "
            "FROM booking WHERE status_pembayaran = 'LUNAS'"
        )
        stats["jumlah_lunas"] = cur.fetchone()["jumlah_lunas"]

        cur.execute(
            "SELECT * FROM booking"
            + sqlwhere
            + " ORDER BY tanggal_pemesanan DESC, id DESC",
            tuple(params),
        )
        bookings = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return render_template(
        "index.html",
        bookings=bookings,
        stats=stats,
        q=q,
        status_filter=status,
    )


@app.route("/booking/<int:booking_id>")
def detail_booking(booking_id):
    booking = get_booking(booking_id)

    if not booking:
        flash("Booking tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    return render_template("detail.html", booking=booking)


@app.route("/booking/<int:booking_id>/edit", methods=["GET", "POST"])
def edit_booking(booking_id):
    booking = get_booking(booking_id)

    if not booking:
        flash("Booking tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            data = parse_booking(request.form)
            conn = db()
            cur = conn.cursor()

            try:
                cur.execute(
                    """
                    UPDATE booking SET
                        nama_pelanggan = %s,
                        tanggal_keberangkatan = %s,
                        nama_paket = %s,
                        jumlah_peserta = %s,
                        harga_per_orang = %s,
                        total_biaya = %s
                    WHERE id = %s
                    """,
                    data + (booking_id,),
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()

            flash("Booking berhasil diperbarui.", "success")
            return redirect(
                url_for("detail_booking", booking_id=booking_id)
            )

        except ValueError as error:
            flash(str(error), "error")
            booking = {
                "id": booking_id,
                "nama_pelanggan": request.form.get(
                    "nama_pelanggan", ""
                ),
                "tanggal_keberangkatan": request.form.get(
                    "tanggal_keberangkatan", ""
                ),
                "nama_paket": request.form.get("nama_paket", ""),
                "jumlah_peserta": request.form.get(
                    "jumlah_peserta", 1
                ),
                "harga_per_orang": request.form.get(
                    "harga_per_orang", 0
                ),
            }

    return render_template("edit.html", booking=booking)


@app.route("/booking/<int:booking_id>/pembayaran", methods=["POST"])
def ubah_pembayaran(booking_id):
    status = request.form.get("status_pembayaran", "")

    if status not in ("LUNAS", "BELUM LUNAS"):
        flash("Status pembayaran tidak valid.", "error")
        return redirect(url_for("dashboard"))

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE booking SET status_pembayaran = %s WHERE id = %s",
            (status, booking_id),
        )
        conn.commit()

        if cur.rowcount:
            flash(
                "Status pembayaran berhasil diperbarui.",
                "success",
            )
        else:
            flash(
                "Booking tidak ditemukan atau status tidak berubah.",
                "error",
            )
    finally:
        cur.close()
        conn.close()

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/booking/<int:booking_id>/hapus", methods=["POST"])
def hapus_booking(booking_id):
    conn = db()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM booking WHERE id = %s",
            (booking_id,),
        )
        conn.commit()

        if cur.rowcount:
            flash("Booking berhasil dihapus.", "success")
        else:
            flash("Booking tidak ditemukan.", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("dashboard"))


@app.route("/laporan.csv")
def laporan_csv():
    mulai = request.args.get("mulai", "").strip()
    sampai = request.args.get("sampai", "").strip()

    conditions = []
    params = []

    try:
        if mulai:
            datetime.strptime(mulai, "%Y-%m-%d")
            conditions.append("tanggal_keberangkatan >= %s")
            params.append(mulai)

        if sampai:
            datetime.strptime(sampai, "%Y-%m-%d")
            conditions.append("tanggal_keberangkatan <= %s")
            params.append(sampai)

        if mulai and sampai and mulai > sampai:
            raise ValueError

    except ValueError:
        flash("Rentang tanggal laporan tidak valid.", "error")
        return redirect(url_for("dashboard"))

    sqlwhere = (
        " WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    conn = db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            """
            SELECT
                id,
                nama_pelanggan,
                tanggal_keberangkatan,
                nama_paket,
                jumlah_peserta,
                harga_per_orang,
                total_biaya,
                status_pembayaran,
                tanggal_pemesanan
            FROM booking
            """
            + sqlwhere
            + " ORDER BY tanggal_keberangkatan, id",
            tuple(params),
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)

    writer.writerow([
        "ID Booking",
        "Nama Pelanggan",
        "Tanggal Keberangkatan",
        "Nama Paket",
        "Jumlah Peserta",
        "Harga per Orang",
        "Total Biaya",
        "Status Pembayaran",
        "Tanggal Pemesanan",
    ])

    for row in rows:
        writer.writerow([
            row["id"],
            row["nama_pelanggan"],
            row["tanggal_keberangkatan"],
            row["nama_paket"],
            row["jumlah_peserta"],
            row["harga_per_orang"],
            row["total_biaya"],
            row["status_pembayaran"],
            row["tanggal_pemesanan"],
        ])

    filename = (
        f"laporan_booking_{mulai or 'awal'}_{sampai or 'akhir'}.csv"
        if (mulai or sampai)
        else "laporan_booking.csv"
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


if __name__ == "__main__":
    app.run(debug=False)
