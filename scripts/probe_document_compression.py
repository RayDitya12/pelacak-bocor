# -*- coding: utf-8 -*-
"""Uji saluran kompresi dokumen yang tidak tercakup matriks serangan.

Peralatan seperti fitur "Reduce File Size" pada pembuat PDF bekerja dengan
menurunkan resolusi raster halaman lalu menyandikan ulang; untuk halaman yang
dominan putih, preset minimum dapat memakai JBIG2 atau CCITT Group 4 dua tingkat
warna. Matriks pada results/serangan.csv menguji resample dan JPEG secara
terpisah, jadi skrip ini mengukur kombinasi keduanya pada seluruh salinan hasil
scripts/demo_exam.py. Yang dicari bukan satu angka, melainkan batas terburuk dan
apakah identitas pernah bergeser ke penerima lain.

Jalankan:  python scripts/probe_document_compression.py
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from fingerprint import core, keys, pdf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "results", "demo")
HALAMAN = 3

KONDISI = [
    ("asli tanpa proses", None),
    ("bilevel 1 bit (JBIG2/CCITT)", "bilevel"),
    ("resample 100 dpi + JPEG 60", (2 / 3, 60)),
    ("resample 100 dpi + JPEG 40", (2 / 3, 40)),
    ("resample 75 dpi + JPEG 60", (0.5, 60)),
    ("resample 60 dpi + JPEG 50", (0.4, 50)),
]


def proses(halaman, cara):
    tinggi, lebar = halaman.shape[:2]
    if cara is None:
        return halaman
    if cara == "bilevel":
        abu = cv2.cvtColor(halaman, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(np.where(abu > 127, 255, 0).astype("uint8"), cv2.COLOR_GRAY2BGR)
    skala, kualitas = cara
    kecil = cv2.resize(halaman, (int(lebar * skala), int(tinggi * skala)),
                       interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", kecil, [int(cv2.IMWRITE_JPEG_QUALITY), kualitas])
    return cv2.resize(cv2.imdecode(buf, cv2.IMREAD_COLOR), (lebar, tinggi),
                      interpolation=cv2.INTER_CUBIC)


def utama():
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    berkas = sorted(f for f in os.listdir(DEMO) if f.endswith(".pdf")) if os.path.isdir(DEMO) else []
    if not berkas:
        raise SystemExit("tidak ada PDF di results/demo, jalankan scripts/demo_exam.py lebih dulu")

    salinan = []
    for nama in berkas:
        halaman = list(pdf.iter_pages(os.path.join(DEMO, nama)))[HALAMAN - 1]
        salinan.append((nama, core.extract_fingerprint(halaman, secret).recipient_id, halaman))
    tinggi, lebar = salinan[0][2].shape[:2]
    print(f"{len(salinan)} salinan, halaman {tinggi}x{lebar} piksel (150 dpi), "
          f"nomor asal {', '.join(str(id_asal) for _, id_asal, _ in salinan)}\n")

    print(f"{'kondisi':32s} {'terburuk':>9s}  {'benar':>6s} {'diam':>6s} {'salah tuduh':>12s}")
    for nama_kondisi, cara in KONDISI:
        terburuk, benar, diam, salah = [], 0, 0, 0
        for _, id_asal, halaman in salinan:
            hasil = core.extract_fingerprint(proses(halaman, cara), secret)
            terburuk.append(hasil.valid_cells)
            if hasil.recipient_id is None:
                diam += 1
            elif hasil.recipient_id == id_asal:
                benar += 1
            else:
                salah += 1
        print(f"{nama_kondisi:32s} {min(terburuk):9d}  {benar:6d} {diam:6d} {salah:12d}"
              + ("  << SALAH TUDUH" if salah else ""))


if __name__ == "__main__":
    utama()
