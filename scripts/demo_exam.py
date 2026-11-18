"""Demo skenario ujian: satu soal, empat kelas, lalu satu kelas menyebarkan.

Alur untuk video Bagian 8, dijalankan dari folder projek:
  1. Dosen menerbitkan soal untuk kelas A..D; keempat berkas tampak sama.
  2. Halaman milik kelas C tersebar setelah dikompresi dan dipotong.
  3. Penelusur mengunggah potongan itu beserta berkas asal tanpa cap.
  4. Sistem menyebut nomor penerima dan label kelasnya.

Jalankan:  python scripts/demo_exam.py
"""

from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fingerprint import attacks, core, issue, keys, pdf, resync  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "demo")
SUMBER = os.path.join(ROOT, "assets", "samples", "materi_sumber.pdf")
KELAS = [(101, "Kelas A"), (102, "Kelas B"), (103, "Kelas C"), (104, "Kelas D")]
PEMBOCOR = 103
HALAMAN = 3
FRKSI_POTONG = 0.06


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    bentuk = pdf.page_shape(SUMBER)
    print(f"soal asal: {SUMBER}, raster halaman {bentuk[1]}x{bentuk[0]} piksel, "
          f"{len(KELAS)} kelas\n")

    terbit = issue.issue_pdf(SUMBER, OUT, KELAS, secret)
    issue.write_roster(os.path.join(ROOT, "results", "roster.csv"), terbit)
    for record in terbit:
        print(f"terbit {record['nomor']} {record['label']:9s} "
              f"{record['berkas']:20s} PSNR {record['psnr']:.2f} dB  "
              f"SSIM {record['ssim']:.4f}")

    nama = next(r["berkas"] for r in terbit if r["nomor"] == PEMBOCOR)
    halaman = list(pdf.iter_pages(os.path.join(OUT, nama)))[HALAMAN - 1]
    bocor, _ = attacks.crop_border(attacks.jpeg(halaman, 80), FRKSI_POTONG)
    cv2.imwrite(os.path.join(OUT, "bocor_hal3.jpg"), bocor)
    print(f"\nberkas yang beredar: halaman {HALAMAN} {nama}, JPEG kualitas 80, "
          f"dipotong {FRKSI_POTONG:.0%} ({bocor.shape[1]}x{bocor.shape[0]} piksel)")

    tanpa_acuan = core.extract_fingerprint(bocor, secret)
    print(f"tanpa berkas asal : {tanpa_acuan.recipient_id} "
          f"({tanpa_acuan.valid_cells}/{tanpa_acuan.total_cells} sel) -> "
          f"{tanpa_acuan.reason}")

    hasil, fraksi = resync.trace_cropped(bocor, secret, bentuk)
    label = issue.label_for(os.path.join(ROOT, "results", "roster.csv"),
                            hasil.recipient_id)
    print(f"dengan berkas asal: fraksi potongan {fraksi:.2f} -> "
          f"penerima {hasil.recipient_id} ({label}), "
          f"{hasil.valid_cells}/{hasil.total_cells} sel lolos HMAC")

    for record in terbit:
        if record["nomor"] == PEMBOCOR:
            continue
        bersih = list(pdf.iter_pages(os.path.join(OUT, record["berkas"])))[HALAMAN - 1]
        cek = core.extract_fingerprint(bersih, secret)
        print(f"apel {record['nomor']} {record['label']}: terbaca {cek.recipient_id} "
              f"({cek.valid_cells}/{cek.total_cells})")


if __name__ == "__main__":
    main()
