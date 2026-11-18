"""Ukur ketahanan satu halaman PDF yang tersebar sebagai berkas gambar.

Halaman bersetifikat dirender, lalu tiap saluran kebocoran nyata dijalankan
di atasnya: unggah dengan kompresi, foto ulang layar, perkecil, potong.

Jalankan:  python scripts/run_pdf_tests.py
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import pymupdf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fingerprint import attacks, core, keys, pdf, resync  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERKAS = os.path.join(ROOT, "assets", "samples", "materi_bersetifikat.pdf")

SERANGAN = [
    ("bersih", lambda img: img),
    ("jpeg_q95", lambda img: attacks.jpeg(img, 95)),
    ("jpeg_q80", lambda img: attacks.jpeg(img, 80)),
    ("jpeg_q60", lambda img: attacks.jpeg(img, 60)),
    ("blur_k3", lambda img: attacks.blur(img, 3)),
    ("resize_0.5", lambda img: attacks.resize(img, 0.5)),
    ("brightness_+25", lambda img: attacks.brightness(img, 25)),
    ("contrast_x1.3", lambda img: attacks.contrast(img, 1.3)),
    ("crop_5pct_selaras", lambda img: attacks.reanchor(
        *(lambda c: (c[0], img.shape, c[1]))(attacks.crop_border(img, 0.05)))),
    ("crop_10pct_selaras", lambda img: attacks.reanchor(
        *(lambda c: (c[0], img.shape, c[1]))(attacks.crop_border(img, 0.10)))),
]


def selaraskan(halaman, secret, bentuk):
    """Jalur penelusuran yang sama dengan antarmuka web: baca langsung, lalu cari fraksi."""
    hasil = core.extract_fingerprint(halaman, secret)
    if hasil.ok:
        return hasil, None
    _, fraksi = resync.trace_cropped(halaman, secret, bentuk)
    tinggi, lebar = int(bentuk[0] * fraksi), int(bentuk[1] * fraksi)
    dipulihkan = core.extract_fingerprint(attacks.reanchor(halaman, bentuk, (tinggi, lebar)),
                                          secret)
    return (dipulihkan if dipulihkan.ok else hasil), fraksi


def main() -> None:
    if not os.path.exists(BERKAS):
        raise SystemExit("materi_bersetifikat.pdf belum ada, jalankan lebih dulu: "
                         "python scripts/make_pdf_sample.py")
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    page = pdf.render_page(pymupdf.open(BERKAS)[0])
    print(f"halaman 1 berukuran {page.shape[1]}x{page.shape[0]} piksel\n")
    for label, fn in SERANGAN:
        result = core.extract_fingerprint(fn(page), secret)
        status = "YA" if result.ok and result.recipient_id == 42 else "TIDAK"
        print(f"   {label:19s} {status:6s} {result.valid_cells:2d}/{result.total_cells:2d}")

    halaman = list(pdf.iter_pages(BERKAS))
    bentuk = halaman[0].shape[:2]
    bocor = list(halaman)
    bocor[2] = attacks.crop_border(bocor[2], 0.10)[0]
    print(f"\nwaktu penelusuran berkas {len(bocor)} halaman, halaman 3 dipotong 10%:")
    mulai = time.perf_counter()
    perlu = [nomor for nomor, lembar in enumerate(bocor)
             if not core.extract_fingerprint(lembar, secret).ok]
    langsung = time.perf_counter() - mulai
    print(f"   ekstraksi langsung {len(bocor)} halaman"
          f"{'':>7}: {langsung:.1f} detik, {len(perlu)} halaman perlu penyelarasan")
    mulai = time.perf_counter()
    hasil, fraksi = selaraskan(bocor[perlu[0]], secret, bentuk)
    selaras = time.perf_counter() - mulai
    status = "YA" if hasil.ok and hasil.recipient_id == 42 else "TIDAK"
    print(f"   penyelarasan 1 halaman{'':>10}: {selaras:.1f} detik -> {status} "
          f"{hasil.valid_cells}/{hasil.total_cells} sel, fraksi {fraksi:.2f}")
    print(f"   total satu berkas{'':>17}: {langsung + selaras:.1f} detik")


if __name__ == "__main__":
    main()
