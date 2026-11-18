# -*- coding: utf-8 -*-
"""Gerbang keamanan repo: periksa isi yang akan masuk commit sebelum push.

Repo ini akan publik dan riwayat commit GitHub tidak bisa ditarik kembali secara
yakin, jadi yang diperiksa bukan direktori kerja melainkan indeks git yang staging
(atau HEAD bila diminta): jalur terlarang, angka pribadi seperti NIM dan NIP, nama
anggota tim, materi kunci, dan path lokal yang membuat repo tidak portabel.
Skrip ini sengaja tidak mencetak nilai yang cocok, hanya lokasinya, supaya hasil
pemeriksaannya sendiri tidak menjadi saluran kebocoran.

Jalankan:  python scripts/cek_repo.py            # periksa indeks yang staging
           python scripts/cek_repo.py --head     # periksa commit terakhir
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TERLARANG = (
    "keys/", "web/uploads/", "web/output/", "results/demo/", "proposal/",
    ".scratch/", "__pycache__/",
    "results/roster.csv", "results/label_penerima.csv", "results/ledger.csv",
    "results/web_server.log", "results/log_run_tests.txt", "results/log_run_demo.txt",
    "review.zip", "PANDUAN_DEMO.md", "scripts/cek_repo_lokal.json",
    "assets/samples/materi_bersetifikat.pdf",
    "scripts/isi_identitas.py", "scripts/make_proposal.py", "scripts/revise_",
    "scripts/kemas_review.py", "scripts/make_kartu_judul.py",
)
# Pola umum saja yang ikut dipublikasikan. Nama orang disimpan di berkas lokal yang
# diabaikan git, supaya daftar hitam itu sendiri tidak menjadi saluran kebocoran.
POLA = {
    "NIM": rb"\b2[45]0[0-9]{7}\b",
    "identitas 18 digit": rb"\b\d{18}\b",
    "kunci heksadesimal": rb"\b[0-9a-fA-F]{64}\b",
    "email": rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "path lokal Windows": rb"(?i)C:\\Users",
}
LOKAL = os.path.join(ROOT, "scripts", "cek_repo_lokal.json")
PLAFON_BERKAS = 45 * 1024 * 1024
PLAFON_TOTAL = 60 * 1024 * 1024


def jalankan(*arg):
    return subprocess.run(arg, cwd=ROOT, capture_output=True, check=True).stdout


def daftar(pakai_head):
    if pakai_head:
        return sorted(jalankan("git", "ls-tree", "-r", "--name-only", "HEAD")
                      .decode("utf-8").splitlines())
    return sorted(jalankan("git", "ls-files").decode("utf-8").splitlines())


def isi(jalur, pakai_head):
    acuan = f"HEAD:{jalur}" if pakai_head else f":{jalur}"
    return jalankan("git", "show", acuan)


def utama():
    pakai_head = "--head" in sys.argv[1:]
    jalur = daftar(pakai_head)
    if not jalur:
        print("indeks kosong, tidak ada yang diperiksa")
        return 1
    cacat, total = [], 0
    pola = dict(POLA)
    if os.path.exists(LOKAL):
        with open(LOKAL, encoding="utf-8") as fh:
            for nama, regex in json.load(fh).items():
                pola[nama] = regex.encode("utf-8")

    for b in jalur:
        if b.startswith(TERLARANG):
            cacat.append(("jalur terlarang", b))
        blob = isi(b, pakai_head)
        total += len(blob)
        if len(blob) > PLAFON_BERKAS:
            cacat.append(("berkas terlalu besar", b, f"{len(blob) / 1e6:.1f} MB"))
        if b"\0" in blob[:8000]:
            continue
        for nama, regex in pola.items():
            if re.search(regex, blob):
                cacat.append(("pola " + nama, b))

    if total > PLAFON_TOTAL:
        cacat.append(("total repo terlalu besar", f"{total / 1e6:.1f} MB"))

    print(f"pemeriksaan {'HEAD' if pakai_head else 'indeks staging'}: "
          f"{len(jalur)} berkas, {total / 1e6:.2f} MB")
    if len(pola) == len(POLA):
        print("CATATAN", "daftar nama pribadi lokal tidak ditemukan, hanya pola umum yang diperiksa")
    for c in cacat:
        print("HITAM", *c)
    print("hasil:", f"ADA {len(cacat)} temuan, jangan push" if cacat
          else "bersih, aman untuk repo publik")
    return 1 if cacat else 0


if __name__ == "__main__":
    sys.exit(utama())
