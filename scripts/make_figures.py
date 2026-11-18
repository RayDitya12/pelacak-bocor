"""Gambar untuk proposal: diagram alur, arsitektur, bukti visual, dan plot ketahanan.

Semua gambar digambar dengan PIL dari data hasil pengujian di results/, bukan
dikarang, sehingga angka yang tampil pada dokumen sama dengan yang dihasilkan
scripts/run_tests.py dan scripts/run_pdf_tests.py.

Jalankan:  python scripts/make_figures.py
"""

from __future__ import annotations

import csv
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "proposal", "gambar")
FONT_DIR = "C:/Windows/Fonts"
SKALA = 2
TINTA = (26, 30, 38)
AKSEN = (31, 79, 168)
GARIS = (198, 206, 219)
LATAR = (246, 248, 251)
KARTU = (255, 255, 255)
HIJAU = (15, 122, 83)
MERAH = (181, 85, 26)


def font(besar, tebal=False):
    nama = "timesbd.ttf" if tebal else "times.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, nama), int(besar * SKALA))


def kanvas(lebar, tinggi, warna=KARTU):
    img = Image.new("RGB", (lebar * SKALA, tinggi * SKALA), warna)
    return img, ImageDraw.Draw(img)


def teks(d, xy, isi, besar=11, warna=TINTA, tebal=False, tengah=None):
    f = font(besar, tebal)
    x, y = xy[0] * SKALA, xy[1] * SKALA
    if tengah is not None:
        w = d.textlength(isi, font=f)
        x = tengah * SKALA - w / 2
    d.text((x, y), isi, font=f, fill=warna)


def kotak(d, xy, label, besar=11, warna=KARTU, garis=GARIS, tebal_teks=False,
          warna_teks=TINTA, tinggi_teks=None):
    box = [c * SKALA for c in xy]
    d.rounded_rectangle(box, radius=6 * SKALA, fill=warna, outline=garis,
                        width=max(1, int(1.2 * SKALA)))
    baris = label.split("\n")
    tinggi = tinggi_teks or (xy[3] - xy[1])
    mulai = xy[1] + tinggi / 2 - len(baris) * besar * 0.72
    for i, b in enumerate(baris):
        teks(d, (0, mulai + i * besar * 1.5), b, besar, warna_teks, tebal_teks,
             tengah=(xy[0] + xy[2]) / 2)


def panah(d, awal, akhir, warna=AKSEN):
    d.line([awal[0] * SKALA, awal[1] * SKALA, akhir[0] * SKALA, akhir[1] * SKALA],
           fill=warna, width=int(1.6 * SKALA))
    dx, dy = akhir[0] - awal[0], akhir[1] - awal[1]
    panjang = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / panjang, dy / panjang
    for sisi in (-1, 1):
        d.line([akhir[0] * SKALA, akhir[1] * SKALA,
                (akhir[0] - 5 * ux + 3 * sisi * uy) * SKALA,
                (akhir[1] - 5 * uy - 3 * sisi * ux) * SKALA], fill=warna,
               width=int(1.6 * SKALA))


def alur_metode():
    img, d = kanvas(690, 118)
    tahap = ["Analisis\nkebutuhan\nkeamanan", "Kajian metode\ndan purwarupa\nawal",
             "Perancangan\nmodul dan\npayload", "Implementasi\nmodul dan\nantarmuka",
             "Pengujian\nmatriks\nterukur", "Evaluasi dan\npenyempurnaan"]
    lebar, gap = 100, 14
    for i, label in enumerate(tahap):
        x = 12 + i * (lebar + gap)
        kotak(d, (x, 26, x + lebar, 84), label, 10.5,
              warna=LATAR if i % 2 else KARTU)
        if i < len(tahap) - 1:
            panah(d, (x + lebar, 55), (x + lebar + gap, 55))
    d.line([12 * SKALA, 100 * SKALA, 676 * SKALA, 100 * SKALA], fill=GARIS,
           width=SKALA)
    panah(d, (600, 100), (600, 86), warna=MERAH)
    teks(d, (12, 103), "Umpan balik terukur: setiap tahap diuji dan hasil pengujian "
                       "menentukan perubahan pada tahap sebelumnya", 9.5, (90, 99, 112))
    img.save(os.path.join(OUT, "gambar_1_alur_metode.png"))


def arsitektur():
    img, d = kanvas(690, 300)
    d.rectangle([12 * SKALA, 12 * SKALA, 678 * SKALA, 128 * SKALA], outline=GARIS,
                width=SKALA)
    teks(d, (20, 16), "SISI PENYELENGGARA (kunci master tidak pernah keluar)", 9.5,
         AKSEN, tebal=True)
    kotak(d, (24, 34, 150, 78), "Materi induk\nPDF / PNG / JPG", 10.5, warna=LATAR)
    kotak(d, (178, 34, 330, 78), "Modul penyemat\ncore.py · payload.py\npdf.py", 10.5)
    kotak(d, (358, 34, 500, 78), "Modul penerbit\nissue.py (daftar\npenerima)", 10.5)
    kotak(d, (528, 34, 666, 78), "Antarmuka web\nweb/app.py (Flask)", 10.5)
    kotak(d, (178, 92, 330, 122), "Kunci\nkeys/master.key", 10, warna=LATAR)
    kotak(d, (358, 92, 500, 122), "Jejak audit\nledger.csv · roster.csv", 10, warna=LATAR)
    panah(d, (150, 56), (178, 56))
    panah(d, (330, 56), (358, 56))
    panah(d, (500, 56), (528, 56))
    panah(d, (270, 92), (270, 78))
    panah(d, (440, 78), (440, 92))

    d.rectangle([12 * SKALA, 150 * SKALA, 678 * SKALA, 196 * SKALA], outline=GARIS,
                width=SKALA)
    teks(d, (20, 154), "BERKAS YANG BEREDAR (hanya membawa nomor, tanpa nama)", 9.5,
         MERAH, tebal=True)
    kotak(d, (24, 172, 240, 192), "101_Kelas_A.pdf · 102_Kelas_B.pdf · ...", 10)
    panah(d, (560, 128), (300, 172), warna=MERAH)

    d.rectangle([12 * SKALA, 214 * SKALA, 678 * SKALA, 288 * SKALA], outline=GARIS,
                width=SKALA)
    teks(d, (20, 218), "PENELUSURAN (di sisi penyelenggara, dengan kunci master yang "
                       "sama)", 9.5, AKSEN, tebal=True)
    kotak(d, (24, 240, 170, 282), "Berkas beredar\n(screenshot / JPEG /\npotong)", 10,
         warna=LATAR)
    kotak(d, (198, 240, 330, 282), "Modul ekstraksi\ncore.extract_*\n+ resync.py", 10.5)
    kotak(d, (358, 240, 486, 282), "Koreksi RS(8,4)\ndan verifikasi\nHMAC + voting", 10.5)
    kotak(d, (514, 240, 666, 282), "Keputusan:\nnomor penerima\ndan label kelas", 10.5,
         warna=(230, 245, 238), garis=HIJAU, warna_teks=(12, 90, 60), tebal_teks=True)
    panah(d, (170, 261), (198, 261))
    panah(d, (330, 261), (358, 261))
    panah(d, (486, 261), (514, 261))
    img.save(os.path.join(OUT, "gambar_2_arsitektur.png"))


def alur_sinyal():
    img, d = kanvas(690, 214)
    teks(d, (12, 8), "PENYISIPAN", 10.5, AKSEN, tebal=True)
    kotak(d, (12, 26, 96, 68), "Citra BGR\n/ raster PDF", 9.5, warna=LATAR)
    kotak(d, (112, 26, 196, 68), "YCrCb,\nkanal Y", 9.5)
    kotak(d, (212, 26, 300, 68), "DWT db2\nlevel-1 → LL", 9.5)
    kotak(d, (316, 26, 410, 68), "Kisi sel\n96×96 koef.", 9.5)
    kotak(d, (426, 26, 530, 68), "Korelasi 32\nblok chip 4×4", 9.5)
    kotak(d, (546, 26, 678, 68), "QIM relatif →\nkoreksi 3 pass", 9.5)
    for x0, x1 in ((96, 112), (196, 212), (300, 316), (410, 426), (530, 546)):
        panah(d, (x0, 47), (x1, 47))
    kotak(d, (316, 80, 530, 104), "payload 64 bit = ID 2 B + HMAC 2 B + paritas RS 4 B, "
                                  "diulang pada 32 sel", 9.5, warna=(234, 240, 251))
    panah(d, (423, 80), (423, 68))

    teks(d, (12, 118), "PEMBACAAN", 10.5, MERAH, tebal=True)
    kotak(d, (12, 136, 96, 178), "Berkas\nberedar", 9.5, warna=LATAR)
    kotak(d, (112, 136, 214, 178), "DWT db2 →\nLL, std global", 9.5)
    kotak(d, (230, 136, 330, 178), "Korelasi +\npenguraian QIM", 9.5)
    kotak(d, (346, 136, 446, 178), "RS(8,4) lalu\ncek HMAC/SHA-256", 9.5)
    kotak(d, (462, 136, 552, 178), "Voting 32\nsel", 9.5)
    kotak(d, (568, 136, 678, 178), "Nomor penerima\natau tolak", 9.5,
         warna=(230, 245, 238), garis=HIJAU)
    for x0, x1 in ((96, 112), (214, 230), (330, 346), (446, 462), (552, 568)):
        panah(d, (x0, 157), (x1, 157), warna=MERAH)
    teks(d, (12, 190), "Lebar kisi QIM ditentukan oleh simpangan baku seluruh subband LL "
                       "sehingga tetap sama saat dibaca; pola chip berjumlah nol membuat "
                       "geser kecerahan tidak mengubah korelasi.", 9.5, (90, 99, 112))
    img.save(os.path.join(OUT, "gambar_3_alur_sinyal.png"))


def bukti_kualitas():
    sumber = os.path.join(ROOT, "results")
    nama = [os.path.join(ROOT, "assets", "samples", "document.png"),
            os.path.join(sumber, "document_bertanda.png"),
            os.path.join(sumber, "document_selisih.png")]
    label = ["(a) Materi asal", "(b) Setelah disemat (PSNR 38,48 dB)",
             "(c) Selisih diperkuat 8×"]
    kotak_lebar = 200
    img, d = kanvas(690, 236)
    for i, (berkas, teks_label) in enumerate(zip(nama, label)):
        citra = Image.open(berkas).convert("RGB")
        tinggi = int(kotak_lebar * citra.height / citra.width)
        citra = citra.resize((kotak_lebar * SKALA, tinggi * SKALA), Image.LANCZOS)
        x = 24 + i * (kotak_lebar + 30)
        img.paste(citra, (x * SKALA, 20 * SKALA))
        d.rectangle([x * SKALA, 20 * SKALA, (x + kotak_lebar) * SKALA,
                     (20 + tinggi) * SKALA], outline=GARIS, width=SKALA)
        teks(d, (0, 22 + tinggi), teks_label, 9.5, TINTA, tengah=x + kotak_lebar / 2)
    img.save(os.path.join(OUT, "gambar_4_kualitas.png"))


def plot_ketahanan():
    data = {}
    with open(os.path.join(ROOT, "results", "serangan.csv"), encoding="utf-8") as fh:
        for baris in csv.DictReader(fh):
            persen = 100 * int(baris["sel_valid"]) / int(baris["sel_total"])
            data.setdefault(baris["serangan"], {})[baris["citra"]] = persen
    urutan = [k for k, _ in sorted(data.items(), key=lambda item: -max(item[1].values()))]
    warna = {"smooth": AKSEN, "texture": HIJAU, "document": MERAH}
    kiri, bawah, tinggi_plot, lebar_plot = 52, 262, 210, 618
    img, d = kanvas(690, 300)
    teks(d, (kiri, 6), "Bagian sidik jari yang lolos verifikasi per serangan "
                       "(persen dari 25 sel)", 10, TINTA, tebal=True)
    for tick in range(0, 101, 20):
        y = bawah - tinggi_plot * tick / 100
        d.line([kiri * SKALA, y * SKALA, (kiri + lebar_plot) * SKALA, y * SKALA],
               fill=GARIS, width=SKALA if tick else int(1.6 * SKALA))
        teks(d, (kiri - 26, y - 6), str(tick), 9, (90, 99, 112))
    grup = lebar_plot / len(urutan)
    for i, serangan in enumerate(urutan):
        for j, citra in enumerate(("smooth", "texture", "document")):
            nilai = data[serangan].get(citra, 0)
            x0 = kiri + i * grup + 4 + j * (grup - 8) / 3
            d.rectangle([x0 * SKALA, (bawah - tinggi_plot * nilai / 100) * SKALA,
                         (x0 + (grup - 8) / 3 - 1.5) * SKALA, bawah * SKALA],
                        fill=warna[citra])
        for k, harfiah in enumerate(serangan.split("_")):
            teks(d, (0, bawah + 6 + k * 11), harfiah, 8, TINTA, tengah=kiri + i * grup + grup / 2)
    x = kiri + lebar_plot - 150
    for j, citra in enumerate(("smooth", "texture", "document")):
        d.rectangle([(x + j * 52) * SKALA, 8 * SKALA, (x + j * 52 + 9) * SKALA, 17 * SKALA],
                    fill=warna[citra])
        teks(d, (x + 13 + j * 52, 7), citra, 9, TINTA)
    img.save(os.path.join(OUT, "gambar_5_ketahanan.png"))


def plot_pdf():
    log = os.path.join(ROOT, "results", "log_run_pdf.txt")
    baris = []
    with open(log, encoding="utf-8") as fh:
        for teks_baris in fh:
            kolom = teks_baris.split()
            if len(kolom) >= 3 and "/" in kolom[-1]:
                valid, total = kolom[-1].split("/")
                baris.append((kolom[0], 100 * int(valid) / int(total), kolom[1]))
    kiri, bawah, tinggi_plot, lebar_plot = 52, 250, 200, 618
    img, d = kanvas(690, 292)
    teks(d, (kiri, 6), "Halaman PDF hasil semat: bagian yang lolos verifikasi per "
                       "serangan (dari 32 sel)", 10, TINTA, tebal=True)
    for tick in range(0, 101, 20):
        y = bawah - tinggi_plot * tick / 100
        d.line([kiri * SKALA, y * SKALA, (kiri + lebar_plot) * SKALA, y * SKALA],
               fill=GARIS, width=SKALA if tick else int(1.6 * SKALA))
        teks(d, (kiri - 26, y - 6), str(tick), 9, (90, 99, 112))
    grup = lebar_plot / len(baris)
    for i, (serangan, persen, pulih) in enumerate(baris):
        x0 = kiri + i * grup + 6
        d.rectangle([x0 * SKALA, (bawah - tinggi_plot * persen / 100) * SKALA,
                     (x0 + grup - 12) * SKALA, bawah * SKALA],
                    fill=HIJAU if pulih == "YA" else MERAH)
        for k, harfiah in enumerate(serangan.split("_")):
            teks(d, (0, bawah + 6 + k * 11), harfiah, 8, TINTA, tengah=kiri + i * grup + grup / 2)
    d.rectangle([500 * SKALA, 8 * SKALA, 509 * SKALA, 17 * SKALA], fill=HIJAU)
    teks(d, (512, 7), "identitas dipulihkan", 9, TINTA)
    d.rectangle([500 * SKALA, 22 * SKALA, 509 * SKALA, 31 * SKALA], fill=MERAH)
    teks(d, (512, 21), "gagal", 9, TINTA)
    img.save(os.path.join(OUT, "gambar_6_pdf.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    alur_metode()
    arsitektur()
    alur_sinyal()
    bukti_kualitas()
    plot_ketahanan()
    plot_pdf()
    print("gambar proposal ditulis ke", OUT)


if __name__ == "__main__":
    main()
