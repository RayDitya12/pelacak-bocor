"""Penyelarasan berkas yang dipotong, bila ukuran berkas asal diketahui.

Kisi sel berpangkal di kiri atas, jadi potongan selebar c piksel menggeser
seluruh isi sejauh c. Karena penelusur memegang berkas asal, dimensi asalnya
diketahui dan posisi geometri dapat dipulihkan: potongan ditempel kembali ke
kanvas berukuran asal pada offset percobaan, lalu dibaca. Offset yang benar
menghasilkan paling banyak sel lolos verifikasi; pembacaan dengan banyak sel
valid sekaligus menjadi bukti bahwa penyelarasan itu bukan tebakan.

Harga yang dibayar: satu pembacaan penuh per offset. Sapuan 0..160 piksel
dengan jarak 4 lalu perbaikan jarak 1 berarti sekitar lima puluh pembacaan.
"""

from __future__ import annotations

import numpy as np

from .attacks import reanchor
from .core import DEFAULT_DELTA, SUBBAND, ExtractionResult, extract_fingerprint

MAX_FRACTION = 0.16
COARSE_STEP = 0.01


def read_at(cropped: np.ndarray, secret: bytes, reference_shape: tuple[int, int],
            offset: tuple[int, int], delta: float = DEFAULT_DELTA,
            subband: str = SUBBAND) -> ExtractionResult:
    """Tempel potongan pada kanvas berukuran asal di offset tertentu, lalu baca."""
    return extract_fingerprint(reanchor(cropped, reference_shape, offset), secret,
                               delta, subband)


def trace_cropped(cropped: np.ndarray, secret: bytes, reference_shape: tuple[int, int],
                  max_fraction: float = MAX_FRACTION, coarse: float = COARSE_STEP,
                  delta: float = DEFAULT_DELTA,
                  subband: str = SUBBAND) -> tuple[ExtractionResult, int]:
    """Cari fraksi potongan yang membuat paling banyak sel terbaca sah.

    Yang dicari adalah potongan sekeliling dengan fraksi sama pada kedua sumbu,
    yaitu bentuk paling umum dari hasil potong unggah portal. Kembalikan hasil
    terbaik dan fraksinya; lebar per sumbu diturunkan dari dimensi berkas asal.
    """
    height, width = reference_shape[:2]

    def at(fraction: float) -> tuple[int, int]:
        return int(height * fraction), int(width * fraction)

    best: tuple[ExtractionResult, float] | None = None

    def consider(fraction: float) -> None:
        nonlocal best
        result = read_at(cropped, secret, reference_shape, at(fraction), delta, subband)
        if best is None or result.valid_cells > best[0].valid_cells:
            best = (result, fraction)

    for step in range(0, int(max_fraction / coarse) + 1):
        consider(step * coarse)
    centre = best[1]
    fine = coarse / 10.0
    for step in range(-10, 11):
        value = round(centre + step * fine, 4)
        if 0.0 <= value < centre + coarse:
            consider(value)
    return best
