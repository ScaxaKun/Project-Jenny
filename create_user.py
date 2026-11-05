"""
Script untuk membuat user baru lewat terminal.

Jalankan (di folder project, venv aktif):
    python create_user.py

Semua isian ditanyakan saat script berjalan. Password diketik tanpa tampil di layar
dan TIDAK disimpan di file ini. Aturannya sama dengan halaman User Management.
"""

import re
from getpass import getpass

import mysql.connector
from werkzeug.security import generate_password_hash

VALID_ROLES = ("admin", "user")
MIN_PASSWORD_LENGTH = 6
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{3,50}")


def get_database_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="cctv_monitoring"
    )


def create_user(username, password, full_name, role):
    """Buat user baru di database dengan password ter-hash. Mengembalikan True kalau berhasil."""

    db = get_database_connection()
    cursor = db.cursor()

    sql = """
        INSERT INTO users
        (username, password_hash, full_name, role)
        VALUES (%s, %s, %s, %s)
    """

    try:
        cursor.execute(sql, (username, generate_password_hash(password), full_name, role))
        db.commit()
        print(f"Berhasil: user '{username}' dibuat (role: {role}).")
        return True
    except mysql.connector.Error as err:
        print(f"Gagal: {err}")
        return False
    finally:
        cursor.close()
        db.close()


def username_exists(username):
    db = get_database_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    found = cursor.fetchone() is not None
    cursor.close()
    db.close()
    return found


def ask_username():
    while True:
        username = input("Username (3-50 karakter: huruf, angka, titik, garis bawah, atau strip): ").strip()
        if not USERNAME_PATTERN.fullmatch(username):
            print("  Username tidak valid, coba lagi.")
        elif username_exists(username):
            print(f"  Username '{username}' sudah dipakai, coba yang lain.")
        else:
            return username


def ask_full_name():
    while True:
        full_name = input("Nama lengkap: ").strip()
        if not full_name:
            print("  Nama lengkap wajib diisi.")
        elif len(full_name) > 100:
            print("  Maksimal 100 karakter.")
        else:
            return full_name


def ask_role():
    while True:
        role = input("Role (admin / user) [user]: ").strip().lower() or "user"
        if role in VALID_ROLES:
            return role
        print("  Role harus 'admin' atau 'user'.")


def ask_password():
    while True:
        password = getpass(f"Password (minimal {MIN_PASSWORD_LENGTH} karakter, tidak tampil di layar): ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"  Password minimal {MIN_PASSWORD_LENGTH} karakter.")
            continue
        if getpass("Ulangi password: ") != password:
            print("  Kedua password tidak sama, coba lagi.")
            continue
        return password


def main():
    print("=== Buat User Baru ===\n")

    username = ask_username()
    full_name = ask_full_name()
    role = ask_role()
    password = ask_password()

    print()
    create_user(username, password, full_name, role)


if __name__ == "__main__":
    main()
