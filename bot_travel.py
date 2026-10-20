
from datetime import datetime
import mysql.connector


# ==========================================
# KONFIGURASI BOT TRAVEL
# ==========================================

NAMA_PAKET = "Wisata Komodo 2 Hari 1 Malam"
HARGA_PER_ORANG = 1500000

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "travel_db"
}


# ==========================================
# FUNGSI DATABASE
# ==========================================

def hubungkan_database():
    """Menghubungkan Python dengan MariaDB."""
    return mysql.connector.connect(**DB_CONFIG)


# ==========================================
# FUNGSI TAMPILAN
# ==========================================

def format_rupiah(angka):
    return f"Rp{angka:,}".replace(",", ".")


def tampilkan_menu():
    print("\n===================================")
    print("       BOT TRAVEL LABUAN BAJO")
    print("===================================")
    print("Ketik: halo, harga, booking, daftar, atau keluar.")


def tampilkan_harga():
    print("\n--- INFORMASI PAKET WISATA ---")
    print("Paket:", NAMA_PAKET)
    print("Durasi: 2 Hari 1 Malam")
    print("Harga per orang:", format_rupiah(HARGA_PER_ORANG))


# ==========================================
# FUNGSI MENYIMPAN BOOKING KE DATABASE
# ==========================================

def simpan_booking(nama, tanggal, peserta, total):
    koneksi = None
    cursor = None

    try:
        koneksi = hubungkan_database()
        cursor = koneksi.cursor()

        query = """
            INSERT INTO booking (
                nama_pelanggan,
                tanggal_keberangkatan,
                nama_paket,
                jumlah_peserta,
                harga_per_orang,
                total_biaya
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        tanggal_database = datetime.strptime(
            tanggal, "%d-%m-%Y"
        ).date()

        data_booking = (
            nama,
            tanggal_database,
            NAMA_PAKET,
            peserta,
            HARGA_PER_ORANG,
            total
        )

        cursor.execute(query, data_booking)
        koneksi.commit()

        print("\nBot: Booking berhasil disimpan ke database!")
        print("Bot: Nomor booking:", cursor.lastrowid)

    except mysql.connector.Error as error:
        if koneksi is not None:
            koneksi.rollback()

        print("\nBot: Booking gagal disimpan.")
        print("Detail error:", error)

    except ValueError:
        print("Bot: Format tanggal tidak valid.")

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()


# ==========================================
# FUNGSI PROSES BOOKING
# ==========================================

def proses_booking():
    print("\n--- FORM BOOKING WISATA ---")
    print("Ketik 'batal' untuk membatalkan booking.")

    nama = input("Bot: Siapa nama Anda? ").strip()

    if nama.lower() == "batal":
        print("Bot: Booking dibatalkan.")
        return

    if not nama:
        print("Bot: Nama tidak boleh kosong.")
        return

    tanggal_input = input(
        "Bot: Tanggal keberangkatan (DD-MM-YYYY)? "
    ).strip()

    if tanggal_input.lower() == "batal":
        print("Bot: Booking dibatalkan.")
        return

    try:
        tanggal_valid = datetime.strptime(
            tanggal_input, "%d-%m-%Y"
        )
        tanggal = tanggal_valid.strftime("%d-%m-%Y")

    except ValueError:
        print("Bot: Format tanggal salah atau tidak valid.")
        print("Bot: Contoh format yang benar: 24-11-2026")
        return

    peserta = input("Bot: Berapa jumlah peserta? ").strip()

    if peserta.lower() == "batal":
        print("Bot: Booking dibatalkan.")
        return

    if not peserta.isdigit() or int(peserta) <= 0:
        print("Bot: Jumlah peserta harus angka lebih dari 0.")
        return

    jumlah_peserta = int(peserta)
    total = jumlah_peserta * HARGA_PER_ORANG

    print("\n--- RINGKASAN BOOKING ---")
    print("Nama:", nama)
    print("Tanggal keberangkatan:", tanggal)
    print("Nama paket:", NAMA_PAKET)
    print("Jumlah peserta:", jumlah_peserta)
    print("Harga per orang:", format_rupiah(HARGA_PER_ORANG))
    print("Total biaya:", format_rupiah(total))

    konfirmasi = input(
        "Bot: Simpan booking ini? (ya/tidak): "
    ).strip().lower()

    if konfirmasi == "ya":
        simpan_booking(
            nama, tanggal, jumlah_peserta, total
        )
    else:
        print("Bot: Booking tidak disimpan.")


# ==========================================
# FUNGSI MENAMPILKAN BOOKING DARI DATABASE
# ==========================================

def tampilkan_daftar_booking():
    koneksi = None
    cursor = None

    print("\n--- DAFTAR BOOKING DARI DATABASE ---")

    try:
        koneksi = hubungkan_database()
        cursor = koneksi.cursor()

        query = """
            SELECT
                id,
                nama_pelanggan,
                tanggal_keberangkatan,
                nama_paket,
                jumlah_peserta,
                harga_per_orang,
                total_biaya,
                tanggal_pemesanan
            FROM booking
            ORDER BY id DESC
        """

        cursor.execute(query)
        daftar = cursor.fetchall()

        if not daftar:
            print("Bot: Belum ada data booking.")
            return

        for data in daftar:
            (
                booking_id,
                nama,
                tanggal,
                paket,
                peserta,
                harga,
                total,
                waktu_pemesanan
            ) = data

            print("\n-------------------------------")
            print("Nomor booking:", booking_id)
            print("Nama pelanggan:", nama)
            print("Tanggal keberangkatan:",
                  tanggal.strftime("%d-%m-%Y"))
            print("Nama paket:", paket)
            print("Jumlah peserta:", peserta)
            print("Harga per orang:", format_rupiah(harga))
            print("Total biaya:", format_rupiah(total))
            print("Tanggal pemesanan:", waktu_pemesanan)
            print("-------------------------------")

        print("\nTotal data booking:", len(daftar))

    except mysql.connector.Error as error:
        print("Bot: Gagal mengambil data booking.")
        print("Detail error:", error)

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()


# ==========================================
# PROGRAM UTAMA
# ==========================================

def jalankan_bot():
    print("Memeriksa koneksi database...")

    try:
        koneksi = hubungkan_database()
        koneksi.close()
        print("Bot: Berhasil terhubung ke MariaDB.")

    except mysql.connector.Error as error:
        print("Bot: Tidak dapat terhubung ke database.")
        print("Periksa apakah MySQL XAMPP berjalan.")
        print("Detail error:", error)
        return

    tampilkan_menu()

    while True:
        pesan = input("\nAnda: ").strip().lower()

        if pesan == "halo":
            print("Bot: Halo! Selamat datang di layanan wisata kami.")

        elif pesan == "harga":
            tampilkan_harga()

        elif pesan == "booking":
            proses_booking()

        elif pesan == "daftar":
            tampilkan_daftar_booking()

        elif pesan == "keluar":
            print("Bot: Terima kasih. Sampai jumpa!")
            break

        elif pesan == "":
            print("Bot: Silakan ketik salah satu perintah.")

        else:
            print("Bot: Perintah tidak dikenali.")
            print("Bot: Ketik halo, harga, booking, daftar, atau keluar.")


if __name__ == "__main__":
    jalankan_bot()
