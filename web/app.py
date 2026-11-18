"""Antarmuka web penyemat dan pelacak sidik jari materi digital.

Dua fungsi sesuai alur kerja sebenarnya:
  sematkan  -> unggah PNG/JPG/PDF + nomor penerima -> unduh berkas bersetifikat
  telusuri  -> unggah berkas yang beredar -> sistem menunjuk penerimanya

Setiap operasi dicatat ke results/ledger.csv sebagai jejak audit.
Jalankan:  python web/app.py   lalu buka http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import os
import sys
import time

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fingerprint import attacks, core, issue, keys, metrics, pdf, resync  # noqa: E402
from fingerprint import payload  # noqa: E402
from fingerprint.files import read_image, write_image  # noqa: E402

UPLOAD = os.path.join(ROOT, "web", "uploads")
OUT = os.path.join(ROOT, "web", "output")
LEDGER = os.path.join(ROOT, "results", "ledger.csv")
ROSTER = os.path.join(ROOT, "results", "roster.csv")
LABEL = os.path.join(ROOT, "results", "label_penerima.csv")
os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

app = Flask(__name__)
app.secret_key = keys.load_or_create_key(os.path.join(ROOT, "keys", "web_session.key")).hex()
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
SECRET = keys.load_or_create_key(os.path.join(ROOT, "keys", "master.key"))


def _catat(aksi: str, nama: str, penerima, detail: str) -> None:
    baru = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if baru:
            writer.writerow(["waktu", "aksi", "berkas", "penerima", "keterangan"])
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), aksi, nama, penerima, detail])


def _label_semua() -> dict[str, str]:
    if not os.path.exists(LABEL):
        return {}
    with open(LABEL, encoding="utf-8") as fh:
        return {r[0]: r[1] for r in list(csv.reader(fh))[1:] if len(r) >= 2}


def _simpan_label(nomor: int, label: str) -> None:
    peta = _label_semua()
    peta[str(nomor)] = label
    os.makedirs(os.path.dirname(LABEL), exist_ok=True)
    with open(LABEL, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nomor", "label"])
        writer.writerows(sorted(peta.items(), key=lambda item: int(item[0])))


def _peta_label() -> dict[str, int]:
    """Nomor yang sudah pernah dipakai untuk sebuah nama penerima.

    Nama yang sama harus selalu membawa nomor yang sama. Bila setiap terbitan
    mencetak nomor baru, satu kelas punya dua identitas dan berkas yang dilacak
    bisa menunjuk ke salah satunya, sehingga jejak audit tidak lagi bisa
    dijelaskan ke pihak lain.
    """
    peta: dict[str, int] = {}
    for sumber in (LABEL, ROSTER):
        if not os.path.exists(sumber):
            continue
        with open(sumber, encoding="utf-8") as fh:
            for baris in csv.DictReader(fh):
                label = (baris.get("label") or "").strip()
                nomor = (baris.get("nomor") or "").strip()
                if label and nomor.isdigit():
                    peta.setdefault(label, int(nomor))
    return peta


def _lengkapi_nomor(teks: str) -> str:
    """Isi nomor untuk baris yang hanya menulis nama.

    Penyelenggara berpikir dalam nama kelas, bukan nomor 16 bit, jadi baris
    "Kelas A" tanpa nomor sah. Nomornya diambil dari yang sudah pernah dipakai
    untuk nama itu, baru bila belum pernah dinaikkan dari nomor tertinggi yang
    ada; nomor tetap bisa ditetapkan manual lewat "112,Kelas A".
    """
    baris = [b.strip() for b in teks.replace("\r", "\n").split("\n") if b.strip()]
    peta = _peta_label()
    sudah = [int(b.split(",")[0]) for b in baris
             if "," in b and b.split(",")[0].strip().isdigit()]
    berikutnya = max([*sudah, *peta.values()], default=100) + 1
    hasil = []
    for b in baris:
        if "," in b and b.split(",")[0].strip().isdigit():
            hasil.append(b)
            continue
        hasil.append(f"{peta.get(b, berikutnya)},{b}")
        berikutnya += 1
    return "\n".join(hasil)


@app.route("/", methods=["GET"])
def beranda():
    return render_template("index.html", rows=_riwayat())


@app.route("/sematkan", methods=["POST"])
def sematkan():
    berkas = request.files.get("berkas")
    if not berkas or not berkas.filename:
        flash("Pilih berkas materi terlebih dahulu.", "eror")
        return redirect(url_for("beranda"))
    try:
        penerima = int(request.form.get("penerima", "0"))
    except ValueError:
        penerima = -1
    if not 0 <= penerima <= 65535:
        flash("Nomor identitas harus antara 0 dan 65535.", "eror")
        return redirect(url_for("beranda"))

    asal = os.path.join(UPLOAD, berkas.filename)
    berkas.save(asal)
    nama = os.path.basename(asal)
    if nama.lower().endswith(".pdf"):
        hasil = os.path.join(OUT, nama.rsplit(".", 1)[0] + "_bersetifikat.pdf")
        catatan = pdf.stamp_pdf(asal, hasil, penerima, SECRET)
        detail = f"{len(catatan)} halaman, raster {catatan[0]['lebar']}x{catatan[0]['tinggi']}"
        kualitas = _kualitas_pdf(asal, hasil)
    else:
        image = read_image(asal)
        bits = payload.to_bits(payload.build_payload(penerima, SECRET))
        marked = core.embed_bits(image, bits, SECRET)
        hasil = os.path.join(OUT, nama.rsplit(".", 1)[0] + "_bersetifikat.png")
        write_image(hasil, marked)
        kualitas = {"psnr": round(metrics.psnr(image, marked), 2),
                    "ssim": round(metrics.ssim(image, marked), 4)}
        detail = f"{marked.shape[1]}x{marked.shape[0]} piksel, " \
                 f"{core.extract_fingerprint(marked, SECRET).valid_cells} sel valid"
    _catat("semat", nama, penerima, f"{detail}, PSNR {kualitas['psnr']} dB, "
           f"SSIM {kualitas['ssim']}")
    label = request.form.get("nama", "").strip()
    if label:
        _simpan_label(penerima, label)
    flash(f"Selesai. Nomor {penerima}" + (f" — {label}" if label else "") +
          " sudah tertanam di berkas dan siap diunduh.")
    return redirect(url_for("unduh", nama=os.path.basename(hasil)))


@app.route("/kedarkan", methods=["POST"])
def kedarkan():
    berkas = request.files.get("berkas")
    if not berkas or not berkas.filename:
        flash("Pilih berkas materi yang akan diedarkan.", "eror")
        return redirect(url_for("beranda"))
    try:
        daftar = issue.parse_roster(_lengkapi_nomor(request.form.get("daftar", "")))
    except ValueError as error:
        flash(f"Daftar penerima tidak sah: {error}", "eror")
        return redirect(url_for("beranda"))
    nama = berkas.filename
    asal = os.path.join(UPLOAD, nama)
    berkas.save(asal)
    out_dir = os.path.join(OUT, "terbitan")
    if nama.lower().endswith(".pdf"):
        records = issue.issue_pdf(asal, out_dir, daftar, SECRET)
    else:
        records = issue.issue_images(asal, out_dir, daftar, SECRET)
    issue.write_roster(ROSTER, records)
    issue.bundle_zip(out_dir, records, os.path.join(OUT, "terbitan.zip"))
    _catat("kedarkan", nama, ",".join(str(r["nomor"]) for r in records),
           f"{len(records)} salinan, PSNR terendah {min(r['psnr'] for r in records)} dB")
    flash(f"Selesai — {len(records)} salinan terbit, masing-masing membawa identitas "
          "penerimanya sendiri. Bundel ZIP berisi semuanya sedang terunduh.")
    return redirect(url_for("unduh_zip", nama="terbitan.zip"))


@app.route("/unduh-zip/<nama>")
def unduh_zip(nama: str):
    path = os.path.join(OUT, os.path.basename(nama))
    if not os.path.exists(path):
        return redirect(url_for("beranda"))
    return send_file(path, as_attachment=True, mimetype="application/zip")


@app.route("/telusuri", methods=["POST"])
def telusuri():
    berkas = request.files.get("berkas")
    if not berkas or not berkas.filename:
        flash("Unggah berkas yang ingin ditelusuri.", "eror")
        return redirect(url_for("beranda"))
    asal = os.path.join(UPLOAD, berkas.filename)
    berkas.save(asal)
    nama = os.path.basename(asal)
    bentuk = _bentuk_acuan(request.files.get("acuan"))
    if nama.lower().endswith(".pdf"):
        baris = _telusuri_pdf(asal, bentuk)
    else:
        baris = [_telusuri_gambar(read_image(asal), bentuk)]
    id_penerima = next((r["penerima"] for r in baris if r["penerima"] is not None), None)
    keterangan = "; ".join(
        f"hal {r['halaman']}: {r['penerima'] or '-'} ({r['sel_valid']}/{r['sel_total']})"
        + (f" {r['catatan']}" if r.get("catatan") else "") for r in baris)
    label = (_label_semua().get(str(id_penerima)) or issue.label_for(ROSTER, id_penerima)
             if id_penerima is not None else None)
    _catat("telusuri", nama, id_penerima, keterangan)
    return render_template("index.html", hasil=_penjelasan(baris, id_penerima, label),
                           rows=_riwayat())


def _penjelasan(baris: list[dict], id_penerima, label) -> dict:
    """Terjemahkan hasil ekstraksi menjadi bahasa penyelenggara.

    Angka sel tidak berarti apa pun bagi yang membaca hasil; yang dibutuhkan
    adalah jawaban tegas atas berkas ini dari siapa, seberapa yakin, dan apa
    langkah berikutnya bila tidak dapat dibaca.
    """
    terbaik = max((r["sel_valid"] for r in baris), default=0)
    seluruh = max((r["sel_total"] for r in baris), default=0)
    fraksi = round(100 * terbaik / seluruh) if seluruh else 0
    dikenal = id_penerima is not None
    bagian_terbaca = len([r for r in baris if r["penerima"] is not None])
    if not dikenal:
        utama = "Identitas tidak dapat ditentukan"
        sampingan = "Tidak ada bagian berkas yang lolos verifikasi"
        petunjuk = ("Bila berkas dipotong tidak rata, lampirkan induk materi yang kamu "
                    "edarkan supaya posisinya bisa diselaraskan; atau unggah bagian "
                    "berkas yang lebih utuh.")
    else:
        utama = f"Berkas ini dari {label}" if label else f"Berkas ini membawa nomor {id_penerima}"
        sampingan = (f"Nomor identitas {id_penerima} · terbaca pada {bagian_terbaca} "
                     f"dari {len(baris)} bagian berkas")
        petunjuk = ("Sedikit bagian yang terbaca — cocokkan dengan daftar terbitan "
                    "sebelum menindaklanjuti." if fraksi < 40 else "")
    return {
        "ditemukan": dikenal,
        "utama": utama,
        "sampingan": sampingan,
        "fraksi": fraksi,
        "meter": (f"{terbaik} dari {seluruh} bagian sidik jari terbaca utuh ({fraksi}%)"
                  if terbaik else "Tidak ada bagian sidik jari yang terbaca"),
        "petunjuk": petunjuk,
        "halaman": [{"nama": ("Halaman " if len(baris) > 1 else "Bagian ") + str(r["halaman"]),
                     "penerima": r["penerima"],
                     "sel": f"{r['sel_valid']}/{r['sel_total']}",
                     "catatan": r["catatan"]} for r in baris],
    }


def _bentuk_acuan(acuan):
    """Ambil dimensi berkas asal bila penelusur melampirkannya."""
    if not acuan or not acuan.filename:
        return None
    path = os.path.join(UPLOAD, "acuan_" + acuan.filename)
    acuan.save(path)
    if acuan.filename.lower().endswith(".pdf"):
        return pdf.page_shape(path)
    return read_image(path).shape[:2]


def _row(halaman, result, catatan=""):
    return {"halaman": halaman, "penerima": result.recipient_id,
            "sel_valid": result.valid_cells, "sel_total": result.total_cells,
            "catatan": catatan}


def _telusuri_gambar(image, bentuk):
    result = core.extract_fingerprint(image, SECRET)
    if result.ok or bentuk is None:
        return _row(1, result)
    dipulihkan, fraksi = _selaras(image, bentuk)
    return _row(1, dipulihkan if dipulihkan.ok else result,
                f"selaras {fraksi:.2f}" if dipulihkan.ok else "")


def _selaras(image, bentuk):
    result, fraksi = resync.trace_cropped(image, SECRET, bentuk)
    tinggi, lebar = int(bentuk[0] * fraksi), int(bentuk[1] * fraksi)
    return core.extract_fingerprint(
        attacks.reanchor(image, bentuk, (tinggi, lebar)), SECRET), fraksi


def _telusuri_pdf(path, bentuk):
    rows = []
    for index, page in enumerate(pdf.iter_pages(path)):
        result = core.extract_fingerprint(page, SECRET)
        row = _row(index + 1, result)
        if bentuk is not None and not result.ok:
            dipulihkan, fraksi = _selaras(page, bentuk)
            if dipulihkan.ok:
                row = _row(index + 1, dipulihkan, f"selaras {fraksi:.2f}")
        rows.append(row)
    return rows


@app.route("/unduh/<nama>")
def unduh(nama: str):
    path = os.path.join(OUT, os.path.basename(nama))
    if not os.path.exists(path):
        return redirect(url_for("beranda"))
    return send_file(path, as_attachment=True)


def _kualitas_pdf(asal: str, hasil: str) -> dict:
    before, after = pdf.page_pair(asal, hasil)
    return {"psnr": round(metrics.psnr(before, after), 2),
            "ssim": round(metrics.ssim(before, after), 4)}


def _riwayat() -> list[list[str]]:
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    return list(reversed(rows[1:]))[:12]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
