"""Penerbitan massal: satu materi, banyak salinan bernomor.

Skenario yang dilayani: seorang dosen mengedarkan berkas soal ke empat kelas
pada waktu ujian berbeda. Setiap kelas menerima berkas dengan nomor penerima
berbeda sementara isinya identik, sehingga soal yang tersebar dapat ditelusuri
kembali ke kelas (atau mahasiswa) yang menerima salinan itu.

Nomor yang tertanam di cap adalah angka, bukan nama. Pemetaan nomor ke label
hanya disimpan di berkas roster sisi penerbit, jadi materi yang beredar tidak
memuat data pribadi di dalam cap-nya.
"""

from __future__ import annotations

import csv
import os
import time
import zipfile

from . import metrics, pdf
from .core import DEFAULT_DELTA, embed_bits, extract_fingerprint
from .files import read_image, write_image
from .payload import build_payload, to_bits

ROSTER_FIELDS = ("nomor", "label", "berkas", "psnr", "ssim", "waktu")


def parse_roster(teks: str) -> list[tuple[int, str]]:
    """Baca recipients penerima dari teks `nomor,label` per baris."""
    recipients = []
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#"):
            continue
        nomor, _, label = baris.partition(",")
        recipients.append((int(nomor), (label or nomor).strip()))
    if not recipients:
        raise ValueError("recipients penerima kosong, tulis satu baris per penerima")
    if len({nomor for nomor, _ in recipients}) != len(recipients):
        raise ValueError("ada nomor penerima yang ganda")
    return recipients


def issue_images(src: str, out_dir: str, recipients: list[tuple[int, str]], secret: bytes,
                 delta: float = DEFAULT_DELTA) -> list[dict]:
    """Terbitkan satu berkas gambar untuk tiap penerima; hasil PNG."""
    os.makedirs(out_dir, exist_ok=True)
    image = read_image(src)
    records = []
    for nomor, label in recipients:
        marked = embed_bits(image, to_bits(build_payload(nomor, secret)), secret, delta)
        nama = f"{nomor}_{label.replace(' ', '_')}.png"
        write_image(os.path.join(out_dir, nama), marked)
        cek = extract_fingerprint(marked, secret)
        records.append({"nomor": nomor, "label": label, "berkas": nama,
                        "psnr": round(metrics.psnr(image, marked), 2),
                        "ssim": round(metrics.ssim(image, marked), 4),
                        "sel_valid": cek.valid_cells, "sel_total": cek.total_cells,
                        "waktu": time.strftime("%Y-%m-%d %H:%M:%S")})
    return records


def issue_pdf(src: str, out_dir: str, recipients: list[tuple[int, str]], secret: bytes,
              dpi: int = pdf.DPI, delta: float = DEFAULT_DELTA) -> list[dict]:
    """Terbitkan berkas PDF asal dalam satu salinan bersetifikat per penerima."""
    os.makedirs(out_dir, exist_ok=True)
    records = []
    for nomor, label in recipients:
        nama = f"{nomor}_{label.replace(' ', '_')}.pdf"
        tujuan = os.path.join(out_dir, nama)
        halaman = pdf.stamp_pdf(src, tujuan, nomor, secret, dpi, delta)
        before, after = pdf.page_pair(src, tujuan)
        records.append({"nomor": nomor, "label": label, "berkas": nama,
                        "psnr": round(metrics.psnr(before, after), 2),
                        "ssim": round(metrics.ssim(before, after), 4),
                        "sel_valid": len(halaman), "sel_total": len(halaman),
                        "waktu": time.strftime("%Y-%m-%d %H:%M:%S")})
    return records


def write_roster(path: str, records: list[dict]) -> None:
    """Lengkapi berkas roster; nomor penerima dipetakan ke label internal."""
    lama = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            lama = [row for row in csv.DictReader(fh)
                    if row.get("nomor") not in {str(r["nomor"]) for r in records}]
    fields = (*ROSTER_FIELDS, "sel_valid", "sel_total")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(lama)
        writer.writerows(records)


def label_for(roster_path: str, nomor: int) -> str | None:
    """Cari label internal sebuah nomor; None bila tidak dikenal."""
    if not os.path.exists(roster_path):
        return None
    with open(roster_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("nomor") == str(nomor):
                return row.get("label")
    return None


def bundle_zip(out_dir: str, records: list[dict], path: str) -> str:
    """Kemas seluruh salinan menjadi satu berkas unduhan."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zip_:
        for record in records:
            zip_.write(os.path.join(out_dir, record["berkas"]), record["berkas"])
    return path
