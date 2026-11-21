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
YAZI_ESIGI = 200           # Bu parlaklıktan açık pikseller "harf adayı" sayılır (beyaz yazı için)
GEVSEK_ESIGI = 150         # Harfin yanındaki noktalama/ince kenarlar için daha düşük eşik
KOYU_ESIGI = 110           # Harfin çevresindeki "koyu" sayılacak parlaklık sınırı
KOYU_ORAN = 0.6            # Harf çevresinin en az bu kadarı koyu olmalı (kutu/kontur/gölge)
MIN_BILESEN = 2            # En az bu kadar harf benzeri parça yoksa bölge "altyazı yok" sayılır
MAX_BILESEN = 150          # Bundan fazla parlak parça = gürültülü sahne, altyazı değil
MIN_HARF_YUK = 6           # Harf adayının en az piksel yüksekliği
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


_K7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
_KYAKIN = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 9))


def yazi_maskesi(bgra):
    """Sadece "altyazı harfine benzeyen" parlak parçaları tutar, gerisini siler.

    Harf = parlak + makul boyutta + çevresi koyu (altyazı kutusu / kontur / gölge).
    Kar, ışık, patlama, parlak gökyüzü gibi büyük veya çevresi koyu olmayan parlak
    bölgeler elenir; böylece hareketli sahnede yazı yokken OCR'a anlamsız görüntü gitmez.
    Altyazı yoksa tamamen siyah (boş) maske döner.
    """
    gri = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY)
    _, parlak = cv2.threshold(gri, YAZI_ESIGI, 255, cv2.THRESH_BINARY)
    bos = np.zeros_like(parlak)
    if cv2.countNonZero(parlak) < MIN_YAZI_PIKSELI:
        return bos

    n, etiket, stat, _ = cv2.connectedComponentsWithStats(parlak, connectivity=8)
    if n > MAX_BILESEN:
        return bos

    yuk, gen = gri.shape
    w = stat[:, cv2.CC_STAT_WIDTH]
    h = stat[:, cv2.CC_STAT_HEIGHT]
    alan = stat[:, cv2.CC_STAT_AREA]
    uygun = (h >= MIN_HARF_YUK) & (w <= 0.5 * gen) & (alan >= 6) & (alan <= 0.05 * yuk * gen)
    uygun[0] = False  # 0 = arka plan

    temiz = bos.copy()
    gecen = 0
    for i in np.flatnonzero(uygun):
        x, y, bw, bh = stat[i, 0], stat[i, 1], stat[i, 2], stat[i, 3]
        y0, y1 = max(0, y - 4), min(yuk, y + bh + 4)
        x0, x1 = max(0, x - 4), min(gen, x + bw + 4)
        kendi = (etiket[y0:y1, x0:x1] == i).astype(np.uint8)
        # Harfin çevresindeki halka (komşu parlak pikseller hariç) koyu mu?
        halka = (cv2.dilate(kendi, _K7) > 0) & (parlak[y0:y1, x0:x1] == 0)
        if not halka.any():
            continue
        if (gri[y0:y1, x0:x1][halka] < KOYU_ESIGI).mean() < KOYU_ORAN:
            continue
        temiz[y0:y1, x0:x1][kendi > 0] = 255
        gecen += 1

    if gecen < MIN_BILESEN:
        return bos

    # Harflerin hemen yanındaki noktalama (. , ' !) ve ince kenarları geri kat
    yakin = cv2.dilate(temiz, _KYAKIN)
    _, gevsek = cv2.threshold(gri, GEVSEK_ESIGI, 255, cv2.THRESH_BINARY)
    return cv2.bitwise_and(gevsek, yakin)


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

    sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
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
