# Doğrulama

1.0.0 paketinin hazırlığı sırasında:

- Kurucu için 7 test geçti: Npcap kontrolü, ip/paylaşım doğrulama, yönetici parolasını saklamama, bilinmeyen kurulum klasörünü koruma, akış simülasyonu ve WinRM parçalı aktarım/temizlik.
- Web uygulaması için 12 test geçti: Türkçe arayüz, tarih sınırları, PDF/CSV, tüm filtreli satırları indirme, bir yıllık silme, API yetkilendirmesi/tekrar gönderim, envanter, ilk giriş ve mevcut parolayı koruma.
- Ayrı geçici SQLite veritabanıyla gerçek HTTP üzerinden ilk `admin / admin` girişi, zorunlu parola değiştirme, Türkçe grafik ekranı ve PDF indirme doğrulandı. Mevcut kullanıcı veritabanı bu testte kullanılmadı.
- Bash kurulum/bakım/kaldırma betikleri ve Windows PowerShell betikleri sözdizimi kontrolünden geçti.
- Python 3.13 / Windows x64 için sabit ajan bağımlılıklarının tekerlek paketlerinin indirilebildiği kontrol edildi.

Paketleyici ayrıca SHA256 dosyası, kaynak arşivleri ve statik HTTP Git deposu üretir.
Web yayın paketini hazırladıktan sonra indirme/kaynak bağlantıları, farklı bir web alt klasöründen adres üretimi ve HTTP Git klonlama kontrol edilir.

Windows kurucusunun yeni bir Windows VM'sinde sıfırdan uçtan uca kurulumu bu sürümün test kapsamına dahil değildir. Npcap ücretsiz sürümünde Windows'taki grafik kurulum adımını kullanıcı tamamlar; sihirbaz sonrasında sürücüyü yeniden doğrular.
