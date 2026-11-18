"""Bangkitkan citra uji sintetis 1024x1024.

Dipakai tiga jenis konten karena ketahanan watermark sangat bergantung pada
karakteristik citra: daerah halus paling sensitif terhadap artefak, daerah
bertekstur menyembunyikan perubahan, dan halaman dokumen adalah kasus nyata
materi kuliah yang akan dilindungi.
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fingerprint.files import ensure_dir, write_image  # noqa: E402

SIZE = 1024
OUT_DIR = os.path.join(ROOT, "assets", "samples")


def smooth_scene() -> np.ndarray:
    """Gradien halus plus lingkaran dan kotak: uji paling berat untuk imperceptibility."""
    axis = np.linspace(0.0, 1.0, SIZE)
    base = 60 + 150 * (0.55 * axis[:, None] + 0.45 * axis[None, :])
    img = np.stack([base] * 3, axis=2).astype(np.float64)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    ring = ((xx - 300) ** 2 + (yy - 320) ** 2) < 180**2
    img[ring] = [40, 170, 220]
    square = (np.abs(xx - 720) < 150) & (np.abs(yy - 700) < 150)
    img[square] = [200, 90, 60]
    return np.clip(img, 0, 255).astype(np.uint8)


def textured_scene() -> np.ndarray:
    """Tekstur acak terstruktur: daerah yang paling mudah menyimpan data tersembunyi."""
    rng = np.random.default_rng(2026)
    coarse = cv2.resize(rng.random((64, 64)), (SIZE, SIZE), interpolation=cv2.INTER_CUBIC)
    fine = cv2.GaussianBlur(rng.random((SIZE, SIZE)), (0, 0), 1.2)
    grid = ((np.add.outer(np.arange(SIZE), np.arange(SIZE))) // 32) % 2
    merged = 0.55 * coarse + 0.35 * fine + 0.10 * grid
    channels = [merged, np.roll(merged, 121, axis=1), np.roll(merged, -77, axis=0)]
    img = np.stack(channels, axis=2)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def document_page() -> np.ndarray:
    """Halaman materi kuliah: latar putih, judul, batang teks, gambar, dan tabel."""
    img = np.full((SIZE, SIZE, 3), 250, np.uint8)
    cv2.rectangle(img, (70, 70), (954, 140), (30, 60, 120), -1)
    cv2.putText(img, "MATERI PERTEMUAN 09", (95, 118), cv2.FONT_HERSHEY_SIMPLEX, 1.1,
                (250, 250, 250), 2, cv2.LINE_AA)
    y = 190
    for row in range(22):
        width = int(600 + 320 * abs(np.sin(row * 1.7)))
        cv2.rectangle(img, (80, y), (80 + width, y + 13), (60, 60, 60), -1)
        y += 28
        if row == 9:
            cv2.rectangle(img, (200, y), (820, y + 190), (220, 200, 150), -1)
            cv2.circle(img, (510, y + 95), 70, (40, 120, 200), -1)
            y += 215
    for r in range(4):
        for c in range(5):
            cv2.rectangle(img, (80 + c * 175, y + r * 45), (80 + (c + 1) * 175, y + (r + 1) * 45),
                          (90, 90, 90), 1)
    return img


def main() -> None:
    ensure_dir(OUT_DIR)
    for name, generator in (("smooth.png", smooth_scene), ("texture.png", textured_scene),
                            ("document.png", document_page)):
        path = write_image(os.path.join(OUT_DIR, name), generator())
        print(f"dibuat: {path}")


if __name__ == "__main__":
    main()
