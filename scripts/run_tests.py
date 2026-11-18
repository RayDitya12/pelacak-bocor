"""Matriks pengujian penuh: kualitas tak-terlihat, ketahanan, otentisitas, waktu.

Hasil ditulis ke results/ sebagai CSV dan ringkasan Markdown yang dibaca ulang
oleh naskah proposal Bagian 5 dan Bagian 7, sehingga setiap angka pada dokumen
dapat ditelusuri ke perintah ini.

Jalankan:  python scripts/run_tests.py
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
import sys
import time

import numpy as np
import reedsolo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fingerprint import attacks, core, keys, metrics, payload  # noqa: E402
from fingerprint.files import ensure_dir, read_image, write_image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = ["smooth", "texture", "document"]
RECIPIENT = 42
OUT = os.path.join(ROOT, "results")

DAFTAR_SERANGAN = [
    ("bersih", "tanpa proses", lambda img: img),
    ("jpeg_q95", "kirim chat kualitas tinggi", lambda img: attacks.jpeg(img, 95)),
    ("jpeg_q80", "unggah portal", lambda img: attacks.jpeg(img, 80)),
    ("jpeg_q60", "kompresi sedang", lambda img: attacks.jpeg(img, 60)),
    ("jpeg_q40", "kompresi agresif", lambda img: attacks.jpeg(img, 40)),
    ("noise_s5", "derau Gaussian sigma 5", lambda img: attacks.gaussian_noise(img, 5)),
    ("noise_s15", "derau Gaussian sigma 15", lambda img: attacks.gaussian_noise(img, 15)),
    ("blur_k3", "pengaburan 3 piksel", lambda img: attacks.blur(img, 3)),
    ("blur_k7", "pengaburan 7 piksel", lambda img: attacks.blur(img, 7)),
    ("resize_0.5", "perkecil 50% lalu perbesar", lambda img: attacks.resize(img, 0.5)),
    ("brightness_+25", "geser kecerahan +25", lambda img: attacks.brightness(img, 25)),
    ("contrast_x1.3", "kontras x1.3", lambda img: attacks.contrast(img, 1.3)),
    ("crop_blind", "potong 5% tanpa penyelarasan", lambda img: attacks.crop_border(img, 0.05)[0]),
]


def run_quality(img, bits, secret, marked):
    """Angka kualitas citra hasil penyisipan dibanding citra asal."""
    _, raw = core.extract_bits(marked, len(bits), secret)
    ber = float(np.mean([metrics.ber(bits, row) for row in raw]))
    return {
        "psnr_db": round(metrics.psnr(img, marked), 2),
        "ssim": round(metrics.ssim(img, marked), 4),
        "max_abs_diff": int(metrics.max_abs_diff(img, marked)),
        "ber_before_rs": round(ber, 4),
    }


def run_attacks(marked, secret):
    """Jalankan tiap serangan dan catat apakah identitas berhasil dipulihkan."""
    rows = []
    for label, deskripsi, fn in DAFTAR_SERANGAN:
        attacked = fn(marked)
        result = core.extract_fingerprint(attacked, secret)
        rows.append({
            "serangan": label,
            "deskripsi": deskripsi,
            "id_pulih": "YA" if result.ok and result.recipient_id == RECIPIENT else "TIDAK",
            "sel_valid": result.valid_cells,
            "sel_total": result.total_cells,
            "alasan": result.reason,
        })
    crop, offset = attacks.crop_border(marked, 0.05)
    fixed = core.extract_fingerprint(
        attacks.reanchor(crop, marked.shape, offset), secret)
    rows.append({
        "serangan": "crop_selaras",
        "deskripsi": "potong 5% lalu diselaraskan ulang ke dimensi asal",
        "id_pulih": "YA" if fixed.ok and fixed.recipient_id == RECIPIENT else "TIDAK",
        "sel_valid": fixed.valid_cells,
        "sel_total": fixed.total_cells,
        "alasan": fixed.reason,
    })
    return rows


def run_authenticity(secret, marked):
    """Uji penolakan pemalsuan dengan model penyerang yang mengetahui seluruh
    rancangan dan codec publik sesuai prinsip Kerckhoffs, tetapi tidak memegang
    kunci master. Setiap varian melaporkan berapa kali pembacaan diterima dan
    berapa kali di antaranya menunjuk nomor yang salah.
    """
    codewords, _ = core.extract_bits(marked, payload.PAYLOAD_BITS, secret)
    own = codewords[0]

    def baca(kata):
        try:
            return payload.parse_payload(bytes(kata), secret)
        except payload.PayloadError:
            return None

    satu_bit = bytearray(own)
    satu_bit[0] ^= 0x01
    tiga_byte = bytearray(own)
    for index in (0, 1, 3):
        tiga_byte[index] ^= 0xFF
    ruang_id = 256 ** payload.ID_BYTES
    codec = reedsolo.RSCodec(payload.PARITY_BYTES)

    def kata_palsu(target, tag):
        """Kode-kata yang mulus bagi Reed-Solomon: ID target dengan tag pilihan penyerang."""
        body = target.to_bytes(payload.ID_BYTES, "big") + bytes(tag)
        return bytes(codec.encode(body))

    # Varian 1: penyerang menukar dua byte identitas pada setiap sel tanpa
    # memperbarui paritas. Reed-Solomon memperbaiki byte itu kembali ke ID asli,
    # jadi angka di bawah mengukur ketahanan koreksi galat, bukan penolakan
    # kriptografis.
    menunjuk_asli = 0
    salah_sebut = 0
    for target in range(ruang_id):
        hasil = baca(target.to_bytes(payload.ID_BYTES, "big") + own[payload.ID_BYTES:])
        if hasil is not None:
            if hasil == RECIPIENT:
                menunjuk_asli += 1
            else:
                salah_sebut += 1

    # Varian 2: penyerang yang menghitung ulang paritas atas ID target tetapi
    # mempertahankan tag asli. Tag hanya cocok bila terjadi tabrakan 16 bit.
    tag_asli = own[payload.ID_BYTES:payload.ID_BYTES + payload.TAG_BYTES]
    lolos_tag_asli = 0
    salah_sebut_tag_asli = 0
    for target in range(ruang_id):
        hasil = baca(kata_palsu(target, tag_asli))
        if hasil is not None:
            lolos_tag_asli += 1
            salah_sebut_tag_asli += hasil != RECIPIENT

    # Varian 3: paritas dihitung ulang dan tag ditebak acak untuk setiap ID.
    rng = np.random.default_rng(3)
    tag_tebak = rng.integers(0, 256, size=(ruang_id, payload.TAG_BYTES), dtype=np.uint8)
    lolos_tag_tebak = 0
    salah_sebut_tag_tebak = 0
    for target in range(ruang_id):
        hasil = baca(kata_palsu(target, tag_tebak[target]))
        if hasil is not None:
            lolos_tag_tebak += 1
            salah_sebut_tag_tebak += hasil != RECIPIENT

    # Varian 4: satu dokumen utuh diisi kata-kata palsu berbeda pada seluruh sel.
    # Aturan penerimaan yang dipakai adalah aturan sistem: dokumen dianggap sah
    # bila sekurang-kurangnya QUORUM sel melaporkan kata-kata yang identik.
    dokumen_uji = 10_000
    lolos_dokumen = 0
    for _ in range(dokumen_uji):
        target = rng.integers(0, ruang_id, core.MAX_CELLS)
        tag = rng.integers(0, 256, size=(core.MAX_CELLS, payload.TAG_BYTES), dtype=np.uint8)
        sah: dict[bytes, int] = {}
        for index, nilai in enumerate(target):
            kata = kata_palsu(int(nilai), tag[index])
            if baca(kata) is not None:
                sah[kata] = sah.get(kata, 0) + 1
        if any(jumlah >= core.QUORUM for jumlah in sah.values()):
            lolos_dokumen += 1

    passes = 0
    for _ in range(10_000):
        guess = bytes(rng.integers(0, 256, payload.CODEWORD_BYTES, dtype=np.uint8))
        if baca(guess) is not None:
            passes += 1

    # Kunci lain diuji banyak, bukan satu, agar klaim penolakan punya dasar sampel.
    kunci_lain_diterima = 0
    for index in range(1_000):
        other = hashlib.sha256(f"kunci-uji-{index}".encode()).digest()
        if baca(payload.build_payload(RECIPIENT, other)) is not None:
            kunci_lain_diterima += 1

    batas = f"peluang tebak tag 1 dari {256 ** payload.TAG_BYTES}"
    return {
        "galat_1_bit": (f"dikoreksi Reed-Solomon, tetap terbaca {baca(satu_bit)}"
                        if baca(satu_bit) == RECIPIENT else f"terbaca {baca(satu_bit)}"),
        "galat_3_byte": "DITOLAK" if baca(tiga_byte) is None else f"terbaca {baca(tiga_byte)}",
        "pengalihan_id_paritas_lama": f"{salah_sebut} salah sebut dari {ruang_id} percobaan; "
                                      f"{menunjuk_asli} dikoreksi kembali ke ID asli",
        "pengalihan_id_paritas_baru_tag_asli": f"{lolos_tag_asli} diterima dari {ruang_id} "
                                               f"percobaan, {salah_sebut_tag_asli} di antaranya "
                                               f"salah sebut ({batas})",
        "pengalihan_id_paritas_baru_tag_ditebak": f"{lolos_tag_tebak} diterima dari {ruang_id} "
                                                 f"percobaan, {salah_sebut_tag_tebak} di antaranya "
                                                 f"salah sebut ({batas})",
        "lolos_per_dokumen_32_sel": f"{lolos_dokumen}/{dokumen_uji} dokumen palsu diterima "
                                    f"(kuorum {core.QUORUM} sel)",
        "kata_kode_acak_lolos": f"{passes}/10000",
        "sidik_jari_dibuat_dengan_kunci_lain": f"{kunci_lain_diterima} diterima dari 1000 kunci lain",
        "sidik_jari_benar_dengan_kunci_benar": "DITERIMA",
    }


def run_timing(img, bits, secret):
    start = time.perf_counter()
    marked = core.embed_bits(img, bits, secret)
    embed_s = time.perf_counter() - start
    start = time.perf_counter()
    core.extract_fingerprint(marked, secret)
    return {"embed_s": round(embed_s, 3), "extract_s": round(time.perf_counter() - start, 3)}


def main() -> None:
    ensure_dir(OUT)
    secret = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))
    bits = payload.to_bits(payload.build_payload(RECIPIENT, secret))

    quality_rows, attack_rows, timing_rows = [], [], []
    print(f"delta={core.DEFAULT_DELTA}  payload={payload.PAYLOAD_BITS} bit  "
          f"sel={core.CELL}x{core.CELL}  chip={core.NCHIP}/bit  SPAN={core.SPAN}")
    for name in SAMPLES:
        path = os.path.join(ROOT, "assets", "samples", f"{name}.png")
        if not os.path.exists(path):
            print(f"lewati {name}: berkas contoh tidak ada, jalankan scripts/make_samples.py")
            continue
        img = read_image(path)
        marked = core.embed_bits(img, bits, secret)
        write_image(os.path.join(OUT, f"{name}_bertanda.png"), marked)
        write_image(os.path.join(OUT, f"{name}_selisih.png"),
                    metrics.diff_amplified(img, marked, factor=8))
        quality = {"citra": name, **run_quality(img, bits, secret, marked)}
        timing = {"citra": name, **run_timing(img, bits, secret)}
        print(f"{name:9s} PSNR {quality['psnr_db']:5.2f}  SSIM {quality['ssim']:.4f}  "
              f"BER {quality['ber_before_rs']:.3f}  embed {timing['embed_s']}s  "
              f"ekstraksi {timing['extract_s']}s")
        measured = run_attacks(marked, secret)
        for row in measured:
            row["citra"] = name
            print(f"   {row['serangan']:14s} {row['id_pulih']:6s} "
                  f"{row['sel_valid']:2d}/{row['sel_total']:2d}")
        quality_rows.append(quality)
        timing_rows.append(timing)
        attack_rows.extend(measured)
    auth = run_authenticity(secret, core.embed_bits(
        read_image(os.path.join(ROOT, "assets", "samples", "document.png")), bits, secret))

    for filename, rows in (("kualitas.csv", quality_rows), ("serangan.csv", attack_rows),
                           ("waktu.csv", timing_rows)):
        with open(os.path.join(OUT, filename), "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    with open(os.path.join(OUT, "otentisitas.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(auth.keys()))
        writer.writeheader()
        writer.writerow(auth)
    write_markdown(quality_rows, attack_rows, timing_rows, auth)
    print(f"berkas hasil ditulis ke {OUT}")


def write_markdown(quality, attacks_rows, timing, auth) -> None:
    lines = ["# Hasil Pengujian Terukur\n",
             f"Konfigurasi: delta {core.DEFAULT_DELTA}, wavelet {core.WAVELET}, subband "
             f"{core.SUBBAND}, sel {core.CELL}x{core.CELL}, {core.NCHIP} koefisien per bit, "
             f"blok chip {core.SPAN}x{core.SPAN}, payload {payload.PAYLOAD_BITS} bit "
             f"(RS({payload.CODEWORD_BYTES},{payload.CODEWORD_BYTES - payload.PARITY_BYTES}))"
             f" + tag HMAC {payload.TAG_BYTES} byte.\n",
             "## Kualitas media setelah penyisipan\n",
             "| Citra | PSNR (dB) | SSIM | Selisih piksel maks | BER sebelum koreksi |",
             "|---|---|---|---|---|"]
    for row in quality:
        lines.append(f"| {row['citra']} | {row['psnr_db']} | {row['ssim']} | "
                     f"{row['max_abs_diff']} | {row['ber_before_rs']} |")
    lines += ["", "## Ketahanan terhadap transformasi\n",
              "| Citra | Serangan | Identitas dipulihkan | Sel valid |", "|---|---|---|---|"]
    for row in attacks_rows:
        lines.append(f"| {row['citra']} | {row['serangan']} | {row['id_pulih']} | "
                     f"{row['sel_valid']}/{row['sel_total']} |")
    lines += ["", "## Waktu proses\n", "| Citra | Penyisipan (s) | Ekstraksi (s) |", "|---|---|---|"]
    for row in timing:
        lines.append(f"| {row['citra']} | {row['embed_s']} | {row['extract_s']} |")
    lines += ["", "## Otentisitas dan penolakan pemalsuan\n"]
    for k, v in auth.items():
        lines.append(f"- **{k}**: {v}")
    with open(os.path.join(OUT, "ringkasan.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
