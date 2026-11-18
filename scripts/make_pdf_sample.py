"""Bangun PDF materi ajar contoh lalu uji cap sidik jari per halaman.

PDF dibuat dengan PyMuPDF sendiri (judul, paragraf, gambar, garis tabel) agar
pengujian benar-benar melewati berkas PDF, bukan citra yang ganti ekstensi.

Jalankan:  python scripts/make_pdf_sample.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pymupdf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fingerprint import keys, metrics, pdf  # noqa: E402
from fingerprint.files import ensure_dir  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "samples")
SUMBER = os.path.join(OUT, "materi_sumber.pdf")
CAP = os.path.join(OUT, "materi_bersetifikat.pdf")
HALAMAN = 4
RECIPIENT = 42

KALIMAT = (
    "Setiap salinan materi membawa identitas tersembunyi sehingga berkas yang "
    "tersebar dapat ditelusuri kembali ke penerimanya tanpa mengubah isi yang "
    "dibaca mahasiswa."
)


def build_source(path: str, pages: int = HALAMAN) -> None:
    """Tulis PDF contoh A4 berisi teks, gambar bernada, dan garis tabel."""
    doc = pymupdf.open()
    rng = np.random.default_rng(4)
    for number in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 84), f"Materi Perkuliahan Modul {number + 1}",
                         fontsize=18, fontname="helv")
        page.insert_textbox(pymupdf.Rect(60, 112, 535, 330),
                            (KALIMAT + " ") * 6, fontsize=11, fontname="helv")
        tone = np.tile(np.linspace(90, 210, 240).astype(np.uint8), (170, 1))
        gray = np.clip(tone.astype(np.int16) + rng.integers(-12, 13, tone.shape),
                       0, 255).astype(np.uint8)
        page.insert_image(pymupdf.Rect(60, 350, 400, 590),
                          stream=pdf.to_png(np.dstack([gray, gray, gray])))
        for row in range(6):
            y = 620 + row * 26
            page.draw_line(pymupdf.Point(60, y), pymupdf.Point(535, y), width=0.7)
            page.insert_text((68, y - 8), f"baris {row + 1}  nilai {(row * 17) % 100:02d}",
                             fontsize=10)
    doc.save(path)
    doc.close()


def main() -> None:
    ensure_dir(OUT)
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    build_source(SUMBER)
    print(f"sumber : {SUMBER} {os.path.getsize(SUMBER) / 1024:.1f} kB")

    records = pdf.stamp_pdf(SUMBER, CAP, RECIPIENT, secret)
    print(f"bersetifikat: {CAP} {os.path.getsize(CAP) / 1024:.1f} kB, "
          f"{len(records)} halaman @ {records[0]['lebar']}x{records[0]['tinggi']}")

    before, after = pdf.page_pair(SUMBER, CAP)
    print(f"raster halaman 1: PSNR {metrics.psnr(before, after):5.2f} dB  "
          f"SSIM {metrics.ssim(before, after):.4f}  "
          f"selisih maks {metrics.max_abs_diff(before, after)}")

    for row in pdf.audit_pdf(CAP, secret):
        print(f"   halaman {row['halaman']}: penerima {row['penerima']} "
              f"({row['sel_valid']}/{row['sel_total']} sel)")


if __name__ == "__main__":
    main()
