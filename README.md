# Pelacak Bocor

Sidik jari forensik per penerima untuk materi ajar: setiap salinan yang diedarkan
membawa identitas tersembunyi, sehingga naskah yang tersebar bisa ditelusuri kembali
ke penerimanya tanpa mengubah isi, tampilan, atau teks yang bisa disalin.

*Per-recipient forensic fingerprinting for teaching material. Every issued copy carries
a hidden, authenticated identity, so a leaked exam or module can be traced back to the
class or student that received it — invisibly, and without altering the document.*

---

## Ancaman yang dilayani

Pelakunya ada **di dalam daftar penerima**. Berkas tidak bocor karena diretas, tapi
karena seorang penerima mengirim ulangnya — lewat chat, diunggah ke portal, atau
difoto. Karena itu tidak ada yang perlu dirahasiakan dari penerima selain kunci
penyelenggara (prinsip Kerckhoffs), dan yang harus dibangun bukan kerahasiaan media
melainkan **keterbuktian**: bacaan hanya boleh dilaporkan sebagai bukti bila lolos
koreksi galat dan verifikasi tag, kalau tidak sistem harus diam dan menyatakan
"identitas tidak dapat ditentukan".

## Cara kerja

| Lapisan | Isi |
|---|---|
| Domain | DWT `db2` level-1 pada kanal Y (YCrCb), subband LL |
| Penanda | 128 koefisien per bit dalam blok 4x4; tanda pola chip ±1 dan posisi blok diturunkan dari seed berkunci; korelasi → kuantisasi indeks modulasi (QIM) |
| Kisi | sel 96x96 → 25 sel untuk gambar 1024x1024, 32 sel untuk halaman PDF 150 dpi |
| Muatan | 64 bit = ID penerima 2 B + tag HMAC-SHA256 terpotong 2 B + paritas Reed-Solomon RS(8,4) 4 B, diulang pada seluruh sel |
| Pembacaan | koreksi RS → verifikasi HMAC → suara terbanyak antarsel, **kuorum 2 sel** |
| Pemulihan posisi | sapuan fraksi piksel simetris untuk berkas yang terpotong (`resync`) |

Redundansi spasial inilah yang membuat sebagian sel boleh rusak: identitas tetap
dilaporkan selama minimal dua sel berbeda melaporkan kata-kode yang sama.

## Model kunci

Satu-satunya rahasia adalah `keys/master.key` (32 byte). Berkas itu **tidak ada di repo**
dan dibangkitkan otomatis dengan CSPRNG saat pertama kali sistem dijalankan
(`src/fingerprint/keys.py`). Cap yang beredar hanya membawa angka, bukan nama:
pemetaan nomor → penerima disimpan di `results/roster.csv` sisi penyelenggara, yang
juga diabaikan git. Mengganti kunci = mengganti seluruh identitas, jadi kunci lama tidak
bisa dipakai menyusun sidik jari orang lain.

## Mulai cepat

Prasyarat: **Python 3.11+** (32-bit bukan; 64-bit) dan pip yang bisa mengakses PyPI.
Wheel PyMuPDF 2.x dibangun untuk `cp311-abi3`, jadi di Python 3.10 ke bawah pip akan
menarik PyMuPDF 1.x yang belum diuji dengan kode ini.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/make_samples.py        # bahan uji sintetis 1024x1024
python scripts/make_pdf_sample.py     # halaman PDF 150 dpi + salinan bersetifikat (nomor 42)
python scripts/run_tests.py           # kualitas + matriks serangan pada gambar
python scripts/run_pdf_tests.py       # matriks yang sama pada halaman PDF 150 dpi
python scripts/probe_robustness.py    # sapuan delta dan ambang kuorum

python scripts/demo_exam.py           # terbit 4 kelas, lacak salinan yang bocor
python scripts/probe_document_compression.py   # batas kompresi dokumen
python scripts/probe_collusion.py     # gabungan beberapa salinan
python web/app.py                     # antarmuka penyelenggara di http://127.0.0.1:5000
```

## Hasil terukur

Angka di bawah adalah catatan pengukuran kami, dan cara membacanya perlu disebut
terang-terangan: posisi chip, penandaan bit, dan pemilihan sel diturunkan dari
`keys/master.key`, jadi menjalankan ulang dengan kunci lain **menghasilkan angka
per-sel yang berbeda**. Kami mengukur ini dengan sengaja pada clone bersih berkunci
baru: 41 dari 42 baris `results/serangan.csv` menghasilkan verdict yang sama, dan pada
kanal PDF 10 dari 10 baris `results/log_run_pdf.txt` tetap sepakat (gambar PDF 150 dpi
perlu dibangkitkan lebih dulu dengan `scripts/make_pdf_sample.py`, karena berkas itu
keluaran, bukan bahan mentah). Yang bergeser di kanal gambar hanya satu baris, dan ia
duduk tepat di ambang kuorum (JPEG kualitas 40 pada citra `smooth`, 1 sel menjadi 2 sel
sehingga berubah dari "diam" menjadi "terbaca"). Yang persisten adalah kesimpulan per
kanal, bukan hitungan tiap sel — dan karena kunci pengukuran kami tidak kami terbitkan,
reproduksi byte-atas-byte dari tabel ini memang tidak mungkin.

Ringkasan lengkap ada di [`results/ringkasan.md`](results/ringkasan.md), data mentahnya
di `results/serangan.csv`, `results/kualitas.csv`, `results/waktu.csv`,
`results/otentisitas.csv`.

Kualitas setelah penyematan (delta 1,2): PSNR 38,48–47,18 dB, SSIM 0,952–0,9966,
selisih piksel maksimum 5–11. Waktu: semat 0,13–0,33 detik, baca 0,04 detik per materi.

Ketahanan gambar (dari 25 sel, citra `smooth`/`texture`/`document`): JPEG kualitas 80
23–25 sel, JPEG kualitas 60 6–25 sel, pengaburan 7 piksel 17–25 sel, perkecil 50%
23–25 sel, potong 5% yang diselaraskan ulang 15–16 sel. Yang gugur: derau Gaussian
sigma 15 (0/25 pada dua citra), kecerahan +25 pada citra `document` (0/25), kontras
1,3 pada `texture` masih benar walau hanya 7 sel, dan potongan 5% tanpa penyelarasan
(0/16).

Halaman PDF (dari 32 sel): utuh dan JPEG kualitas 80 terbaca penuh 32/32; kompresi
lebih kasar, pengaburan, dan perubahan ukuran masih menghasilkan identitas yang benar
walau sebagian sel gugur; potongan 10% pulih pada 18 sel setelah penyelarasan; geser
kecerahan dan kontras **gagal** pada PDF karena halaman sebagian besar putih sehingga
acuan lebar kisi terpotong.

Otentisitas (terukur, bukan argumen):

| Serangan | Hasil |
|---|---|
| 1 bit galat | dikoreksi Reed-Solomon, tetap terbaca |
| 3 byte galat | DITOLAK |
| Pengalihan ID, paritas lama | 0 salah sebut dari 65.536 percobaan |
| Pengalihan ID, paritas baru + tag asli | 3 diterima dari 65.536, 2 di antaranya salah sebut |
| Pengalihan ID, paritas baru + tag ditebak | 1 diterima dari 65.536, 1 salah sebut |
| Dokumen palsu seluruh selnya | 0/10.000 diterima (kuorum 2 sel) |
| Sidik jari dibuat dengan kunci lain | 0/1.000 diterima |

Peluang sebuah tag acak lolos verifikasi adalah 1 dari 65.536 kata-kode, dan angka
salah sebut di atas konsisten dengan peluang itu. Plafon sistem: 16 bit = 65.536
penerima.

## Batas yang kami ukur sendiri

Dua kanal ini tidak ada di matriks proposal; `scripts/probe_document_compression.py`
dan `scripts/probe_collusion.py` mengukurnya pada keempat salinan demo, dan nol
tuduhan salah muncul di 24 percobaan kanal berat.

- **Kompresi dokumen.** Gabungan resample + JPEG (setara preset "Reduce File Size")
  menyisakan 4 dari 32 sel dan **keempat-empatnya tetap menunjuk kelasnya sendiri**;
  pada 100 dpi + JPEG 40 tersisa 3 sel dan masih benar semua. Batasnya sekitar
  75 dpi + JPEG 60, di mana satu salinan jatuh ke 1 sel sehingga kuorum 2 tidak
  tercapai dan sistem diam. Kompresi dua tingkat (JBIG2/CCITT, halaman diputihkan
  jadi 1-bit) menghapus seluruh bukti (0/32, keempatnya diam).
- **Collusion.** Median atau minimum per piksel dari 2, 3, dan 4 salinan bernomor
  berbeda menghasilkan 0 sel yang lolos verifikasi pada semua kombinasi: bukti
  dihapus, bukan dipindahkan. Jadi penyerang dapat membuat berkasnya tak
  teridentifikasi, tetapi tidak dapat menuduh pihak di luar kelompoknya. Ini juga
  alasan kami menomori per kelas — seluruh penerima di kelas yang sama memegang
  berkas yang identik, jadi tukar-menukar dalam satu kelas tidak menghasilkan bahan
  collusion; menghapus bukti butuh kesepakatan lintas kelas.

## Struktur

```
src/fingerprint/   core.py (semat/baca) payload.py keys.py attacks.py pdf.py resync.py
                   issue.py (terbit massal + roster + ZIP) metrics.py files.py
scripts/           pengukuran, demo, probe batas, generator bahan uji
web/               antarmuka penyelenggara (Flask): terbit, lacak, jejak audit
results/           CSV dan log hasil pengujian yang dikutip di atas
docs/gambar/       diagram alur, arsitektur, dan bukti visual
```

## Yang sengaja tidak dipublikasikan

`keys/`, `results/roster.csv`, `results/label_penerima.csv`, `results/ledger.csv`,
seluruh keluaran run (`web/output/`, `web/uploads/`, `results/demo/`), proposal serta
dokumen resmi panitia lomba (memuat NIM dan NIP), dan skrip jalur penulisan dokumen.
Daftar itu dijaga `.gitignore` dan diperiksa ulang oleh `scripts/cek_repo.py` sebelum
setiap commit.

## Catatan repo

`scripts/make_figures.py` menulis diagram ke `proposal/gambar/` (diregulasi format
lomba), jadi salinan untuk README disimpan di `docs/gambar/`.
