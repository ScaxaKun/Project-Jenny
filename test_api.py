"""
test_api.py - SIMULATOR AI Engine (BUKAN AI Engine yang sebenarnya).
 
Cara pakai (di terminal, folder project, venv aktif, server Flask sedang jalan):
 
    python test_api.py                 -> kirim 1 data (3 orang) dengan waktu SEKARANG
    python test_api.py loop            -> kirim data acak tiap 5 detik, berhenti dengan Ctrl+C
    python test_api.py loop 10         -> sama, tapi tiap 10 detik
 
    python test_api.py alert           -> kirim 1 data yang berisi PERINGATAN (duduk/berdiri 1 jam atau lebih)
    python test_api.py alert loop      -> kirim terus tiap 5 detik, durasinya BERTAMBAH seperti kejadian nyata:
                                          dalam sekitar 1 menit kamu melihat peringatan muncul satu per satu
    python test_api.py alert loop 2    -> sama, tapi tiap 2 detik (lebih cepat)
 
Untuk melihat status di dashboard berubah:
    1. Jalankan mode loop        -> status "Online"
    2. Tekan Ctrl+C (berhenti)   -> setelah 60 detik "Delayed", setelah 5 menit "Offline"
"""
 
import random
import sys
import time
from datetime import datetime
 
import requests
 
URL = "http://127.0.0.1:5000/api/detection"
CAMERA_ID = "CAM01"
ACTIVITIES = ["standing", "sitting", "walking"]
 
 
def now_text():
    """Waktu sekarang dalam format yang diterima server: 2026-10-14 09:30:15"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 
 
def sample_once():
    """Data contoh tetap (sama seperti sebelumnya), tapi dengan waktu sekarang."""
    return {
        "camera_id": CAMERA_ID,
        "timestamp": now_text(),
        "person_count": 3,
        "activities": [
            {"person_id": 1, "activity": "standing", "duration": 20},
            {"person_id": 2, "activity": "sitting", "duration": 35},
            {"person_id": 3, "activity": "standing", "duration": 10},
        ],
    }
 
 
def sample_random():
    """Data acak (1-4 orang) supaya angka di dashboard terlihat berubah."""
    count = random.randint(1, 4)
    activities = [
        {
            "person_id": number,
            "activity": random.choice(ACTIVITIES),
            "duration": random.randint(5, 120),
        }
        for number in range(1, count + 1)
    ]
    return {
        "camera_id": CAMERA_ID,
        "timestamp": now_text(),
        "person_count": count,
        "activities": activities,
    }
 
 
def sample_alert(elapsed=0):
    """
    Data yang berisi peringatan. 'elapsed' = detik sejak simulasi dimulai,
    ditambahkan ke durasi supaya durasinya terus bertambah seperti kejadian nyata.
    Batas peringatan: 3600 detik (1 jam) untuk duduk atau berdiri.
    """
    activities = [
        {"person_id": 1, "activity": "walking",  "duration": 8 + elapsed % 25},    # jalan kaki: tidak pernah peringatan
        {"person_id": 2, "activity": "sitting",  "duration": 3725 + elapsed},      # sudah lewat 1 jam -> peringatan
        {"person_id": 3, "activity": "standing", "duration": 3560 + elapsed},      # melewati 1 jam setelah sekitar 40 detik
        {"person_id": 4, "activity": "sitting",  "duration": 900 + elapsed},       # 15 menit, aman
    ]
    return {
        "camera_id": CAMERA_ID,
        "timestamp": now_text(),
        "person_count": len(activities),
        "activities": activities,
    }
 
 
def send(data):
    """Kirim data ke server. Mengembalikan True kalau berhasil."""
    try:
        response = requests.post(URL, json=data, timeout=5)
    except requests.exceptions.ConnectionError:
        print("Gagal: server tidak bisa dihubungi. Pastikan Flask sedang berjalan (python app.py).")
        return False
    except requests.exceptions.Timeout:
        print("Gagal: server terlalu lama menjawab.")
        return False
 
    try:
        body = response.json()
    except ValueError:
        body = response.text[:200]      # jawaban bukan JSON (misalnya halaman error)
 
    print(f"[{data['timestamp']}] Status code: {response.status_code} | "
          f"{data['person_count']} orang | Response: {body}")
    return response.ok
 
 
def run_loop(make_data, interval):
    print(f"Mode loop: kirim data tiap {interval} detik. Tekan Ctrl+C untuk berhenti.")
    started = time.time()
    try:
        while True:
            send(make_data(int(time.time() - started)))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDihentikan. Kalau tidak ada data baru, dashboard akan berubah ke Delayed lalu Offline.")
 
 
def read_interval(args, default=5):
    for item in args:
        if item.isdigit():
            return int(item)
    return default
 
 
def main():
    args = sys.argv[1:]
 
    if args and args[0] == "alert":
        if "loop" in args[1:]:
            run_loop(sample_alert, read_interval(args[1:]))
        else:
            send(sample_alert())
    elif args and args[0] == "loop":
        run_loop(lambda elapsed: sample_random(), read_interval(args[1:]))
    else:
        send(sample_once())
 
 
if __name__ == "__main__":
    main()
 