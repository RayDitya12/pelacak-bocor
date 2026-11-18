"""Inti penyisipan dan ekstraksi: DWT subband LL + korelasi chip acak + QIM relatif.

Rancangan
---------
1. Citra BGR -> YCrCb; hanya kanal luma Y yang disentuh agar perubahan tidak
   mudah terlihat mata.
2. DWT level-1 db2 pada Y. Subband LL membawa frekuensi terendah, yaitu suku
   yang paling halus terkuantisasi ulang oleh JPEG, sehingga paling cocok
   menjadi tempat menyimpan sinyal yang harus bertahan setelah kompresi.
3. LL dibagi ke dalam sel berukuran CELL x CELL yang berpangkal tetap di kiri
   atas. Payload 64 bit yang sama diulang pada setiap sel. Redundansi spasial
   inilah yang membuat sebagian sel boleh rusak tanpa mematikan pembacaan.
4. Di dalam tiap sel, koefisien dibagi menjadi 64 kelompok berisi NCHIP
   koefisien yang tersebar acak menurut seed turunan kunci, dan tiap kelompok
   dipasangi pola chip +1/-1 yang jumlah totalnya nol.
5. Yang dikuantisasi adalah korelasi kelompok, C = sum(z * chip) dengan z bagian
   yang telah dikurangi nilai rata-ratanya. Lebar kisi dibuat relatif terhadap
   korelasi silang energi AC kelompok dan simpangan baku seluruh subband:

       C' = QIM(C, bit, delta * sqrt(||z||^2 + (sigma_LL * sqrt(NCHIP))^2))

   Tiga sifat penting ikut diperoleh. Pola chip berjumlah nol membuat geser
   kecerahan (penambahan konstanta seragam) tidak mengubah C sedikit pun. Kisi
   yang berskala sigma_LL membuat perubahan kontras menyeluruh ikut menala
   kisi sehingga pembacaan tetap benar, dan daerah yang sangat halus tetap
   memiliki lebar kisi yang cukup karena suku sigma_LL tidak menuju nol.
6. Koreksi berulang (passes) mengukur selisih tulis-baca akibat pembulatan 8
   bit dan pemotongan rentang piksel, lalu menggeser target penulisan sampai
   citra hasil penyisipan benar-benar terbaca bersih.

Catatan pemilihan metode. Versi awal memakai nilai singular terbesar hasil SVD
tiap blok 8x8 sebagai pembawa, mengikuti praktik umum DWT-SVD. Pendekatan itu
ditinggalkan karena dua cacat terukur: kisi dihitung dari energi blok yang
sendiri berubah setelah penyisipan sehingga kisi saat tulis dan saat baca tidak
sama, dan menurunkan nilai singular dominan dapat menukar urutannya dengan nilai
singular berikutnya sehingga yang terbaca adalah suku yang salah.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np
import pywt

from . import payload as pl
from .keys import derive_seed
from .metrics import ber as _ber

WAVELET = "db2"
CELL = 96
CELLS_LABEL = "cells-v1"
NCHIP = 128
MAX_CELLS = 32
SUBBAND = "LL"
DEFAULT_DELTA = 1.2
REF_MIX = 1.0
CORRECTION_PASSES = 3
QUORUM = 2
LAYOUT_LABEL = "layout-v1"
CHIP_LABEL = "chip-v1"
SPAN = 4


@dataclass
class ExtractionResult:
    """Hasil pembacaan sidik jari dari satu citra."""

    recipient_id: int | None
    valid_cells: int
    total_cells: int
    codeword_votes: dict[bytes, int] = field(default_factory=dict)
    all_bits: list[list[int]] = field(default_factory=list)
    decoded_bits: list[int] | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        """Identitas dilaporkan hanya bila kuorum sel sepakat setelah koreksi Reed-Solomon
        dan verifikasi HMAC."""
        return self.recipient_id is not None

    def mean_ber(self, embedded: list[int]) -> float:
        """Rata-rata bit error rate seluruh sel, diukur sebelum koreksi Reed-Solomon."""
        if not self.all_bits:
            return float("nan")
        return float(np.mean([_ber(embedded, cell) for cell in self.all_bits]))


def group_slots(secret: bytes, bits_needed: int) -> np.ndarray:
    """Indeks koefisien tiap kelompok bit, relatif terhadap pojok kiri atas sel.

    Satu bit dilayani NCHIP koefisien yang dikemas menjadi chip persegi SPAN x
    SPAN. Bentuk utuh ini penting: chip berukuran satu koefisien akan saling
    meniadakan saat citra di-blur, sedangkan blok kecil mempertahankan tanda
    korelasinya selama jendela filter belum melebihi ukuran blok.
    """
    chips = NCHIP // (SPAN * SPAN)
    per_axis = CELL // SPAN
    if bits_needed * chips > per_axis * per_axis:
        raise ValueError("payload terlalu besar untuk satu sel")
    rng = np.random.default_rng(derive_seed(secret, LAYOUT_LABEL))
    picked = rng.permutation(per_axis * per_axis)[: bits_needed * chips]
    picked = picked.reshape(bits_needed, chips)
    rows, cols = picked // per_axis, picked % per_axis
    offsets = np.arange(SPAN)
    rr = (rows[..., None, None] * SPAN + offsets[None, None, :, None])
    cc = (cols[..., None, None] * SPAN + offsets[None, None, None, :])
    return (rr * CELL + cc).reshape(bits_needed, NCHIP)


def chip_patterns(secret: bytes, bits_needed: int) -> np.ndarray:
    """Pola chip +1/-1 berjumlah nol untuk tiap kelompok bit, satu tanda per blok."""
    chips = NCHIP // (SPAN * SPAN)
    rng = np.random.default_rng(derive_seed(secret, CHIP_LABEL))
    halves = np.concatenate([np.ones(chips // 2), -np.ones(chips - chips // 2)])
    signs = np.stack([rng.permutation(halves) for _ in range(bits_needed)])
    return np.repeat(signs, SPAN * SPAN, axis=1)


def cells_for(shape: tuple[int, int], secret: bytes) -> list[tuple[int, int]]:
    """Pojok kiri atas setiap sel yang dipakai, berpangkal kiri atas dan tersebar.

    Semua posisi kisi yang mungkin dihitung, lalu sejumlah MAX_CELLS dipilih
    menurut turunan kunci. Pemilihan acak berkunci ini penting: mengambil
    beberapa sel pertama berarti seluruh cap menumpuk di bagian atas halaman,
    sehingga memotong kepala surat saja sudah cukup menghapus sidik jari.
    Dengan sebaran, potongan di satu wilayah hanya mematikan sebagian sel dan
    suara terbanyak antar sel tetap berjalan.
    """
    rows, cols = shape[0] // CELL, shape[1] // CELL
    if rows < 1 or cols < 1:
        raise ValueError(
            f"citra terlalu kecil: subband {SUBBAND} berukuran {shape}, kurang dari satu sel "
            f"{CELL}x{CELL}. Gunakan citra minimal sekitar 400x400 piksel."
        )
    total = rows * cols
    if total <= MAX_CELLS:
        picked = np.arange(total)
    else:
        rng = np.random.default_rng(derive_seed(secret, CELLS_LABEL))
        picked = np.sort(rng.choice(total, size=MAX_CELLS, replace=False))
    return [(int(i) // cols * CELL, int(i) % cols * CELL) for i in picked]


def _quantize(values: np.ndarray, bit: np.ndarray, step: np.ndarray) -> np.ndarray:
    """Geser nilai ke titik kisi QIM yang mewakili bit."""
    offset = np.where(bit == 1, step / 2.0, 0.0)
    return step * np.round((values - offset) / step) + offset


def _decoded(correl: np.ndarray, step: np.ndarray) -> np.ndarray:
    """Bit hasil pembacaan kisi QIM dari korelasi teramati."""
    near_zero = np.abs(correl - _quantize(correl, np.zeros_like(correl), step))
    near_one = np.abs(correl - _quantize(correl, np.ones_like(correl), step))
    return (near_one < near_zero).astype(np.int8)


def _absolute(slots: np.ndarray, top: int, left: int, width: int) -> np.ndarray:
    """Indeks datar barisan-first dari slot relatif sel ke datar subband utuh.

    Slot disimpan sebagai posisi dalam jendela CELL x CELL, jadi pemetaannya
    harus mengikuti lebar baris subband, bukan sekadar ditambah offset sel.
    """
    return (slots // CELL + top) * width + (slots % CELL + left)


def _correlation(plane: np.ndarray, cells, slots, patterns, delta: float):
    """Hitung korelasi, lebar kisi, dan energi AC tiap kelompok bit pada tiap sel."""
    correl = np.empty((len(cells), len(slots)))
    energy = np.empty_like(correl)
    flat = plane.reshape(-1)
    width = plane.shape[1]
    for row_index, (top, left) in enumerate(cells):
        x = flat[_absolute(slots, top, left, width)]
        z = x - x.mean(axis=1, keepdims=True)
        correl[row_index] = (z * patterns).sum(axis=1)
        energy[row_index] = np.linalg.norm(z, axis=1)
    # Acuan langkah diambil dari simpangan baku seluruh subband, bukan dari
    # energi tiap kelompok. Energi kelompok berubah tepat setelah penyisipan,
    # sehingga kisi yang dihitung darinya tidak lagi sama saat dibaca dan bit
    # menjadi acak. Simpangan baku global nyaris tidak bergeser karena hanya
    # sebagian kecil koefisien yang disentuh, dan ia tetap ikut terskala saat
    # kontras berubah.
    ref = REF_MIX * float(np.std(plane)) * math.sqrt(NCHIP)
    return correl, delta * np.sqrt(energy**2 + ref**2), energy


def _split(image_bgr: np.ndarray):
    """YCbCr lalu DWT level-1; kembalikan kanal penuh, subband, dan bentuk asal.

    Sisi ganjil digenapkan dengan pemantulan lebih dulu. Tanpa itu idwt2 dari
    subband berukuran (n+1)//2 menghasilkan 2 x ((n+1)//2), yaitu satu baris
    lebih banyak daripada citra asal, dan halaman PDF setinggi 1755 piksel
    gagal ditulis kembali.
    """
    ycc = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float64)
    height, width = ycc.shape[:2]
    pad_h, pad_w = height % 2, width % 2
    if pad_h or pad_w:
        ycc = np.pad(ycc, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
    approx, (detail_h, detail_v, detail_d) = pywt.dwt2(ycc[:, :, 0], WAVELET)
    return ycc, {"LL": approx, "LH": detail_h, "HL": detail_v, "HH": detail_d}, (height, width)


def _merge(ycc: np.ndarray, bands: dict[str, np.ndarray],
           shape: tuple[int, int] | None = None) -> np.ndarray:
    """Balikkan DWT, potong kembali ke bentuk asal, kemas menjadi BGR uint8."""
    ycc[:, :, 0] = pywt.idwt2((bands["LL"], (bands["LH"], bands["HL"], bands["HH"])), WAVELET)
    if shape is not None:
        ycc = ycc[: shape[0], : shape[1], :]
    return cv2.cvtColor(np.clip(ycc, 0, 255).round().astype(np.uint8), cv2.COLOR_YCrCb2BGR)


def embed_bits(image_bgr: np.ndarray, bits: list[int], secret: bytes,
               delta: float = DEFAULT_DELTA, subband: str = SUBBAND,
               passes: int = CORRECTION_PASSES) -> np.ndarray:
    """Sisipkan urutan bit ke seluruh sel dengan koreksi berulang; hasil BGR uint8."""
    wanted = np.asarray(bits, dtype=np.int8)[None, :]
    slots = group_slots(secret, len(bits))
    patterns = chip_patterns(secret, len(bits))
    scale = patterns / NCHIP

    ycc, bands, shape = _split(image_bgr)
    source = bands[subband]
    cells = cells_for(source.shape, secret)
    correl, step, _ = _correlation(source, cells, slots, patterns, delta)
    grid = _quantize(correl, wanted, step)
    delta_c = grid - correl

    bias = np.zeros_like(grid)
    marked = image_bgr
    width = source.shape[1]
    for _ in range(max(1, passes)):
        plane = source.copy()
        flat = plane.reshape(-1)
        target = (delta_c - bias)[:, :, None] * scale
        for row_index, (top, left) in enumerate(cells):
            flat[_absolute(slots, top, left, width).reshape(-1)] += (
                target[row_index].reshape(-1)
            )
        bands[subband] = plane
        marked = _merge(ycc.copy(), bands, shape)

        seen, seen_step, _ = _correlation(_split(marked)[1][subband], cells, slots,
                                          patterns, delta)
        bias = seen - grid
        if not np.any(_decoded(seen, seen_step) != wanted):
            break
    return marked


def extract_bits(image_bgr: np.ndarray, bits_expected: int, secret: bytes,
                 delta: float = DEFAULT_DELTA, subband: str = SUBBAND,
                 ) -> tuple[list[bytes], list[list[int]]]:
    """Baca payload mentah dari tiap sel: (kode-kata per sel, daftar bit per sel)."""
    slots = group_slots(secret, bits_expected)
    patterns = chip_patterns(secret, bits_expected)
    plane = _split(image_bgr)[1][subband]
    correl, step, _ = _correlation(plane, cells_for(plane.shape, secret), slots, patterns, delta)
    rows = _decoded(correl, step).tolist()
    return [pl.from_bits(row) for row in rows], rows


def extract_fingerprint(image_bgr: np.ndarray, secret: bytes, delta: float = DEFAULT_DELTA,
                        subband: str = SUBBAND) -> ExtractionResult:
    """Ekstraksi buta, koreksi Reed-Solomon, verifikasi HMAC, lalu suara terbanyak antar
    sel dengan kuorum minimum QUORUM sel yang sepakat.
    """
    codewords, raw_bits = extract_bits(image_bgr, pl.PAYLOAD_BITS, secret, delta, subband)

    votes: dict[bytes, int] = {}
    for word in codewords:
        try:
            pl.parse_payload(word, secret)
        except pl.PayloadError:
            continue
        votes[word] = votes.get(word, 0) + 1

    if not votes:
        return ExtractionResult(None, 0, len(codewords), votes, raw_bits,
                                raw_bits[0] if raw_bits else None,
                                "tidak ada sel yang lolos verifikasi HMAC")

    best_word, best_count = max(votes.items(), key=lambda item: item[1])
    if best_count < QUORUM:
        return ExtractionResult(None, best_count, len(codewords), votes, raw_bits,
                                next(iter(raw_bits), None),
                                f"kuorum {QUORUM} sel tidak tercapai, hanya {best_count} "
                                f"sel lolos verifikasi HMAC")
    winner = next(bits for word, bits in zip(codewords, raw_bits) if word == best_word)
    return ExtractionResult(pl.parse_payload(best_word, secret), best_count, len(codewords),
                            votes, raw_bits, winner, "ok")
