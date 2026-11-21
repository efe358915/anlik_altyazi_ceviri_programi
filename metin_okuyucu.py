"""
Aşama 2: RAM'den okuma + değişim algılama + gecikme ölçümü.

C# aracı artık PNG yerine bolge.json (x, y, w, h) yazar.
Ekran görüntüsünü bu süreç kendisi alır (dosya yok, süreçler arası piksel aktarımı yok).

Gerekli paketler:
    pip install mss numpy rapidocr_onnxruntime pytesseract
(opencv, rapidocr_onnxruntime ile zaten gelir)
"""
import json
import shutil
import time
from pathlib import Path

import cv2
import mss
import numpy as np
import pytesseract
from rapidocr_onnxruntime import RapidOCR

# ---------------- Ayarlar ----------------
BOLGE_DOSYASI = (
    Path(__file__).resolve().parent
    / "SubtitleOverlay" / "bin" / "Debug" / "net11.0-windows" / "bolge.json"
)
POLL_ARALIGI = 0.05        # sn. 0.05 = saniyede 20 kontrol
YAZI_ESIGI = 200           # Bu parlaklıktan açık pikseller "yazı" sayılır (beyaz yazı için)
DEGISIM_ESIGI = 25         # Maskede bu kadar piksel değişirse "değişti" say
MIN_YAZI_PIKSELI = 25      # Bundan az yazı pikseli varsa bölge boş sayılır
EN_FAZLA_BEKLEME = 0.4     # sn. Yazı oturmasa bile en fazla bu kadar bekle
TEK_SATIR = False          # Altyazılar hep tek satırsa True yap (daha hızlı)


def tesseract_bul():
    bulunan_yol = shutil.which("tesseract")
    if bulunan_yol:
        return bulunan_yol

    varsayilan_yollar = (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    )
    for yol in varsayilan_yollar:
        if yol.exists():
            return str(yol)
    return None


def bolge_oku():
    with open(BOLGE_DOSYASI, encoding="utf-8") as f:
        b = json.load(f)
    return {"left": b["x"], "top": b["y"], "width": b["w"], "height": b["h"]}


def yazi_maskesi(bgra):
    """Parlak pikselleri 255, gerisini 0 yapar. Arka plan hareketini eler."""
    gri = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY)
    _, maske = cv2.threshold(gri, YAZI_ESIGI, 255, cv2.THRESH_BINARY)
    return maske


def ocr_icin_hazirla(maske):
    ters = cv2.bitwise_not(maske)  # beyaz zemin, siyah yazı (OCR motorları sever)
    buyuk = cv2.resize(ters, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(buyuk, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)


def ocr_yap(hazir, tesseract_var, rapid):
    """(metin, tesseract_ms, rapid_ms) döndürür."""
    metin, t_ms, r_ms = "", 0.0, 0.0

    if tesseract_var:
        t0 = time.perf_counter()
        ham = pytesseract.image_to_string(
            hazir,
            lang="eng",
            config=f"--psm {'7' if TEK_SATIR else '6'}",
        )
        t_ms = (time.perf_counter() - t0) * 1000
        metin = " ".join(ham.split())

    if not metin:
        t0 = time.perf_counter()
        sonuc, _ = rapid(cv2.cvtColor(hazir, cv2.COLOR_GRAY2BGR))
        r_ms = (time.perf_counter() - t0) * 1000
        if sonuc:
            metin = " ".join(s[1].strip() for s in sonuc).strip()

    return metin, t_ms, r_ms


def main():
    try:
        bolge = bolge_oku()
    except FileNotFoundError:
        print(f"[HATA] '{BOLGE_DOSYASI}' bulunamadı! Önce C# aracıyla ekran bölgesini seçin.")
        return

    tesseract_yolu = tesseract_bul()
    if tesseract_yolu:
        pytesseract.pytesseract.tesseract_cmd = tesseract_yolu
    tesseract_var = bool(tesseract_yolu)

    # Modeller BİR KEZ yüklenir (döngü içinde değil)
    rapid = RapidOCR(use_text_det=not TEK_SATIR)

    # Isınma turu: ilk gerçek OCR çağrısı yavaş olmasın
    ocr_yap(np.full((40, 200), 255, dtype=np.uint8), tesseract_var, rapid)

    print(f"[BİLGİ] Bölge: {bolge} | Tesseract: {'var' if tesseract_var else 'yok'} | Çıkış: Ctrl+C")

    sct = mss.mss()
    onceki = None      # bir önceki karenin maskesi
    okunan = None      # en son OCR'a giden maske
    ilk_degisim = None # değişimi ilk fark ettiğimiz an
    son_metin = None

    try:
        while True:
            t0 = time.perf_counter()

            ham = np.asarray(sct.grab(bolge))  # RAM'den, dosya yok (BGRA)
            t1 = time.perf_counter()

            maske = yazi_maskesi(ham)
            if okunan is None:  # ilk kare: boş ekranla kıyasla
                okunan = np.zeros_like(maske)
                onceki = maske
            fark_okunan = cv2.countNonZero(cv2.bitwise_xor(maske, okunan))
            fark_onceki = cv2.countNonZero(cv2.bitwise_xor(maske, onceki))
            onceki = maske
            t2 = time.perf_counter()

            if fark_okunan > DEGISIM_ESIGI:
                if ilk_degisim is None:
                    ilk_degisim = t0

                oturdu = fark_onceki <= DEGISIM_ESIGI
                zaman_asimi = (t0 - ilk_degisim) > EN_FAZLA_BEKLEME

                if oturdu or zaman_asimi:
                    if cv2.countNonZero(maske) < MIN_YAZI_PIKSELI:
                        metin, t_tes, t_rap = "", 0.0, 0.0  # bölge boş, OCR çalıştırma
                    else:
                        metin, t_tes, t_rap = ocr_yap(
                            ocr_icin_hazirla(maske), tesseract_var, rapid
                        )
                    t3 = time.perf_counter()
                    okunan = maske

                    if metin != son_metin:
                        son_metin = metin
                        print("-" * 40)
                        print(f"Okunan Metin : {metin or '[altyazı yok]'}")
                        print("-" * 40)
                        print(f"Yakalama      : {(t1 - t0) * 1000:.1f} ms")
                        print(f"Maske + fark  : {(t2 - t1) * 1000:.1f} ms")
                        if tesseract_var:
                            print(f"Tesseract     : {t_tes:.1f} ms")
                        if t_rap > 0:
                            print(f"RapidOCR      : {t_rap:.1f} ms")
                        print(f"Değişimi görmekten metne: {(t3 - ilk_degisim) * 1000:.1f} ms")

                    ilk_degisim = None

            kalan = POLL_ARALIGI - (time.perf_counter() - t0)
            if kalan > 0:
                time.sleep(kalan)

    except KeyboardInterrupt:
        print("\n[BİLGİ] Durduruldu.")
    finally:
        sct.close()


if __name__ == "__main__":
    main()
