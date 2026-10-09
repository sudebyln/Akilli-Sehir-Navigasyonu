# CLAUDE.md — Akıllı Şehir Navigasyonu

## Proje Özeti

İstanbul toplu taşıma rota planlayıcısı. Raylı sistem (metro, tramvay, marmaray, vapur, füniküler) ve İETT otobüs ağını birleştirerek A noktasından B noktasına en iyi rotayı bulur. Flask backend + vanilla JS frontend + Leaflet harita.

**Sunucu:** `python3 app.py` → `127.0.0.1:5001`

---

## Dizin Yapısı

```
akilli_sehir_navigasyon/
├── app.py                          # Flask API — ana dosya, tüm endpoint'ler
├── models/
│   └── graf.py                     # Graf sınıfı (multigraph, node_meta, hat_ekle)
├── services/
│   ├── bfs.py                      # Raylı sistem rota motorları (BFS tabanlı)
│   └── router.py                   # İETT otobüs rota motoru (Dijkstra/A*)
├── data/
│   ├── gtfs_yukleyici.py           # GTFS veri yükleyici, durak temizleme, canonical map
│   ├── walking_edge_yukleyici.py   # Yürüme kenarları (yakın duraklar arası)
│   ├── ornek_sehir.py              # Mini örnek graf (fallback)
│   ├── istanbul_graf.json          # Raylı sistem graph cache (JSON)
│   ├── iett_graph.pkl              # İETT graph (pickle) — ~15K durak
│   └── gtfs/
│       ├── stops.csv               # Raylı durak verileri
│       └── iett_stops.csv          # İETT durak verileri
├── templates/
│   └── index.html                  # Frontend (tek dosya: HTML + CSS + JS)
└── fix_all.py                      # Toplu yama scripti
```

---

## İki Ayrı Graf Sistemi

### 1. Raylı Sistem Grafı (`GRAF` — `models/graf.py`)

- **Kaynak:** `data/gtfs/` klasöründeki GTFS dosyaları → JSON cache: `istanbul_graf.json`
- **Yapı:** `Graf` sınıfı — `graf.istasyonlar`, `graf._node_meta`, `graf.hat_ekle()`
- **Rota motorları** (`services/bfs.py`):
  - `en_kisa_sureli_rota(GRAF, bas_ids, hdf_ids)` → En hızlı
  - `en_az_aktarmali_rota(GRAF, bas_ids, hdf_ids)` → En az aktarma
  - `en_az_yurume_rota(GRAF, bas_ids, hdf_ids)` → En az yürüme
- **Stop ID format:** Sayısal string (`"18996"`, `"18954"`)
- **Stop name format:** Title Case (`"Taksim"`, `"Kabataş"`, `"Sultanahmet"`)

### 2. İETT Otobüs Grafı (`_graph` — `services/router.py`)

- **Kaynak:** `data/iett_graph.pkl` (pickle, modül başlangıcında 1 kere yüklenir)
- **Yapı:** `_graph[stop_id] = [(next_stop_id, sure, hat_adi, hat_tipi, renk), ...]`
- **Meta:** `_stop_meta[stop_id] = {"name": "...", "lat": ..., "lon": ...}`
- **Rota motoru:** `dijkstra(bas_ids, hdf_ids, strateji="hizli"|"aktarma"|"yurume")`
- **Stop name format:** BÜYÜK HARF (`"KABATAŞ"`, `"TAKSİM"`, `"SANCAKTEPE"`)

### İki Sistem Arasındaki Köprüler

- `STOP_NAME_TO_IDS`: Raylı stop_name → stop_id listesi
- `CANONICAL_MAP`: Canonical (parantez öncesi) isim → disambiguated isimler
- `STOP_ID_TO_NAME`: stop_id → UI'da gösterilecek isim
- `iett_isim_to_ids(name)`: İETT'de isim → stop_id
- `iett_isim_to_ids_koord(name, lat, lon)`: İETT'de isim+koordinat → stop_id

---

## API Endpoint'leri

| Endpoint | Method | Açıklama |
|---|---|---|
| `/` | GET | Ana sayfa (index.html) |
| `/api/istasyonlar` | GET | Tüm durak isim listesi (autocomplete için) |
| `/api/durak-ara?q=...&fmt=isim\|full` | GET | Durak arama (isim prefix match) |
| `/api/akilli-rota` | POST | **Ana endpoint** — raylı+İETT birleşik rota |
| `/api/rota` | POST | Sadece raylı sistem rotası |
| `/api/iett-rota` | POST | Sadece İETT rotası |
| `/api/graf` | GET | Tüm graf verisi (harita görselleştirme) |
| `/api/hat-profil?hat=...` | GET | Hat detayı (duraklar, mesafeler) |
| `/api/iett-duraklar` | GET | İETT durak listesi (koordinatlı) |
| `/api/iett-durak-ara?q=...` | GET | İETT durak arama |

### `/api/akilli-rota` — Ana Rota Endpoint'i

**Request:**
```json
{
  "baslangic": "Kadıköy",
  "hedef": "Taksim",
  "strateji": "aktarma",
  "bas_lat": 40.99, "bas_lon": 29.02,
  "hdf_lat": 41.04, "hdf_lon": 28.98
}
```

**Response (rota objesi):**
```json
{
  "baslangic": "Kadıköy",
  "hedef": "Taksim",
  "rotalar": [{
    "yol": ["Kadıköy", "Ayrılık Çeşmesi", ...],
    "yol_stop_ids": ["18996", "18955", ...],
    "sure": 25,
    "aktarma": 1,
    "etkin_maliyet": 30.5,
    "hatlar": ["M4", "M4", "Marmaray1", ...],
    "hat_renkleri": ["#1A4F8A", "#1A4F8A", "#7A8084", ...],
    "aktarma_noktalari": ["Ayrılık Çeşmesi"],
    "koordinatlar": [[40.99, 29.02], ...],
    "adimlar": [
      {"tip": "bin", "durak": "Kadıköy", "stop_id": "18996", "hat": "M4"},
      {"tip": "devam", "hat": "M4", "durak_sayisi": 3},
      {"tip": "aktarma", "durak": "Ayrılık Çeşmesi", "hat_den": "M4", "hat_e": "Marmaray1"},
      {"tip": "devam", "hat": "Marmaray1", "durak_sayisi": 5},
      {"tip": "in", "durak": "Taksim", "stop_id": "18955"}
    ],
    "strateji": "En Az Aktarma",
    "kaynak": "rayli",
    "segmentler": [
      {"coords": [[40.99,29.02],[41.00,29.03]], "hat": "M4", "renk": "#1A4F8A", "yurume": false}
    ]
  }]
}
```

### Adım Tipleri

| tip | Alanlar | Anlam |
|---|---|---|
| `bin` | durak, stop_id, hat | İlk biniş noktası |
| `devam` | hat, durak_sayisi | Aynı hatta devam (N durak) |
| `aktarma` | durak, stop_id, hat_den, hat_e | Hat değişimi |
| `in` | durak, stop_id, hat | Son durakta iniş |
| `yurume` | durak_den, durak_e | Yürüme (iki durak arası transfer) |

---

## Rota Seçim Mantığı (`/api/akilli-rota`)

1. Hem raylı hem İETT'de stop_id'leri çöz
2. Birden fazla rota hesapla (raylı, İETT hızlı, İETT aktarmasız)
3. Skor fonksiyonu ile en iyiyi seç:

```
hizli mod:  skor = sure + aktarma_cezasi
            (0 akt → 0, 1 akt → +15, 2 akt → +40, 3+ → +1000)

aktarma mod: skor = aktarma × 1000 + sure
```

4. Post-processing: YURUME adımlarını temizle, hat isimlerini çevir, renkleri ata

---

## Bilinen Teknik Sorunlar ve Çözümleri

### 🔴 KRİTİK: Türkçe İ/i Case Bug

**Sorun:** Python'da `"İ".lower()` = `"i̇"` (i + combining dot above U+0307), `"i"` DEĞİL.
Bu yüzden `"TAKSİM".lower()` ≠ `"Taksim".lower()`, durak eşleşmesi başarısız olur.

**Etkilenen yerler:**
- `app.py` → `_resolve()` fonksiyonu (akilli-rota'da)
- `app.py` → `_resolve_stop_ids()` fonksiyonu (rota'da)
- `app.py` → `_durak_ara_disambiguated()` (durak arama)
- `services/router.py` → `isim_to_ids()`, `durak_ara()`

**Çözüm:** Her yerde `.lower()` yerine Türkçe-uyumlu normalize helper kullan:
```python
def tr_lower(s: str) -> str:
    """Türkçe İ/i uyumlu lowercase."""
    return s.replace("İ", "i").replace("I", "ı").lower().replace("\u0307", "")
```

### 🔴 İki Sistem Arası İsim Uyumsuzluğu

**Sorun:** Raylı sistemde `"Taksim"` (Title Case), İETT'de `"TAKSİM"` (BÜYÜK HARF).
Kullanıcı hangi formatta yazarsa yazsın ikisi de eşleşmeli.

**Etkilenen yerler:** `_resolve()` fonksiyonundaki `STOP_NAME_TO_IDS` ve `CANONICAL_MAP` lookup'ları.

**Çözüm:** Tüm isim karşılaştırmalarında `tr_lower()` kullan, hem aranacak ismi hem sözlük key'lerini normalize et.

### 🟡 "Yürüme Hattına Bin" Metinsel Bug

**Sorun:** Rota yürüme kenarı ile başlıyorsa adımlar şöyle çıkıyor:
```
"KABATAŞ durağından başla — Yürüme hattına bin"
```
Bu saçma — yürüme bir hat değil.

**Neden:** `_adim_tarif_olustur()` (router.py) her kenarı aynı mantıkla işliyor.
İlk kenar YURUME ise `{"tip": "bin", "hat": "YURUME"}` üretiyor.

**Çözüm:** `app.py`'de adım post-processing:
- `tip=bin, hat=YURUME` → `tip=yurume, durak_den=X, durak_e=Y` dönüştür
- `tip=aktarma, hat_e=YURUME` + `tip=aktarma, hat_den=YURUME` → birleştir
- `tip=in, hat=YURUME` → önceki gerçek hattı bul

### 🟡 YURUME Koordinatları Siliniyor

**Sorun:** YURUME kenarlarının koordinatları temizlenince harita polyline'ı kopuyor.

**Çözüm:** YURUME koordinatlarını silme, bunun yerine `segmentler` array'i oluştur:
```python
{"coords": [[lat1,lon1],[lat2,lon2]], "hat": "YURUME", "renk": "#888888", "yurume": true}
```
Frontend bu segmentleri iterate edip yürüme segmentlerini kesikli çizgi (`dashArray`) ile çizsin.

### 🟡 Aynı İsimli Farklı Lokasyonlar

**Sorun:** GTFS'te `"SANCAKTEPE"` ismiyle birden fazla durak var — biri gerçek Sancaktepe (41.01°N, 29.23°E), diğeri yanlış koordinatlı (41.20°N, Arnavutköy tarafı).

**Mevcut çözüm:** `en_iyi_id_sec()` (router.py) — en çok komşusu olan + İstanbul merkezine en yakın durağı seçer. `_YANLIS_KOORDINATLI_DURAKLAR` set'inde bilinen kötü stop_id'ler hardcoded.

---

## Graph Edge Formatları

### Raylı Sistem (`Graf` sınıfı)
```python
graf.hat_ekle(baslangic_id, bitis_id, hat_tipi, hat_adi, sure, renk)
# hat_tipi: "Metro", "Tramvay", "Tren", "Vapur", "Füniküler", "Teleferik", "Metrobüs"
# hat_adi: "M1", "M2", "T1", "Marmaray", "F1", vb.
```

### İETT Sistem (`_graph` dict)
```python
_graph[stop_id] = [
    (next_stop_id, sure_dakika, hat_adi, hat_tipi, renk_hex),
    # hat_adi: "70KE", "500T", "YURUME" (yürüme kenarı)
    # hat_tipi: "Otobüs", "Yürüme", "Dolmuş"
]
```

### Yürüme Kenarları
- `hat_adi = "YURUME"`, `hat_tipi = "Yürüme"`
- Yakın duraklar arası (~100m) otomatik eklenir
- Süre: mesafe / 80 m/dk

---

## HAT_ISIMLERI Sözlüğü

Teknik hat kodları → okunabilir isimler çevrimi `app.py`'de yapılır:
```python
"F1"  → "Taksim-Kabataş Füniküler"
"EMN-KDK" → "Eminönü-Kadıköy Vapuru"
"YURUME" → "Yürüme"
```
Eksik hat kodu varsa orijinal kod UI'da görünür.

---

## Frontend Mimarisi (templates/index.html)

- Leaflet.js harita
- Vanilla JS (framework yok)
- Tek dosya (HTML + CSS + JS)
- `state` objesi: `{baslangic, hedef, strateji, koordinatlar}`
- `/api/akilli-rota` çağrısı sonucu:
  - Polyline çizimi (`rota.segmentler` veya `rota.koordinatlar` + `rota.hatlar`)
  - A/B marker'ları
  - Aktarma marker'ları
  - Adım adım yol tarifi panel'i

### Polyline Çizimi
- Her segment için ayrı polyline (farklı renkler)
- Yürüme segmentleri: kesikli çizgi (`dashArray: "6,8"`)
- Normal segmentler: düz çizgi

---

## Geliştirme Kuralları

### Değişiklik Yaparken

1. **Asla `.lower()` kullanma** — Türkçe metinlerde her zaman `tr_lower()` helper'ı kullan
2. **Stop name karşılaştırmasında** her iki tarafı da normalize et
3. **Yeni hat kodu eklenince** `HAT_ISIMLERI` sözlüğüne okunabilir isim ekle
4. **Koordinat kontrolü:** `if lat and lon` — 0.0 koordinat geçersiz sayılır
5. **Adım post-processing:** `YURUME` hat adı hiçbir zaman UI'da görünmemeli
6. **Test senaryoları:** Her değişiklikten sonra şu rotaları test et:
   - KABATAŞ → TAKSİM (Füniküler, 5dk)
   - Kadıköy → Taksim (M4 + Marmaray veya M4 + M2)
   - SULTANAHMET → Taksim (T1 + Füniküler)
   - Sancaktepe → Eminönü (İETT veya hibrit)

### Fix Script Yazarken

- `fix_all.py` pattern: string find-replace, `old in content` guard
- Her değişiklik idempotent olmalı (zaten uygulanmışsa skip)
- Backup al: `cp app.py app.py.backup`
- Çalıştır: `python3 fix_all.py && python3 app.py`

### Sık Karşılaşılan Hatalar

| Hata | Neden | Çözüm |
|---|---|---|
| "Durak bulunamadı: 'TAKSİM'" | Türkçe İ/i case bug | `tr_lower()` kullan |
| "Yürüme hattına bin" | YURUME adım post-process eksik | Adımları post-process et |
| Harita polyline kopuk | YURUME koordinatları siliniyor | Segmentler koru |
| İETT rotası raylıdan kötü ama seçiliyor | Raylı durak bulunamıyor (case mismatch) | `_resolve()` düzelt |
| Sancaktepe yanlış lokasyon | Aynı isimli farklı koordinatlı duraklar | `en_iyi_id_sec()` |
| Aktarma marker A üstünde | Aynı koordinat kontrolü yok | Mesafe threshold ekle |

---

## Strateji Seçenekleri

| Strateji | API Değer | Optimizasyon | Skor |
|---|---|---|---|
| En Hızlı | `hizli` | Toplam süre minimum | sure + aktarma_cezası |
| En Az Aktarma | `aktarma` | Aktarma sayısı minimum | aktarma×1000 + sure |
| En Az Yürüme | `yurume` | Yürüme mesafesi minimum | (sadece İETT'de) |

---

## Çalıştırma

```bash
cd /Users/melos/Desktop/Akıllı_Şehir_Navigasyonu/akilli_sehir_navigasyon
python3 app.py
# → http://127.0.0.1:5001
```

### Gerekli Paketler
```
flask, flask-cors
```

### Yama Uygulama
```bash
cp app.py app.py.backup
python3 fix_all.py
python3 app.py
```
