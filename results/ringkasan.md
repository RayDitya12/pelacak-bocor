# Hasil Pengujian Terukur

Konfigurasi: delta 1.2, wavelet db2, subband LL, sel 96x96, 128 koefisien per bit, blok chip 4x4, payload 64 bit (RS(8,4)) + tag HMAC 2 byte.

## Kualitas media setelah penyisipan

| Citra | PSNR (dB) | SSIM | Selisih piksel maks | BER sebelum koreksi |
|---|---|---|---|---|
| smooth | 47.18 | 0.9907 | 6 | 0.0006 |
| texture | 46.79 | 0.9966 | 5 | 0.0 |
| document | 38.48 | 0.952 | 11 | 0.0 |

## Ketahanan terhadap transformasi

| Citra | Serangan | Identitas dipulihkan | Sel valid |
|---|---|---|---|
| smooth | bersih | YA | 24/25 |
| smooth | jpeg_q95 | YA | 24/25 |
| smooth | jpeg_q80 | YA | 23/25 |
| smooth | jpeg_q60 | YA | 6/25 |
| smooth | jpeg_q40 | TIDAK | 1/25 |
| smooth | noise_s5 | YA | 16/25 |
| smooth | noise_s15 | TIDAK | 0/25 |
| smooth | blur_k3 | YA | 23/25 |
| smooth | blur_k7 | YA | 20/25 |
| smooth | resize_0.5 | YA | 23/25 |
| smooth | brightness_+25 | YA | 24/25 |
| smooth | contrast_x1.3 | YA | 17/25 |
| smooth | crop_blind | TIDAK | 0/16 |
| smooth | crop_selaras | YA | 15/25 |
| texture | bersih | YA | 25/25 |
| texture | jpeg_q95 | YA | 25/25 |
| texture | jpeg_q80 | YA | 25/25 |
| texture | jpeg_q60 | YA | 25/25 |
| texture | jpeg_q40 | YA | 23/25 |
| texture | noise_s5 | YA | 23/25 |
| texture | noise_s15 | TIDAK | 0/25 |
| texture | blur_k3 | YA | 25/25 |
| texture | blur_k7 | YA | 17/25 |
| texture | resize_0.5 | YA | 25/25 |
| texture | brightness_+25 | YA | 25/25 |
| texture | contrast_x1.3 | YA | 7/25 |
| texture | crop_blind | TIDAK | 0/16 |
| texture | crop_selaras | YA | 16/25 |
| document | bersih | YA | 25/25 |
| document | jpeg_q95 | YA | 25/25 |
| document | jpeg_q80 | YA | 25/25 |
| document | jpeg_q60 | YA | 25/25 |
| document | jpeg_q40 | YA | 25/25 |
| document | noise_s5 | YA | 25/25 |
| document | noise_s15 | YA | 22/25 |
| document | blur_k3 | YA | 25/25 |
| document | blur_k7 | YA | 3/25 |
| document | resize_0.5 | YA | 24/25 |
| document | brightness_+25 | TIDAK | 0/25 |
| document | contrast_x1.3 | YA | 2/25 |
| document | crop_blind | TIDAK | 0/16 |
| document | crop_selaras | YA | 16/25 |

## Waktu proses

| Citra | Penyisipan (s) | Ekstraksi (s) |
|---|---|---|
| smooth | 0.327 | 0.039 |
| texture | 0.131 | 0.043 |
| document | 0.132 | 0.041 |

## Otentisitas dan penolakan pemalsuan

- **galat_1_bit**: dikoreksi Reed-Solomon, tetap terbaca 42
- **galat_3_byte**: DITOLAK
- **pengalihan_id_paritas_lama**: 0 salah sebut dari 65536 percobaan; 65536 dikoreksi kembali ke ID asli
- **pengalihan_id_paritas_baru_tag_asli**: 3 diterima dari 65536 percobaan, 2 di antaranya salah sebut (peluang tebak tag 1 dari 65536)
- **pengalihan_id_paritas_baru_tag_ditebak**: 1 diterima dari 65536 percobaan, 1 di antaranya salah sebut (peluang tebak tag 1 dari 65536)
- **lolos_per_dokumen_32_sel**: 0/10000 dokumen palsu diterima (kuorum 2 sel)
- **kata_kode_acak_lolos**: 0/10000
- **sidik_jari_dibuat_dengan_kunci_lain**: 0 diterima dari 1000 kunci lain
- **sidik_jari_benar_dengan_kunci_benar**: DITERIMA
