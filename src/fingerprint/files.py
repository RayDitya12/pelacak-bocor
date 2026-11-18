"""Bantuan baca/tulis berkas citra yang aman untuk jalur berisi spasi atau karakter non-ASCII."""

from __future__ import annotations

import os

import cv2
import numpy as np


def read_image(path: str) -> np.ndarray:
    """Baca citra menjadi BGR uint8; galat menyebut nama berkas agar mudah dilacak."""
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise IOError(f"bukan berkas citra yang terbaca: {path}")
    return image


def write_image(path: str, image: np.ndarray) -> str:
    """Tulis citra memakai imencode agar nama berkas non-ASCII tidak gagal diam-diam."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, image)
    if not ok:
        raise IOError(f"gagal mengode citra untuk {path}")
    buf.tofile(path)
    return path


def ensure_dir(path: str) -> str:
    """Buat direktori bila belum ada, kembalikan jalurnya."""
    os.makedirs(path, exist_ok=True)
    return path
