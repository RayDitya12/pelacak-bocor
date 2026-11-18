# -*- coding: utf-8 -*-
"""Uji collusion: sekelompok penerima menggabungkan salinan mereka.

Ancaman ini hanya muncul bila ada dua salinan dengan nomor berbeda di tangan yang
sama, jadi bentuk serangannya merata-rata atau mengambil nilai minimum per piksel
untuk membuang bagian yang berbeda antarsalinan. Yang diuji di sini bukan apakah
bukti hilang, melainkan apakah tuduhan berpindah ke pihak yang tidak ikut
menggabungkan salinan. Skrip memakai keluaran scripts/demo_exam.py.

Jalankan:  python scripts/probe_collusion.py
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


def klasifikasi(hasil, terlibat):
    """Pisahkan tiga nasib: menunjuk anggota kelompok, diam, atau menunjuk orang luar."""
    if hasil.recipient_id is None:
        return "diam"
    if hasil.recipient_id in terlibat:
        return "benar"
    return "salah tuduh"


def utama():
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    berkas = sorted(f for f in os.listdir(DEMO) if f.endswith(".pdf")) if os.path.isdir(DEMO) else []
    if len(berkas) < 2:
        raise SystemExit("butuh sekurang-kurangnya dua salinan, jalankan scripts/demo_exam.py lebih dulu")

    salinan = []
    for nama in berkas:
        halaman = list(pdf.iter_pages(os.path.join(DEMO, nama)))[HALAMAN - 1]
        hasil = core.extract_fingerprint(halaman, secret)
        salinan.append((hasil.recipient_id, halaman))
        print(f"{nama:26s} sendirian  nomor {hasil.recipient_id}  "
              f"{hasil.valid_cells}/{hasil.total_cells}")
    print()

    print(f"{'gabungan':20s} {'sel':>5s}  {'nasib':>12s}  {'nomor yang dilaporkan':>22s}")
    for k in range(2, len(salinan) + 1):
        tumpuk = np.stack([np.array(h, dtype=np.int16) for _, h in salinan[:k]])
        for cara in ("median", "min"):
            gabungan = np.median(tumpuk, axis=0) if cara == "median" else tumpuk.min(axis=0)
            uji = np.ascontiguousarray(gabungan.astype("uint8"))
            if uji.ndim == 2:
                uji = cv2.cvtColor(uji, cv2.COLOR_GRAY2BGR)
            terlibat = {id_asal for id_asal, _ in salinan[:k]}
            hasil = core.extract_fingerprint(uji, secret)
            dilaporkan = "-" if hasil.recipient_id is None else hasil.recipient_id
            print(f"{k} salinan {cara:7s} {hasil.valid_cells:5d}  {klasifikasi(hasil, terlibat):>12s}"
                  f"  {str(dilaporkan):>10s} dari {sorted(terlibat)}")


if __name__ == "__main__":
    utama()
