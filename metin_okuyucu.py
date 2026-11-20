import time
from pathlib import Path
import shutil
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
import pytesseract


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

def altyazi_oku():
    # 1. Adım: Dosyanın Varlığını ve Yolunu Kontrol Etmek
    gorsel_yolu = (
    Path(__file__).resolve().parent
    / "SubtitleOverlay" / "bin" / "Debug" / "net11.0-windows"
    / "secilen_altyazi_bolgesi.png"
)
    
    if not gorsel_yolu.exists():
        print(f"[HATA] '{gorsel_yolu}' bulunamadı! Önce C# aracıyla ekran bölgesini seçin.")
        return

    print("[BİLGİ] Görsel bulundu, OCR motoru hazırlanıyor...")
    
    # Tek satırlık altyazılar için Tesseract daha iyi noktalama tanır.
    # RapidOCR Tesseract kurulu değilse veya metin döndürmezse yedektir.
    tesseract_yolu = tesseract_bul()
    ocr_motoru = RapidOCR(use_text_det=False)
    if tesseract_yolu:
        pytesseract.pytesseract.tesseract_cmd = tesseract_yolu

    # Süre ölçümünü başlat
    baslangic_zamani = time.perf_counter()
    goruntu_yukleme_baslangici = baslangic_zamani

    # 2. Adım: Görseli Belleğe Almak (with bloğu ile dosya kilitlenmesini önleyerek)
    try:
        with Image.open(gorsel_yolu) as img:
            goruntu_yukleme_suresi = (time.perf_counter() - goruntu_yukleme_baslangici) * 1000
            # 3. Adım: Ön İşleme (İlk testte görseli ham haliyle RGB'ye çevirip veriyoruz)
            ham_gorsel = img.convert("RGB")

            # 4. Adım: Önce Tesseract, gerekirse RapidOCR kullan
            sonuclar = None
            if tesseract_yolu:
                tesseract_baslangici = time.perf_counter()
                tesseract_metin = pytesseract.image_to_string(
                    ham_gorsel,
                    lang="eng",
                    config="--psm 7",
                ).strip()
                tesseract_suresi = (time.perf_counter() - tesseract_baslangici) * 1000
                if tesseract_metin:
                    temiz_metin = " ".join(tesseract_metin.split())
                else:
                    temiz_metin = ""
            else:
                temiz_metin = ""
                tesseract_suresi = 0.0

            if not temiz_metin:
                rapid_baslangici = time.perf_counter()
                sonuclar, _ = ocr_motoru(ham_gorsel)
                rapid_suresi = (time.perf_counter() - rapid_baslangici) * 1000
                if sonuclar:
                    temiz_metin = " ".join(
                        satir[1].strip() for satir in sonuclar
                    ).strip()
            else:
                rapid_suresi = 0.0

    except PermissionError:
        print("[UYARI] Dosya şu an C# tarafından yazılıyor, okuma atlandı.")
        return
    except Exception as hata:
        print(f"[HATA] Görsel okunurken bir sorun oluştu: {hata}")
        return

    # 5. Adım: Çıktıyı Temizlemek ve Çok Satırlı Altyazıları Birleştirmek
    if not temiz_metin:
        print("[SONUÇ] Ekranda altyazı algılanmadı.")
        return

    # 6. Adım: Konsola Yazdırmak ve Süreyi Gözlemlemek
    if temiz_metin:
        print("-" * 40)
        print(f"Okunan Metin : {temiz_metin}")
        print("-" * 40)
        toplam_sure = (time.perf_counter() - baslangic_zamani) * 1000
        print(f"Görüntü yükleme süresi : {goruntu_yukleme_suresi:.1f} ms")
        if tesseract_yolu:
            print(f"Tesseract süresi       : {tesseract_suresi:.1f} ms")
        if rapid_suresi > 0:
            print(f"RapidOCR yedek süresi   : {rapid_suresi:.1f} ms")
        print(f"Toplam işlem süresi     : {toplam_sure:.1f} ms")
    else:
        print("[SONUÇ] Altyazı algılanmadı (Boş çıktı).")

if __name__ == "__main__":
    altyazi_oku()
