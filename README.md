# SIMOCS
### Sistem Monitoring CCTV Berbasis Server

SIMOCS (Sistem Monitoring CCTV) merupakan sistem berbasis web yang dikembangkan untuk melakukan monitoring aktivitas manusia melalui kamera CCTV dengan memanfaatkan teknologi Artificial Intelligence (AI).

Sistem ini dirancang untuk membantu proses pemantauan aktivitas di lingkungan Ruang Teknologi Informasi PSP PT Pupuk Sriwidjaja Palembang secara lebih terstruktur melalui dashboard monitoring.

## Tujuan Proyek

Mengembangkan sistem monitoring CCTV berbasis web yang dapat menampilkan informasi hasil deteksi manusia dan aktivitasnya secara terpusat melalui server.

## Arsitektur Sistem

Sistem SIMOCS memiliki alur kerja sebagai berikut:

1. **CCTV** – Menyediakan input video melalui RTSP Stream.
2. **AI Engine** – Melakukan deteksi manusia dan pengenalan aktivitas.
3. **Flask API** – Menerima dan memproses data hasil deteksi dari AI Engine.
4. **MySQL Database** – Menyimpan data hasil deteksi dan aktivitas.
5. **Web Dashboard** – Menampilkan informasi monitoring secara real-time atau berkala.

## Fitur Sistem

- Monitoring jumlah manusia yang terdeteksi.
- Menampilkan aktivitas manusia seperti berdiri, duduk, dan berjalan.
- Menampilkan durasi aktivitas.
- Menyimpan riwayat hasil deteksi.
- Menampilkan informasi peringatan aktivitas.
- Dashboard monitoring berbasis web.

## Teknologi yang Digunakan

- Python
- Flask
- MySQL
- HTML
- CSS
- JavaScript
- Artificial Intelligence (AI)
- YOLO (pada AI Engine)

## Struktur Repository

```text
SIMOCS/
├── static/
├── templates/
├── app.py
├── create_user.py
├── test_api.py
└── README.md
```

## Pengembangan

Proyek ini dikembangkan sebagai bagian dari kegiatan Kerja Praktik (KP) di PT Pupuk Sriwidjaja Palembang.

Repository ini digunakan sebagai dokumentasi dan penyimpanan source code pengembangan sistem SIMOCS.
