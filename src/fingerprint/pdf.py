"""Sidik jari pada berkas PDF, dikerjakan per halaman.

Cara kerja
----------
Halaman dirender menjadi raster pada DPI tetap, dilewatkan mesin penyisipan
citra yang sama seperti pada berkas gambar, lalu hasilnya ditumpuk menutupi
halaman asal. Kisi sel berpangkal kiri atas pada raster beresolusi tetap,
sehingga posisi penyisipan dapat direproduksi saat pembacaan selama ekstraksi
memakai DPI yang sama.

Konsekuensi yang diterima. Isi halaman menjadi raster: teks vektor tidak lagi
dapat diseleksi pada berkas bersetifikat dan ukuran berkas bertambah. Ditukar
dengan kemampuan menelusuri satu halaman yang difoto atau diunggah berdiri
sendiri, yaitu kasus kebocoran materi ajar yang ingin diselesaikan.
"""

from __future__ import annotations

import numpy as np
import pymupdf

from . import payload as pl
from .core import DEFAULT_DELTA, ExtractionResult, embed_bits, extract_fingerprint

DPI = 150


def render_page(page: pymupdf.Page, dpi: int = DPI) -> np.ndarray:
    """Raster satu halaman sebagai citra BGR uint8."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
    data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return np.ascontiguousarray(data[:, :, :3][:, :, ::-1])


def to_png(image_bgr: np.ndarray) -> bytes:
    """Kemas citra BGR menjadi alur PNG tanpa kerugian untuk ditempel ke halaman.

    PNG dipilih karena kompresi lossy pada berkas PDF sudah ditangani mesin
    pengujian; menambah kerugian lain di sini akan mengaburkan angka hasil.
    """
    import cv2  # lokal: hanya dipakai untuk mengode alur PNG

    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("gagal mengode PNG")
    return buf.tobytes()


def stamp_pdf(src: str, dst: str, recipient_id: int, secret: bytes,
              dpi: int = DPI, delta: float = DEFAULT_DELTA) -> list[dict]:
    """Beri cap seluruh halaman satu berkas PDF dan simpan sebagai berkas baru.

    Tiap halaman membawa identitas penerima yang sama, jadi satu halaman yang
    tersebar berdiri sendiri tetap menunjuk ke penerimanya.
    """
    bits = pl.to_bits(pl.build_payload(recipient_id, secret))
    doc = pymupdf.open(src)
    records = []
    for index in range(doc.page_count):
        page = doc[index]
        raster = render_page(page, dpi)
        marked = embed_bits(raster, bits, secret, delta)
        page.insert_image(page.rect, stream=to_png(marked), overlay=True,
                          keep_proportion=False)
        records.append({"halaman": index + 1, "tinggi": raster.shape[0],
                        "lebar": raster.shape[1]})
    doc.save(dst, deflate=True)
    doc.close()
    return records


def iter_pages(path: str, dpi: int = DPI):
    """Raster tiap halaman satu berkas PDF sebagai penghasil bertahap."""
    doc = pymupdf.open(path)
    try:
        for index in range(doc.page_count):
            yield render_page(doc[index], dpi)
    finally:
        doc.close()


def page_shape(path: str, dpi: int = DPI, page_index: int = 0) -> tuple[int, int]:
    """Dimensi raster satu halaman, dipakai sebagai acuan penyelarasan potongan."""
    doc = pymupdf.open(path)
    try:
        return render_page(doc[page_index], dpi).shape[:2]
    finally:
        doc.close()


def extract_pdf(path: str, secret: bytes, dpi: int = DPI,
                delta: float = DEFAULT_DELTA) -> list[ExtractionResult]:
    """Baca sidik jari tiap halaman; urutan hasil mengikuti urutan halaman."""
    doc = pymupdf.open(path)
    results = [extract_fingerprint(render_page(doc[i], dpi), secret, delta)
               for i in range(doc.page_count)]
    doc.close()
    return results


def audit_pdf(path: str, secret: bytes, dpi: int = DPI,
              delta: float = DEFAULT_DELTA) -> list[dict]:
    """Ringkasan per halaman dalam bentuk yang siap dipakai antarmuka."""
    return [
        {"halaman": index + 1,
         "penerima": result.recipient_id,
         "sel_valid": result.valid_cells,
         "sel_total": result.total_cells,
         "alasan": result.reason}
        for index, result in enumerate(extract_pdf(path, secret, dpi, delta))
    ]


def page_pair(src: str, dst: str, dpi: int = DPI,
              page_index: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Raster halaman yang sama sebelum dan sesudah cap, untuk ukur mutu."""
    with pymupdf.open(src) as before, pymupdf.open(dst) as after:
        return render_page(before[page_index], dpi), render_page(after[page_index], dpi)
