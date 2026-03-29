# Hackathon Submission Draft

## Yuksek Duzey Ozet

Bu cozum, NOAA/SWPC uzay hava verilerini otomatik toplayarak 6-24 saatlik elektromanyetik firtina riskini erken tespit eden bir Uzay Havasi Erken Uyari Paneli sunar. Sistem; veri toplama, kural tabanli risk siniflandirma, otomatik alarm ve panel goruntuleme adimlarini tek bir akis haline getirir.

## Detayli Cozum

- Veri kaynaklari: Planetary K-index, GOES X-ray, GOES Proton Flux
- Canli veri kesintisinde mock fallback ile calisma devam eder
- NOAA G/S/R esiklerine gore siddet derecesi belirlenir
- Bilesik risk seviyesi (calm-minor-moderate-strong-severe-extreme) uretilir
- Alarm sistemi dedupe + cooldown ile gereksiz tekrar alarmi engeller
- SMTP tabanli e-posta bildirimleri desteklenir
- React panelinde canli durum, trend ve alarm gecmisi gosterilir

## Teknik Yaklasim

- Backend: FastAPI, asenkron veri cekimi, servis tabanli mimari
- Frontend: React + TypeScript + Recharts
- Isletim: Docker Compose ile lokal orkestrasyon
- Test: Risk motoru ve alarm davranisi icin birim testleri

## Odaklanilan Etki

- Erken uyari ile operasyon ekiplerine zaman kazandirma
- Uzay havasi kaynakli iletisim, navigasyon ve enerji etkilerine hazirlik
- Demo ortaminda veri kesintilerine dayanabilecek guvenilir panel davranisi
