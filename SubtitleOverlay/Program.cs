using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;

namespace OyunCeviriAraci
{
    public partial class Form1 : Form
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Form1());
        }

        private Point baslangicNoktasi;
        private Rectangle secilenAlan;
        private bool cizimYapiliyor = false;

        public Form1()
        {
            // 1. Tam Ekran Şeffaf Katman Ayarları
            this.FormBorderStyle = FormBorderStyle.None; // Kenarlıkları kaldır
            this.WindowState = FormWindowState.Maximized; // Tam ekran yap
            this.TopMost = true; // Her şeyin en üstünde tut
            this.BackColor = Color.Black; // Arka planı siyah yap
            this.Opacity = 0.35; // %35 şeffaflık (Ekranı hafif karartır)
            this.Cursor = Cursors.Cross; // Fare imlecini artı (+) yap
            this.DoubleBuffered = true; // Çizim yaparken ekranın titremesini önler

            // 2. Fare ve Klavye Olaylarını Bağlama
            this.MouseDown += Ekran_MouseDown;
            this.MouseMove += Ekran_MouseMove;
            this.MouseUp += Ekran_MouseUp;
            this.Paint += Ekran_Paint;
            this.KeyDown += (s, e) => { if (e.KeyCode == Keys.Escape) this.Close(); }; // ESC ile çıkış
        }

        // Tıklama Anı (X1, Y1)
        private void Ekran_MouseDown(object? sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                cizimYapiliyor = true;
                baslangicNoktasi = e.Location;
            }
        }

        // Sürükleme Anı (X2, Y2)
        private void Ekran_MouseMove(object? sender, MouseEventArgs e)
        {
            if (cizimYapiliyor)
            {
                // Ters yöne çizim ihtimaline karşı en küçük X ve Y'yi bul
                int x = Math.Min(baslangicNoktasi.X, e.X);
                int y = Math.Min(baslangicNoktasi.Y, e.Y);
                int genislik = Math.Abs(baslangicNoktasi.X - e.X);
                int yukseklik = Math.Abs(baslangicNoktasi.Y - e.Y);

                secilenAlan = new Rectangle(x, y, genislik, yukseklik);
                this.Invalidate(); // Ekranı yeniden çiz (Dikdörtgeni güncelle)
            }
        }

        // Ekrana Kırmızı Seçim Çerçevesini Çizme
        private void Ekran_Paint(object? sender, PaintEventArgs e)
        {
            if (secilenAlan.Width > 0 && secilenAlan.Height > 0)
            {
                // Seçilen alanın içini biraz daha aydınlık göster
                using (Brush firca = new SolidBrush(Color.FromArgb(60, Color.White)))
                {
                    e.Graphics.FillRectangle(firca, secilenAlan);
                }
                // Etrafına 2 piksel kalınlığında kırmızı çerçeve çiz
                using (Pen kalem = new Pen(Color.Red, 2))
                {
                    e.Graphics.DrawRectangle(kalem, secilenAlan);
                }
            }
        }

        // Bırakma Anı ve Görüntüyü Yakalama
        private void Ekran_MouseUp(object? sender, MouseEventArgs e)
        {
            if (cizimYapiliyor)
            {
                cizimYapiliyor = false;
                this.Hide(); // Şeffaf katmanı gizle ki yakalanan resim kararmasın

                // Çok küçük (yanlışlıkla) tıklamaları yoksay
                if (secilenAlan.Width > 10 && secilenAlan.Height > 10)
                {
                    BolgeyiYakala(secilenAlan);
                }

                this.Close(); // İşlem bitince seçim ekranını kapat
            }
        }

        // 3. Piksel Verisini Kırpma (Screen Capture)
        private void BolgeyiYakala(Rectangle bolge)
        {
            // Seçilen boyutlarda boş bir resim (Bitmap) oluştur
            using (Bitmap yakalananResim = new Bitmap(bolge.Width, bolge.Height))
            {
                using (Graphics g = Graphics.FromImage(yakalananResim))
                {
                    // Ekran kartından doğrudan ilgili koordinatları belleğe kopyala
                    g.CopyFromScreen(bolge.Location, Point.Empty, bolge.Size);
                }

                // Test amaçlı bilgisayara kaydet (Asıl programda RAM'den direkt OCR'a gidecek)
                yakalananResim.Save("secilen_altyazi_bolgesi.png", ImageFormat.Png);
                MessageBox.Show($"Bölge yakalandı!\nKoordinatlar: {bolge}", "Başarılı");
            }
        }
    }
}
