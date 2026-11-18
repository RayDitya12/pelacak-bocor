"""Metrik imperceptibility dan akurasi pembacaan sidik jari."""

from __future__ import annotations

import cv2
import numpy as np
from skimage.metrics import structural_similarity


def psnr(original: np.ndarray, modified: np.ndarray, peak: float = 255.0) -> float:
    """Peak Signal-to-Noise Ratio dalam dB; makin tinggi makin tak terlihat."""
    mse = float(np.mean((original.astype(np.float64) - modified.astype(np.float64)) ** 2))
    if mse == 0:
        return float("inf")
    return 10.0 * np.log10(peak**2 / mse)


def ssim(original: np.ndarray, modified: np.ndarray) -> float:
    """Struktural similarity indeks, kanal per kanal lalu dirata-ratakan."""
    if original.ndim == 2:
        return float(structural_similarity(original, modified, data_range=255))
    channels = [
        structural_similarity(original[:, :, c], modified[:, :, c], data_range=255)
        for c in range(original.shape[2])
    ]
    return float(np.mean(channels))


def ber(embedded: list[int], extracted: list[int]) -> float:
    """Bit Error Rate: fraksi bit yang berbeda di antara kedua urutan bit."""
    if len(embedded) != len(extracted):
        raise ValueError("panjang urutan bit harus sama")
    if not embedded:
        return float("nan")
    return float(np.mean(np.asarray(embedded) != np.asarray(extracted)))


def nc(embedded: list[int], extracted: list[int]) -> float:
    """Normalized correlation antara watermark biner asli dan hasil baca.

    Bit 0 dipetakan ke -1 agar korelasi tidak jenuh pada payload yang didominasi nol.
    """
    a = np.asarray(embedded, dtype=np.float64) * 2 - 1
    b = np.asarray(extracted, dtype=np.float64) * 2 - 1
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    return float(np.sum(a * b) / denom) if denom else 0.0


def max_abs_diff(original: np.ndarray, modified: np.ndarray) -> int:
    """Selisih piksel terbesar, untuk membuktikan perubahan tidak tampak mata."""
    return int(np.max(np.abs(original.astype(np.int16) - modified.astype(np.int16))))


def diff_amplified(original: np.ndarray, modified: np.ndarray, factor: int = 10) -> np.ndarray:
    """Visualisasi selisih yang diperbesar, dipakai sebagai bukti pada Bagian 7."""
    diff = np.abs(original.astype(np.int16) - modified.astype(np.int16)) * factor
    return np.clip(diff, 0, 255).astype(np.uint8)


def side_by_side(*images: np.ndarray) -> np.ndarray:
    """Tempel beberapa citra BGR sejajar secara horizontal."""
    return cv2.hconcat(images)
