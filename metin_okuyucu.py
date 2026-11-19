import time
from pathlib import Path
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

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
    
    # OCR Motorunu başlat (Gerçek döngüde bu satır döngünün dışında sadece 1 kez çalıştırılır)
    ocr_motoru = RapidOCR()

    # Süre ölçümünü başlat
    baslangic_zamani = time.perf_counter()

    # 2. Adım: Görseli Belleğe Almak (with bloğu ile dosya kilitlenmesini önleyerek)
    try:
        with Image.open(gorsel_yolu) as img:
            # 3. Adım: Ön İşleme (İlk testte görseli ham haliyle RGB'ye çevirip veriyoruz)
            ham_gorsel = img.convert("RGB")
            
            # 4. Adım: OCR Motorunu Çalıştırmak
            # RapidOCR doğrudan PIL Image veya dosya yolu alabilir
            sonuclar, _ = ocr_motoru(gorsel_yolu)

    except PermissionError:
        print("[UYARI] Dosya şu an C# tarafından yazılıyor, okuma atlandı.")
        return
    except Exception as hata:
        print(f"[HATA] Görsel okunurken bir sorun oluştu: {hata}")
        return

    # 5. Adım: Çıktıyı Temizlemek ve Çok Satırlı Altyazıları Birleştirmek
    if not sonuclar:
        print("[SONUÇ] Ekranda altyazı algılanmadı.")
        return

    # RapidOCR her satırı [koordinat, metin, güven_skoru] olarak döndürür.
    # Tüm satırları alıp aralarına boşluk koyarak tek bir cümle haline getiriyoruz.
    okunan_satirlar = [satir[1].strip() for satir in sonuclar]
    temiz_metin = " ".join(okunan_satirlar).strip()

    # 6. Adım: Konsola Yazdırmak ve Süreyi Gözlemlemek
    if temiz_metin:
        print("-" * 40)
        print(f"Okunan Metin : {temiz_metin}")
        print("-" * 40)
    else:
        print("[SONUÇ] Altyazı algılanmadı (Boş çıktı).")

if __name__ == "__main__":
    altyazi_oku()
