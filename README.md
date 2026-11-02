# BankScope — Otomatik veri altyapısı, v0.2

**Bu sürüm tam ve canlı veri ürünü değildir.** Resmî kaynakların teknik keşfi, ham veri arşivleme, kontrollü haftalık kredi aktarımı, otomasyon şablonu, denetim raporu ve *veri yükleme gerektirmeyen* yeni arayüz kurulmuştur. Aylık interaktif BDDK tablo entegrasyonu ve TBB banka finansal tablolarının muhasebe bazlı eşleştirmesi **henüz tamamlanmamıştır**; bu alanlarda sayı gösterilmez. Başka bir şey söyleyen bir gösterge paneline güvenilmemelidir.

## Çalıştırma

- Siteyi denemek için `web/index.html` dosyasını çift tıklayın. Doğrulanmış 23.10.2026 BDDK kredi kesiti (`web/data/snapshot.js`) açılır. İnternet gerekmez.
- Sistem yöneticisi için: `python -m pip install -r requirements.txt` ve `python -m pytest -q`.
- Canlı resmî veri kontrolü: `python -m src.pipeline --online`.
- TBB'nin en güncel standart ZIP/XLS raporlarını **ham ve eşleştirilmemiş arşive** almak için: `python -m src.pipeline --online --download-bank-archives`.
- `web/data/snapshot.json` statik yayın modeli, `web/data/audit.json` kalite/durum raporu, `archive/` içerik hash'li kaynak arşividir.

## Çalışan otomasyon

- BDDK haftalık bültenin mevcut *Krediler* tablosu (22 satır × TP/YP/toplam = 66 gözlem) HTML'den okunur, tutarlılık kontrolü yapılır, önceki dönem korunarak yenilenir. **Tüm haftalık tabloları veya tüm tarihi kapsadığı iddia edilmez**.
- TBB'nin raporlar listesi otomatik taranır; güncel solo/konsolide standart veri seti bağlantıları keşfedilir; uygun ZIP/XLS dosyaları indirilebilir, dosya imzası ve hash bilgisiyle arşivlenir. **Arşivlenmiş belge, muhasebe satırları doğrulanana kadar bankaya ait bir rakam olarak yayımlanmaz.**
- BDDK Eylül 2026 aylık bülteni duyurusu resmî siteden kontrol edilir; aylık tabloyu oluşturacak form akışı henüz uygulanmamıştır.
- GitHub Actions, daha sonra bir GitHub reposuna yüklendiğinde hafta içi otomatik olarak test/yenileme yapabilecek şekilde tanımlıdır. Netlify yapılandırması vardır; **repo bağlantısı veya canlı yayın henüz yapılmamıştır**.
- Kaynak çökerse önceki doğrulanmış kesit korunur ve denetim kayıtlarına hata yazılır. Verinin bulunmadığı alan boş bırakılır.

## Tasarım / finansal kalite kuralları

- Veri anahtarı: kaynak + dönem + kapsam + banka + gösterge + para birimi. Konsolide/solo ve farklı dönemler aynı toplamda birleştirilmez.
- Tutarlar MİLYON TL; TP ve YP her ikisi de TL karşılığıdır. YP doğrudan USD/EUR tutarı **değildir**.
- `TDO = brüt takipteki alacaklar / brüt nakdi krediler × 100`, fakat yalnızca aynı tanımlı/paydalı kaynaktan veriler varsa uygulanır; Stage 3 otomatik NPL sayılmaz.
- Net dönem kârları gibi birikimli (YTD) akımlar çeyrek akımı sayılmaz; gerekli olduğunda önceki döneme göre fark alınır.
- En büyük 10 listesi, aynı dönem ve aynı solo/konsolide kapsamda yeterli doğrulanmış banka bulunmadan yayımlanmaz. TBB üyesi olmayan katılım bankaları için TKBB ve KAP ayrıca kapsama alınmalıdır.
- BDDK ve TBB yayın/tekrar kullanım koşulları değerlendirilmelidir; özellikle BDDK verilerinin **ticari kullanımında yazılı izin** hükmü bulunur.

## Dosya yapısı

```
web/index.html,style.css,app.js     kullanıcı web sitesi, manuel veri girişi içermez
web/data/snapshot.js,json           yayınlanabilir doğrulanmış veri kesiti
web/data/audit.json                 son yenileme durumu
src/core.py                         kaynak, birim ve tekilleştirme kuralları
src/bddk.py                         haftalık BDDK Krediler tablosu ayrıştırıcısı
src/tbb.py                          TBB rapor keşfi + ham arşiv
src/pipeline.py                     ETL işlem sırası, korunmuş yayın snapshotu
tests/                              kaynak-parsing ve hata-önleme testleri
.github/workflows/refresh.yml       ileride repo bağlantısından sonra zamanlı güncelleme
netlify.toml                        ileride statik yayın
```

## Tam üretime geçiş için kalan zorunlu işler

1. Haftalık tüm gösterge gruplarının tarihsel dönem formu ve indirme API'sini resmî sayfadan doğrulayıp sağlam parser eklemek.
2. BDDK aylık etkileşimli rapor oluşturma akışını, tüm dönemler ve sınıflamalar için otomatik okuyup muhasebe tablo karşılaştırmasıyla test etmek.
3. TBB solo/konsolide XLS/ZIP'lerinden en az 10 banka değil, **aday bankaların tamamını** okuyup resmi aktif büyüklüğü sıralamasıyla karşılaştırmak; bankaya ait finansal kalemleri doğrulanmış sözlük üzerinden eşlemek.
4. TBB üyesi olmayan katılım bankalarını TKBB/KAP üzerinden kapsama almak; tanım farklılıklarını doğrulamak.
5. 3–5 yıllık geriye dönük doldurma, revizyon takibi ve min. 1 dönem mutabakat testi yapmak.
6. Canlı GitHub Actions ve Netlify kurulumu; çoklu veri kaynağı yayım koşullarının gözden geçirilmesi.

**Kamuya açık ve sürekli güncel bir ürün olarak yayınlamadan önce eksik kalemler tamamlanmalı ve kalite eşiği sağlanmalıdır.**
