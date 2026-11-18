"""Serangan/transformasi yang mungkin menimpa berkas hasil bocor.

Setiap fungsi menerima dan mengembalikan citra BGR uint8, sehingga hasil
pemrosesan benar-benar melewati kanal yang sama dengan berkas sungguhan
(termasuk kuantisasi 8 bit dan penyimpanan JPEG).
"""

from __future__ import annotations

import cv2
import numpy as np


def jpeg(image_bgr: np.ndarray, quality: int) -> np.ndarray:
    """Kompresi lossy JPEG, simulasi kirim lewat chat/email atau unggah portal."""
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("gagal mengode JPEG")
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def gaussian_noise(image_bgr: np.ndarray, sigma: float) -> np.ndarray:
    """Derau Gaussian aditif, simulasi tangkapan layar berkualitas rendah."""
    noisy = image_bgr.astype(np.float64) + np.random.default_rng(int(sigma * 100)).normal(
        0.0, sigma, image_bgr.shape[:2] + (1,)
    )
    return np.clip(noisy, 0, 255).round().astype(np.uint8)


def salt_pepper(image_bgr: np.ndarray, amount: float = 0.01) -> np.ndarray:
    """Derau garam-merica pada fraksi piksel tertentu."""
    rng = np.random.default_rng(7)
    out = image_bgr.copy()
    total = out.shape[0] * out.shape[1]
    count = int(total * amount)
    rows, cols = rng.integers(0, out.shape[0], count), rng.integers(0, out.shape[1], count)
    out[rows[: count // 2], cols[: count // 2]] = 0
    out[rows[count // 2 :], cols[count // 2 :]] = 255
    return out


def resize(image_bgr: np.ndarray, scale: float) -> np.ndarray:
    """Ubah ukuran lalu kembalikan ke dimensi awal, seperti fitur potong-unggah portal."""
    h, w = image_bgr.shape[:2]
    small = cv2.resize(image_bgr, (max(1, int(w * scale)), max(1, int(h * scale))),
                       interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def crop_border(image_bgr: np.ndarray, fraction: float) -> tuple[np.ndarray, tuple[int, int]]:
    """Potong sekeliling citra sebanding fraksi sisi terpendek.

    Offset dikembalikan sebagai (tinggi, lebar) karena potongan fraksi yang
    sama pada berkas non-persegi menghasilkan lebar berbeda pada tiap sumbu;
    menyatukannya menjadi satu angka membuat penempelan ulang salah sumbu dan
    seluruh kisi ikut meleset.
    """
    height, width = image_bgr.shape[:2]
    off_y, off_x = int(height * fraction), int(width * fraction)
    return image_bgr[off_y:height - off_y, off_x:width - off_x], (off_y, off_x)


def blur(image_bgr: np.ndarray, ksize: int = 5) -> np.ndarray:
    """Pengaburan Gaussian, simulasi foto ulang layar."""
    k = ksize if ksize % 2 == 1 else ksize + 1
    return cv2.GaussianBlur(image_bgr, (k, k), 0)


def brightness(image_bgr: np.ndarray, shift: int) -> np.ndarray:
    """Geser kecerahan menyeluruh, misal mode gelap pada penampil dokumen."""
    return np.clip(image_bgr.astype(np.int16) + shift, 0, 255).astype(np.uint8)


def contrast(image_bgr: np.ndarray, gain: float) -> np.ndarray:
    """Perubahan kontras menyeluruh."""
    return np.clip(image_bgr.astype(np.float64) * gain, 0, 255).round().astype(np.uint8)


def reanchor(cropped: np.ndarray, reference_shape: tuple[int, int],
             offset: int | tuple[int, int]) -> np.ndarray:
    """Tempelkan potongan kembali ke kanvas berukuran berkas asli.

    Penelusur mengetahui dimensi materi yang ia edarkan, jadi posisi geometri
    dapat dipulihkan sebelum ekstraksi. Bingkai yang hilang diisi dengan
    perulangan piksel tepi, bukan hitam: pengisian hitam mengubah sebaran
    seluruh subband dan menggeser lebar kisi yang dihitung darinya, sehingga
    sel-sel yang masih utuh ikut terbaca salah.
    """
    rh, rw = reference_shape[:2]
    h, w = cropped.shape[:2]
    off_y, off_x = (offset, offset) if isinstance(offset, int) else offset
    y = max(0, min(off_y, rh - h))
    x = max(0, min(off_x, rw - w))
    return cv2.copyMakeBorder(cropped, y, max(rh - (y + h), 0), x,
                              max(rw - (x + w), 0), cv2.BORDER_REPLICATE)
