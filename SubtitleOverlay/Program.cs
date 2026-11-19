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
            Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Form1());
        }

        private Point baslangicNoktasi;
        private Rectangle secilenAlan;
        private bool cizimYapiliyor = false;

        public Form1()
        {
            // Sanal masaüstünü (tum monitörleri ve negatif koordinatları) kapsar.
            Rectangle sanalMasaustu = GetSanalMasaustu();

            this.FormBorderStyle = FormBorderStyle.None;
            this.StartPosition = FormStartPosition.Manual;
            this.Bounds = sanalMasaustu;
            this.TopMost = true;
            this.BackColor = Color.Black;
            this.Opacity = 0.35;
            this.Cursor = Cursors.Cross;
            this.DoubleBuffered = true;
            this.AutoScaleMode = AutoScaleMode.Dpi;

            // 2. Fare ve Klavye Olaylarını Bağlama
            this.MouseDown += Ekran_MouseDown;
            this.MouseMove += Ekran_MouseMove;
            this.MouseUp += Ekran_MouseUp;
            this.Paint += Ekran_Paint;
            this.KeyDown += (s, e) => { if (e.KeyCode == Keys.Escape) this.Close(); }; // ESC ile çıkış
        }

        private static Rectangle GetSanalMasaustu()
        {
            int sol = 0;
            int ust = 0;
            int sag = 0;
            int alt = 0;

            foreach (Screen ekran in Screen.AllScreens)
            {
                sol = Math.Min(sol, ekran.Bounds.Left);
                ust = Math.Min(ust, ekran.Bounds.Top);
                sag = Math.Max(sag, ekran.Bounds.Right);
                alt = Math.Max(alt, ekran.Bounds.Bottom);
            }

            return Rectangle.FromLTRB(sol, ust, sag, alt);
        }

        // Tıklama Anı (X1, Y1)
        private void Ekran_MouseDown(object? sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                cizimYapiliyor = true;
                baslangicNoktasi = e.Location;
                secilenAlan = new Rectangle(e.Location, Size.Empty);
                this.Invalidate();
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

                int x = Math.Min(baslangicNoktasi.X, e.X);
                int y = Math.Min(baslangicNoktasi.Y, e.Y);
                secilenAlan = new Rectangle(
                    x,
                    y,
                    Math.Abs(baslangicNoktasi.X - e.X),
                    Math.Abs(baslangicNoktasi.Y - e.Y));

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
            Point solUst = this.PointToScreen(bolge.Location);
            Point sagAlt = this.PointToScreen(
                new Point(bolge.Right, bolge.Bottom));
            Rectangle ekranBolgesi = Rectangle.FromLTRB(
                Math.Min(solUst.X, sagAlt.X),
                Math.Min(solUst.Y, sagAlt.Y),
                Math.Max(solUst.X, sagAlt.X),
                Math.Max(solUst.Y, sagAlt.Y));

            // Seçilen boyutlarda boş bir resim (Bitmap) oluştur
            using (Bitmap yakalananResim = new Bitmap(ekranBolgesi.Width, ekranBolgesi.Height))
            {
                using (Graphics g = Graphics.FromImage(yakalananResim))
                {
                    // Ekran kartından doğrudan ilgili koordinatları belleğe kopyala
                    g.CopyFromScreen(ekranBolgesi.Location, Point.Empty, ekranBolgesi.Size);
                }

                // Test amaçlı bilgisayara kaydet (Asıl programda RAM'den direkt OCR'a gidecek)
                yakalananResim.Save("secilen_altyazi_bolgesi.png", ImageFormat.Png);
                MessageBox.Show($"Bölge yakalandı!\nKoordinatlar: {ekranBolgesi}", "Başarılı");
            }
        }
    }
}
