# -*- coding: utf-8 -*-

import csv
import json
import math  # YENİ
import os
import re
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.graf import Graf  # noqa: E402

# ── Sabitler ──────────────────────────────────────────────────────────────────

FILTRELENEN_TIPLER: set[int] = {9, 10}     # Otobüs (9) ve Dolmuş (10) hariç tutulur

# ── Resmi aktarma noktaları ──────────────────────────────────────────────────
# İstanbul ulaşım sisteminde fiziksel olarak aktarma yapılabilen istasyonlar.
# BFS/Dijkstra bu sözlüğü dış kaynaktan import ederek "aynı istasyonda hat
# değişimi" kararını yalnızca buradaki noktalarda izinli sayar.
VAPUR_PREFIXES = ["BĞZ", "ŞH", "KBTŞ", "BSK", "BOS", "KDK", "EMN", "ÜSK", "ADA"]

AKTARMA_NOKTALARI: dict[str, list[str]] = {
    "Kabataş":         ["T1", "F1"] + VAPUR_PREFIXES,
    "Eminönü":         ["T1"] + VAPUR_PREFIXES,
    "Kadıköy":         ["M4", "M5"] + VAPUR_PREFIXES,
    "Üsküdar":         ["Marmaray", "M5"] + VAPUR_PREFIXES,
    "Beşiktaş":        VAPUR_PREFIXES,
    "Yenikapı":        ["M1A", "M1B", "M2", "T1", "Marmaray"] + VAPUR_PREFIXES,
    "Söğütlüçeşme":    ["Marmaray", "M4"],
    "Ayrılık Çeşmesi": ["Marmaray", "M4"],
    "Bostancı":        ["Marmaray", "M4", "M8"] + VAPUR_PREFIXES,
    "Taksim":          ["M2", "F1"],
    "Sirkeci":          ["Marmaray", "T1", "Yürüme"],
    "Kazlıçeşme":      ["Marmaray", "T1"],
    "Zeytinburnu":     ["M1A", "M1B", "T1"],
}

ROUTE_TYPE_ETIKETLERI: dict[int, str] = {
    0:  "Tramvay",
    1:  "Metro",
    2:  "Tren",
    3:  "Otobüs",
    4:  "Vapur",
    6:  "Teleferik",
    7:  "Füniküler",
    9:  "Otobüs",
    10: "Dolmuş",
}

HAT_TIPI_RENKLERI: dict[int, str] = {
    0:  "#C8102E",   # Tramvay (T1) → kırmızı
    1:  "#E30613",   # Metro → İBB kırmızısı
    2:  "#1A4F8A",   # Marmaray → lacivert
    3:  "#FF6B00",   # Otobüs → İETT turuncu
    4:  "#00ACC1",   # Vapur → turkuaz
    6:  "#9C27B0",   # Teleferik → mor
    7:  "#FF9800",   # Füniküler → amber
    9:  "#FF6B00",   # Otobüs (tip9) → tip3 ile aynı
    10: "#795548",   # Dolmuş → kahverengi
}

HAT_OZEL_RENKLERI: dict[str, str] = {
    "M1A": "#E30613", "M1B": "#E30613",
    "M2":  "#00A651", "M3":  "#1976D2",
    "M4":  "#FF9800", "M5":  "#9C27B0",
    "M6":  "#1976D2", "M7":  "#E30613",
    "T1":  "#C8102E", "T3":  "#C8102E",
    "F1":  "#FF9800", "F2":  "#FF9800",
    "Marmaray": "#1976D2",
}

_SONEK_KALIP: re.Pattern = re.compile(
    r'\s+(?:[şŞ][Hh]\.?|[İi]st\.?|[Dd]ura[gğ]ı|[İi]stasyonu?|[Mm]eydanı|[Pp]ier)$',
    re.UNICODE,
)

_TURKCE_BUYUK: dict[str, str] = {'ı': 'İ', 'i': 'İ'}


# ── Durak İsim Temizleme & Canonical Mapping Sistemi ─────────────────────────
#
# Ham GTFS verisini kullanıcı dostu, sade ve ölçeklenebilir bir durak modeline
# dönüştürür. UI'da sadece temiz canonical isimler gösterilir; routing motoru
# tüm varyantları multi-source Dijkstra ile kullanır.

_GECERSIZ_KELIMELER = {"Turyol", "İDO", "Adalar", "BUDO", "Dentur"}

_GECERSIZ_KELIME_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(k) for k in _GECERSIZ_KELIMELER) + r')\b',
    re.IGNORECASE | re.UNICODE,
)

_SONU_SAYI_RE = re.compile(r'\d+$')

_TURKCE_NORMALIZE: dict[str, str] = {
    'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
    'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U',
}


def canonical_name(name: str) -> str:
    """Durak adının canonical (temel) formunu üretir.

    Kurallar (sırayla uygulanır):
        1. Underscore sonrası kaldır: 'Kadıköy_EMN' → 'Kadıköy'
        2. Parantez içi kaldır: 'Kadıköy (Vapur)' → 'Kadıköy'
        3. Sondaki sayıları kaldır: 'Kadıköy2' → 'Kadıköy'
        4. Tire ile ayrılmış hat isimlerinde ilk parçayı al:
           'Kadıköy-Beşiktaş' → 'Kadıköy'
        5. Trim + normalize

    Complexity: O(len(name))
    """
    if not name:
        return ""
    result = re.split(r'[_(]', name)[0].strip()
    if '-' in result:
        result = result.split('-')[0].strip()
    result = _SONU_SAYI_RE.sub('', result).strip()
    return result


def is_valid_stop(name: str) -> bool:
    """Durak isminin UI'da gösterilmeye uygun olup olmadığını kontrol eder.

    Geçersiz kabul edilen isimler:
        - İçinde '-' geçenler (hat isimleri: Kadıköy-Beşiktaş)
        - İçinde _suffix geçenler (Kadıköy_EMN)
        - Geçersiz kelime içerenler (Turyol, İDO, Adalar, BUDO, Dentur)
        - Sonu sayı ile bitenler (Kadıköy2)
        - 'Yeni' veya 'Eski' prefix'li varyantlar

    Returns: True → UI'da gösterilebilir, False → gizlenmeli
    """
    if not name or not name.strip():
        return False
    if '-' in name:
        return False
    if '_' in name:
        return False
    if _GECERSIZ_KELIME_RE.search(name):
        return False
    if _SONU_SAYI_RE.search(name):
        return False
    lower = name.lower()
    if lower.startswith('yeni ') or lower.startswith('eski '):
        return False
    return True


def turkce_normalize(text: str) -> str:
    """Türkçe karakterleri ASCII eşdeğerine dönüştürür (arama için).
    'Kadıköy' → 'kadikoy'
    """
    result = text.lower()
    for tr_char, ascii_char in _TURKCE_NORMALIZE.items():
        result = result.replace(tr_char, ascii_char.lower())
    return result


def canonical_map_olustur(istasyonlar: set[str] | list[str]) -> dict[str, list[str]]:
    """İstasyon kümesinden canonical_name → [gerçek_adlar] eşleşmesi üretir.

    Sadece is_valid_stop() geçen canonical isimler dahil edilir.
    Tüm varyantlar (geçersizler dahil) routing için listeye eklenir.

    Complexity: O(n) — n = istasyon sayısı
    """
    cmap: dict[str, list[str]] = defaultdict(list)
    for ad in istasyonlar:
        canon = canonical_name(ad)
        if canon:
            cmap[canon].append(ad)
    for v in cmap.values():
        v.sort()
    return dict(cmap)


def get_clean_stop_list(istasyonlar: set[str] | list[str]) -> list[str]:
    """UI dropdown için temiz, benzersiz, sıralı canonical isim listesi döndürür.

    Filtreleme: is_valid_stop() ile geçersiz canonical isimler elenir.
    Sonuç: kullanıcının göreceği sade liste.

    Complexity: O(n log n) — sort dahil
    """
    cmap = canonical_map_olustur(istasyonlar)
    return sorted(canon for canon in cmap if is_valid_stop(canon))


def durak_ara(
    sorgu: str,
    istasyonlar: set[str] | list[str],
    max_sonuc: int = 10,
) -> list[str]:
    """Autocomplete için Türkçe-duyarlı durak arama.

    Hem orijinal hem de ASCII-normalized formda prefix eşleşmesi yapar.
    Küçük/büyük harf duyarsız. Max 10 sonuç.

    Complexity: O(n) — n = canonical isim sayısı
    """
    if not sorgu or not sorgu.strip():
        return []

    sorgu_temiz = sorgu.strip().lower()
    sorgu_ascii = turkce_normalize(sorgu)

    temiz_liste = get_clean_stop_list(istasyonlar)
    sonuclar: list[str] = []

    for ad in temiz_liste:
        ad_lower = ad.lower()
        ad_ascii = turkce_normalize(ad)
        if ad_lower.startswith(sorgu_temiz) or ad_ascii.startswith(sorgu_ascii):
            sonuclar.append(ad)
            if len(sonuclar) >= max_sonuc:
                break

    return sonuclar


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def gtfs_saati_dakikaya_cevir(saat_str: str) -> int:
    parcalar = saat_str.strip().split(":")
    return int(parcalar[0]) * 60 + int(parcalar[1])


def sure_hesapla(dep_str: str, arr_str: str) -> int:
    fark = gtfs_saati_dakikaya_cevir(arr_str) - gtfs_saati_dakikaya_cevir(dep_str)
    return max(1, abs(fark))


def durak_adini_temizle(ad: str, stop_id: str) -> str:
    if not ad or not ad.strip():
        return f"Durak_{stop_id}"
    ad = ad.strip()
    
    # Vapur hub'larını tespit et ve temizle (örn: Beşiktaş-Kadıköy -> Beşiktaş)
    # Bu sayede aktarma motoru bu durakları aynı merkezde toplar ve kullanıcı aramalarında kolay bulunur.
    vapur_merkezleri = ["Beşiktaş", "Kadıköy", "Üsküdar", "Eminönü", "Karaköy", "Kabataş", "Bostancı", "Adalar", "Bakırköy", "Yenikapı", "Sirkeci", "Harem"]
    
    # Case-insensitive ve Türkçe karakter duyarlı kontrol için geçici normalize ad
    norm_ad = ad.replace("İ", "i").replace("I", "ı").lower()
    for m in vapur_merkezleri:
        norm_m = m.replace("İ", "i").replace("I", "ı").lower()
        if norm_ad.startswith(norm_m + "-") or norm_ad.startswith(norm_m + " "):
            ad = m
            break
            
    ad = _SONEK_KALIP.sub("", ad).strip()
    if not ad:
        return f"Durak_{stop_id}"
    ilk = ad[0]
    ad = _TURKCE_BUYUK.get(ilk, ilk.upper()) + ad[1:]

    # ── Bilinen yazım varyantı düzeltmeleri ───────────────────────────────
    ad = ad.replace("Ayrılıkçeşme", "Ayrılık Çeşmesi")
    ad = ad.replace("Eminönü-Kadıköy", "Eminönü")
    ad = ad.replace("Eminönü-Boğaz",   "Eminönü")

    return ad


# ── Ana ETL fonksiyonu ────────────────────────────────────────────────────────

def istanbul_grafi_olustur(
    gtfs_klasoru: str = "data/gtfs",
    sadece_rayli: bool = True,
    verbose: bool = True,
) -> Graf:
    """
    İBB Açık Veri GTFS dosyalarını okuyup multigraf oluşturur.

    Parametreler:
        gtfs_klasoru : CSV'lerin bulunduğu klasör yolu
        sadece_rayli : True → sadece type 0,1,2,4,6,7
                       False → tüm hatlar (dikkat: çok büyük!)
        verbose      : True → ilerleme mesajları (CLI); False → sessiz (web)

    Dönüş: Gerçek İstanbul toplu taşıma multigrafı

    Karmaşıklık:
        stops okuma    : O(n)
        routes okuma   : O(r)
        trips okuma    : O(t)
        stop_times     : O(s log s) — sıralama darboğazı
        kenar çıkarımı : O(s)
        Toplam         : O(s log s)

    AYRIK MATEMATİK:
        ETL süreci ilişkisel bir bileşim işlemidir:
        StopTimes ⋈ Trips ⋈ Routes → E kümesinin elemanları
        (⋈ = doğal birleşim, trip_id ve route_id üzerinden)
    """

    def _log(mesaj: str) -> None:
        if verbose:
            print(mesaj)

    routes_dosya     = os.path.join(gtfs_klasoru, "routes.csv")
    stops_dosya      = os.path.join(gtfs_klasoru, "stops.csv")
    trips_dosya      = os.path.join(gtfs_klasoru, "trips.csv")
    stop_times_dosya = os.path.join(gtfs_klasoru, "stop_times.csv")

    graf = Graf()
    atlanan_satirlar = 0

    # ── ADIM 1: routes.csv oku  — O(r) ───────────────────────────────────────
    _log("ADIM 1: routes.csv okunuyor...")

    guzergahlar: dict[str, dict[str, Any]] = {}

    try:
        with open(routes_dosya, encoding="cp1254", newline="") as f:
            for satir in csv.DictReader(f, delimiter=","):
                if satir is None:
                    continue
                tur_str = (satir.get("route_type") or "").strip()
                if not tur_str:
                    atlanan_satirlar += 1
                    continue
                try:
                    tur = int(tur_str)
                except ValueError:
                    atlanan_satirlar += 1
                    continue
                if sadece_rayli and tur in FILTRELENEN_TIPLER:
                    continue
                route_id = (satir.get("route_id") or "").strip()
                kisa_ad  = (satir.get("route_short_name") or "").strip()
                if not route_id:
                    atlanan_satirlar += 1
                    continue
                guzergahlar[route_id] = {
                    "kisa_ad": kisa_ad or route_id,
                    "tur": tur,
                }
    except FileNotFoundError:
        raise FileNotFoundError(
            f"routes.csv bulunamadı. '{gtfs_klasoru}/' klasörüne koyduğunuzdan emin olun."
        )

    _log(f"  {len(guzergahlar):,} hat yüklendi.")

    # ── ADIM 2: stops.csv oku  — O(n) ────────────────────────────────────────
    _log("ADIM 2: stops.csv okunuyor...")

    duraklar:     dict[str, str]                 = {}
    koordinatlar: dict[str, tuple[float, float]] = {}

    try:
        with open(stops_dosya, encoding="utf-8-sig", newline="") as f:
            for satir in csv.DictReader(f, delimiter=","):
                stop_id   = (satir.get("stop_id") or "").strip()
                stop_name = (satir.get("stop_name") or "").strip()
                if not stop_id:
                    continue
                duraklar[stop_id] = durak_adini_temizle(stop_name, stop_id)
                try:
                    lat = float((satir.get("stop_lat") or 0))
                    lon = float((satir.get("stop_lon") or 0))
                    koordinatlar[stop_id] = (lat, lon)
                except (ValueError, TypeError):
                    koordinatlar[stop_id] = (0.0, 0.0)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"stops.csv bulunamadı. '{gtfs_klasoru}/' klasörüne koyduğunuzdan emin olun."
        )

    _log(f"  {len(duraklar):,} durak yüklendi.")

    # ── ADIM 3: trips.csv oku  — O(t) ────────────────────────────────────────
    _log("ADIM 3: trips.csv okunuyor...")

    seferler: dict[str, str] = {}

    try:
        with open(trips_dosya, encoding="utf-8-sig", newline="") as f:
            for satir in csv.DictReader(f, delimiter=","):
                route_id = (satir.get("route_id") or "").strip()
                trip_id  = (satir.get("trip_id") or "").strip()
                if route_id in guzergahlar and trip_id:
                    seferler[trip_id] = route_id
    except FileNotFoundError:
        raise FileNotFoundError(
            f"trips.csv bulunamadı. '{gtfs_klasoru}/' klasörüne koyduğunuzdan emin olun."
        )

    _log(f"  {len(seferler):,} sefer yüklendi.")

    # ── ADIM 4: stop_times.csv oku ve grupla  — O(s) ─────────────────────────
    _log("ADIM 4: stop_times.csv okunuyor (büyük dosya)...")

    sefer_duraklari: dict[str, list[dict[str, Any]]] = defaultdict(list)
    satir_no = 0

    try:
        with open(stop_times_dosya, encoding="cp1254", newline="") as f:
            for satir in csv.DictReader(f, delimiter=","):
                satir_no += 1
                if satir_no % 100_000 == 0:
                    _log(f"  stop_times: {satir_no:,} satır işlendi...")

                trip_id = (satir.get("trip_id") or "").strip()
                if trip_id not in seferler:
                    continue

                stop_id   = (satir.get("stop_id") or "").strip()
                seq_str   = (satir.get("stop_sequence") or "").strip()
                arrival   = (satir.get("arrival_time") or "").strip()
                departure = (satir.get("departure_time") or "").strip()

                if not all([stop_id, seq_str, arrival, departure]):
                    atlanan_satirlar += 1
                    continue

                try:
                    sefer_duraklari[trip_id].append({
                        "stop_id":   stop_id,
                        "sequence":  int(seq_str),
                        "arrival":   arrival,
                        "departure": departure,
                    })
                except (ValueError, KeyError):
                    atlanan_satirlar += 1

    except FileNotFoundError:
        raise FileNotFoundError(
            f"stop_times.csv bulunamadı. '{gtfs_klasoru}/' klasörüne koyduğunuzdan emin olun."
        )

    _log(
        f"  Toplam {satir_no:,} satır tarandı, "
        f"{len(sefer_duraklari):,} sefer grubu oluşturuldu."
    )

    # ── ADIM 5: Düğümleri (V) ekle  — O(aktif_durak) ────────────────────────
    _log("ADIM 5: İstasyonlar grafa ekleniyor...")

    aktif_stop_idler: set[str] = set()
    for durak_listesi in sefer_duraklari.values():
        for durak in durak_listesi:
            aktif_stop_idler.add(durak["stop_id"])

    for stop_id in aktif_stop_idler:  # YENİ: stop_id bazlı node
        temiz_ad = duraklar.get(stop_id)
        if temiz_ad:
            koord = koordinatlar.get(stop_id, (0.0, 0.0))  # YENİ
            meta = {  # YENİ
                "stop_id":   stop_id,  # YENİ
                "stop_name": temiz_ad,  # YENİ
                "stop_lat":  koord[0],  # YENİ
                "stop_lon":  koord[1],  # YENİ
            }  # YENİ
            try:
                graf.istasyon_ekle(stop_id, metadata=meta)  # YENİ: stop_id
            except ValueError:
                atlanan_satirlar += 1

    _log(f"  {graf.istasyon_sayisi():,} istasyon grafa eklendi.")

    # ── ADIM 6: Kenarları (E) çıkar  — O(s log s) sıralama + O(s) pencere ───
    _log("ADIM 6: Kenarlar çıkarılıyor (kayan pencere)...")

    eklenen_kenar = 0
    atlanan_kenar = 0

    for trip_id, durak_listesi in sefer_duraklari.items():
        route_id = seferler[trip_id]
        guzergah = guzergahlar[route_id]
        hat_adi  = guzergah["kisa_ad"]
        tur      = guzergah["tur"]
        hat_tipi = ROUTE_TYPE_ETIKETLERI.get(tur, "Diğer")
        renk     = HAT_OZEL_RENKLERI.get(hat_adi, HAT_TIPI_RENKLERI.get(tur, "#808080"))

        # stop_sequence bazı feed'lerde azalan sırada gelebilir — kritik düzeltme
        siralanmis = sorted(durak_listesi, key=lambda x: int(x["sequence"]))

        for i in range(len(siralanmis) - 1):
            a = siralanmis[i]
            b = siralanmis[i + 1]

            if a["stop_id"] not in duraklar or b["stop_id"] not in duraklar:
                continue

            sid_a = a["stop_id"]  # YENİ: stop_id bazlı kenar
            sid_b = b["stop_id"]  # YENİ

            if sid_a == sid_b:  # YENİ: self-loop kontrolü
                atlanan_kenar += 1
                continue

            sure = sure_hesapla(a["departure"], b["arrival"])

            try:
                graf.hat_ekle(sid_a, sid_b, hat_tipi, hat_adi, sure, renk)  # YENİ
                eklenen_kenar += 1
            except ValueError:
                atlanan_kenar += 1

    _log(
        f"  {eklenen_kenar:,} kenar eklendi, "
        f"{atlanan_kenar:,} duplicate/self-loop atlandı."
    )

    if atlanan_satirlar > 0:
        _log(f"  Uyarı: {atlanan_satirlar:,} eksik/bozuk satır atlandı.")

    # ── ADIM 6.5: stop_name → stop_id ters-lookup oluştur ──────────────────  # YENİ
    # Aktarma ve yürüme kenarları stop_name bazlı tanımlı;  # YENİ
    # stop_id bazlı grafa bağlamak için ters eşleşme gerekli.  # YENİ
    ad_to_stop_ids: dict[str, list[str]] = defaultdict(list)  # YENİ
    for sid in aktif_stop_idler:  # YENİ
        temiz = duraklar.get(sid)  # YENİ
        if temiz:  # YENİ
            ad_to_stop_ids[temiz].append(sid)  # YENİ

    # AKTARMA_NOKTALARI için sanal kenar enjeksiyonu  # YENİ
    # Aynı istasyon adındaki farklı stop_id'ler arası aktarma kenarı  # YENİ
    sanal_eklenen = 0
    for istasyon_adi, _hatlar in AKTARMA_NOKTALARI.items():  # YENİ
        stop_ids = ad_to_stop_ids.get(istasyon_adi, [])  # YENİ
        for i in range(len(stop_ids)):  # YENİ
            for j in range(i + 1, len(stop_ids)):  # YENİ
                try:  # YENİ
                    graf.hat_ekle(  # YENİ
                        stop_ids[i], stop_ids[j],  # YENİ
                        "Aktarma",  # YENİ
                        "aktarma_" + istasyon_adi,  # YENİ
                        3,  # YENİ
                        "#888888",  # YENİ
                    )  # YENİ
                    sanal_eklenen += 1  # YENİ
                except Exception:  # YENİ
                    pass  # YENİ
                try:  # YENİ — ters yön
                    graf.hat_ekle(  # YENİ
                        stop_ids[j], stop_ids[i],  # YENİ
                        "Aktarma",  # YENİ
                        "aktarma_" + istasyon_adi,  # YENİ
                        3,  # YENİ
                        "#888888",  # YENİ
                    )  # YENİ
                    sanal_eklenen += 1  # YENİ
                except Exception:  # YENİ
                    pass  # YENİ
    _log(f"  {sanal_eklenen} sanal aktarma kenarı eklendi.")

    # ── ADIM 6.6: Birleşik vapur durakları ↔ tekil duraklar arası yürüme ─────
    YURUME_BAGLANTILARI = [
        ("Beşiktaş-Üsküdar", "Beşiktaş"),
        ("Beşiktaş-Üsküdar", "Üsküdar"),
        ("Karaköy",          "Eminönü"),
    ]
    yurume_eklenen = 0
    for ad_a, ad_b in YURUME_BAGLANTILARI:  # YENİ
        ids_a = ad_to_stop_ids.get(ad_a, [])  # YENİ
        ids_b = ad_to_stop_ids.get(ad_b, [])  # YENİ
        for sid_a in ids_a:  # YENİ
            for sid_b in ids_b:  # YENİ
                try:  # YENİ
                    graf.hat_ekle(sid_a, sid_b, "Yürüme", "yurume", 3, "#888888")  # YENİ
                    yurume_eklenen += 1  # YENİ
                except Exception:  # YENİ
                    pass  # YENİ
                try:  # YENİ — ters yön
                    graf.hat_ekle(sid_b, sid_a, "Yürüme", "yurume", 3, "#888888")  # YENİ
                    yurume_eklenen += 1  # YENİ
                except Exception:  # YENİ
                    pass  # YENİ
    _log(f"  {yurume_eklenen} yürüme kenarı eklendi.")

    # ── ADIM 7: JSON çıktısı  — O(|V| + |E|) ─────────────────────────────────
    _log("ADIM 7: JSON çıktısı yazılıyor...")

    gtfs_abs  = os.path.abspath(gtfs_klasoru)
    json_yolu = os.path.join(os.path.dirname(gtfs_abs), "istanbul_graf.json")
    os.makedirs(os.path.dirname(json_yolu), exist_ok=True)

    with open(json_yolu, "w", encoding="utf-8") as f:
        json.dump(graf.to_dict(), f, ensure_ascii=False, indent=2)

    _log(f"  JSON yazıldı → {json_yolu}")

    return graf


# ── Otobüs Entegrasyonu ──────────────────────────────────────────────────────  # YENİ


# YENİ: Nominatim reverse geocoding ile ilçe tespiti
import time as _time  # YENİ
import urllib.request as _urllib  # YENİ

_ILCE_CACHE: dict[tuple[float, float], str | None] = {}  # YENİ — (lat_r, lon_r) → ilçe
_ILCE_CACHE_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ilce_cache.json")  # YENİ


def _ilce_cache_yukle() -> None:  # YENİ
    """Disk cache'ini belleğe yükler."""  # YENİ
    global _ILCE_CACHE  # YENİ
    if os.path.exists(_ILCE_CACHE_YOLU):  # YENİ
        try:  # YENİ
            with open(_ILCE_CACHE_YOLU, encoding="utf-8") as f:  # YENİ
                for k, v in json.load(f).items():  # YENİ
                    lat_s, lon_s = k.split(",")  # YENİ
                    _ILCE_CACHE[(float(lat_s), float(lon_s))] = v  # YENİ
            print(f"  {len(_ILCE_CACHE)} ilçe cache kaydı yüklendi.")  # YENİ
        except Exception:  # YENİ
            pass  # YENİ


def _ilce_cache_kaydet() -> None:  # YENİ
    """Bellek cache'ini diske yazar."""  # YENİ
    try:  # YENİ
        with open(_ILCE_CACHE_YOLU, "w", encoding="utf-8") as f:  # YENİ
            json.dump(  # YENİ
                {f"{k[0]},{k[1]}": v for k, v in _ILCE_CACHE.items()},  # YENİ
                f, ensure_ascii=False, indent=2,  # YENİ
            )  # YENİ
    except OSError:  # YENİ
        pass  # YENİ


_ilce_cache_yukle()  # YENİ — modül yüklenince cache'i oku


def _ilce_bul(lat: float, lon: float) -> str | None:  # YENİ
    """Nominatim reverse geocoding ile ilçe adı döndürür; disk cache'li."""  # YENİ
    anahtar = (round(lat, 2), round(lon, 2))  # YENİ — ~1km hassasiyet
    if anahtar in _ILCE_CACHE:  # YENİ
        return _ILCE_CACHE[anahtar]  # YENİ
    try:  # YENİ
        url = (  # YENİ
            f"https://nominatim.openstreetmap.org/reverse"  # YENİ
            f"?lat={lat}&lon={lon}&format=json&accept-language=tr"  # YENİ
        )  # YENİ
        req = _urllib.Request(url, headers={"User-Agent": "istanbul-nav/1.0"})  # YENİ
        with _urllib.urlopen(req, timeout=5) as r:  # YENİ
            veri = json.loads(r.read())  # YENİ
        adres = veri.get("address", {})  # YENİ
        ilce = (  # YENİ
            adres.get("district")  # YENİ
            or adres.get("town")  # YENİ
            or adres.get("city_district")  # YENİ
            or adres.get("suburb")  # YENİ
            or adres.get("county")  # YENİ
            or None  # YENİ
        )  # YENİ
        _ILCE_CACHE[anahtar] = ilce  # YENİ
        _time.sleep(1.1)  # YENİ — Nominatim rate limit: max 1 istek/sn
        return ilce  # YENİ
    except Exception:  # YENİ
        _ILCE_CACHE[anahtar] = None  # YENİ
        return None  # YENİ


def disambiguate_stop_names(  # YENİ
    graf: "Graf",  # YENİ
    stop_name_to_ids: dict[str, list[str]],  # YENİ
    stop_id_to_name: dict[str, str],  # YENİ
    mesafe_esik_km: float = 0.5,  # YENİ
) -> None:  # YENİ
    """
    Aynı isimde birden fazla FARKLI lokasyonda bulunan durakları
    ilçe/bölge adıyla ayırt eder.  In-place güncelleme yapar.

    "Bülbül Sokak" → "Bülbül Sokak (Sultanbeyli)", "Bülbül Sokak (Ümraniye)"

    Kurallar:
    - Aynı isimli stop_id'lerin koordinatları 500m'den yakınsa → tek lokasyon, dokunma
    - 500m'den uzaksa → farklı lokasyon, ilçe adı ekle
    - İlçe bulunamazsa stop_id prefix fallback
    - Eski belirsiz isim silinir, yeni isimler eklenir
    """  # YENİ
    isimler_to_process = [  # YENİ
        (name, sids) for name, sids in list(stop_name_to_ids.items())  # YENİ
        if len(sids) >= 2  # YENİ
    ]  # YENİ

    degisen = 0  # YENİ
    for name, sids in isimler_to_process:  # YENİ
        # ── Her stop_id için koordinat topla ─────────────────────────  # YENİ
        koord_gruplar: list[tuple[list[str], float, float]] = []  # YENİ
        for sid in sids:  # YENİ
            meta = graf.node_meta(sid)  # YENİ
            if not meta:  # YENİ
                continue  # YENİ
            lat = meta.get("stop_lat") or meta.get("lat") or 0.0  # YENİ
            lon = meta.get("stop_lon") or meta.get("lon") or 0.0  # YENİ
            if lat == 0.0 and lon == 0.0:  # YENİ
                continue  # YENİ
            # Mevcut gruplara yakın mı?  # YENİ
            yerlestirildi = False  # YENİ
            for grup in koord_gruplar:  # YENİ
                g_sids, g_lat, g_lon = grup  # YENİ
                if _haversine(lat, lon, g_lat, g_lon) < mesafe_esik_km:  # YENİ
                    g_sids.append(sid)  # YENİ
                    yerlestirildi = True  # YENİ
                    break  # YENİ
            if not yerlestirildi:  # YENİ
                koord_gruplar.append(([sid], lat, lon))  # YENİ

        if len(koord_gruplar) < 2:  # YENİ
            continue  # YENİ

        # ── Birden fazla farklı lokasyon var → disambiguate ──────────  # YENİ
        del stop_name_to_ids[name]  # YENİ

        for grup_sids, g_lat, g_lon in koord_gruplar:  # YENİ
            # İlçe bul  # YENİ
            ilce = None  # YENİ
            # 1. category metadata'dan  # YENİ
            for sid in grup_sids:  # YENİ
                meta = graf.node_meta(sid) or {}  # YENİ
                cat = meta.get("category", "")  # YENİ
                if cat:  # YENİ
                    ilce = cat  # YENİ
                    break  # YENİ
            # 2. koordinattan bbox  # YENİ
            if not ilce:  # YENİ
                ilce = _ilce_bul(g_lat, g_lon)  # YENİ
            # 3. fallback  # YENİ
            if not ilce:  # YENİ
                ilce = f"Bölge-{grup_sids[0][:3]}"  # YENİ

            yeni_isim = f"{name} ({ilce})"  # YENİ
            stop_name_to_ids[yeni_isim] = grup_sids  # YENİ
            for sid in grup_sids:  # YENİ
                stop_id_to_name[sid] = yeni_isim  # YENİ
        degisen += 1  # YENİ

    if degisen > 0:  # YENİ
        _ilce_cache_kaydet()  # YENİ
        print(f"  İlçe cache'i güncellendi → data/ilce_cache.json")  # YENİ
        print(f"  {degisen} belirsiz durak adı ilçe bilgisiyle ayrıştırıldı.")  # YENİ


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:  # YENİ
    """İki koordinat arası mesafeyi km olarak döndürür (Haversine formülü)."""  # YENİ
    R = 6371  # YENİ
    dlat = math.radians(lat2 - lat1)  # YENİ
    dlon = math.radians(lon2 - lon1)  # YENİ
    a = (math.sin(dlat / 2) ** 2  # YENİ
         + math.cos(math.radians(lat1))  # YENİ
         * math.cos(math.radians(lat2))  # YENİ
         * math.sin(dlon / 2) ** 2)  # YENİ
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))  # YENİ


def _en_yakin_komsu_sayisi(durak: tuple, tum_duraklar: list, esik_km: float = 0.5) -> int:  # YENİ
    """Bir durağın esik_km içindeki komşu sayısını döndürür."""  # YENİ
    sayi = 0  # YENİ
    for d in tum_duraklar:  # YENİ
        if d[0] == durak[0]:  # YENİ
            continue  # YENİ
        if _haversine(durak[1], durak[2], d[1], d[2]) <= esik_km:  # YENİ
            sayi += 1  # YENİ
    return sayi  # YENİ


def _uc_durak_bul(duraklar: list) -> tuple:  # YENİ
    """
    Hat için en mantıklı başlangıç noktasını döner.
    Input: [(stop_id, lat, lon, stop_name, stop_code), ...]
    Öncelik:
        1. Zincir ucu: sadece 1 yakın komşusu olan durak (degree=1)
        2. Fallback: en kuzeybatı durak (score = lat - lon)
    """  # YENİ
    if len(duraklar) <= 2:  # YENİ
        return duraklar[0]  # YENİ
    en_az = None  # YENİ
    en_az_sayi = float("inf")  # YENİ
    for d in duraklar:  # YENİ
        s = _en_yakin_komsu_sayisi(d, duraklar)  # YENİ
        if s < en_az_sayi:  # YENİ
            en_az_sayi = s  # YENİ
            en_az = d  # YENİ
    if en_az is not None and en_az_sayi == 1:  # YENİ
        return en_az  # YENİ
    return max(duraklar, key=lambda d: d[1] - d[2])  # YENİ


def _nearest_neighbor_sirala(stop_list: list) -> list:  # YENİ
    """Nearest-neighbor sıralaması. Input: [(stop_id, lat, lon, ...)] formatında tuple listesi."""  # YENİ
    if len(stop_list) <= 1:  # YENİ
        return list(stop_list)  # YENİ
    kalan = list(stop_list)  # YENİ
    baslangic = _uc_durak_bul(kalan)  # YENİ
    kalan.remove(baslangic)  # YENİ
    siralanan = [baslangic]  # YENİ
    while kalan:  # YENİ
        son = siralanan[-1]  # YENİ
        en_yakin_idx = 0  # YENİ
        en_yakin_mesafe = float("inf")  # YENİ
        for i, durak in enumerate(kalan):  # YENİ
            d = _haversine(son[1], son[2], durak[1], durak[2])  # YENİ
            if d < en_yakin_mesafe:  # YENİ
                en_yakin_mesafe = d  # YENİ
                en_yakin_idx = i  # YENİ
        siralanan.append(kalan.pop(en_yakin_idx))  # YENİ
    return siralanan  # YENİ


def otobus_hatlari_yukle(csv_yolu: str, graf: "Graf", hat_stop_cache: dict = None) -> int:  # YENİ
    """24 İETT otobüs hattını CSV'den okuyup grafa ekler. Eklenen kenar sayısını döndürür."""  # YENİ
    eklenen_kenar = 0  # YENİ

    # CSV oku ve hat bazında grupla  # YENİ
    hatlar: dict[str, list[tuple]] = defaultdict(list)  # YENİ
    with open(csv_yolu, encoding="utf-8-sig", newline="") as f:  # YENİ
        for satir in csv.DictReader(f):  # YENİ
            route = (satir.get("route_short_name") or "").strip()  # YENİ
            stop_id = (satir.get("stop_id") or "").strip()  # YENİ
            stop_name = (satir.get("stop_name") or "").strip()  # YENİ
            stop_code_raw = (satir.get("stop_code") or "").strip()  # YENİ
            lat_s = (satir.get("stop_lat") or "").strip()  # YENİ
            lon_s = (satir.get("stop_lon") or "").strip()  # YENİ
            if not route or not stop_id:  # YENİ
                continue  # YENİ
            try:  # YENİ
                lat = float(lat_s)  # YENİ
                lon = float(lon_s)  # YENİ
            except (ValueError, TypeError):  # YENİ
                continue  # YENİ
            # stop_code temizleme: "222092.0" → "222092", NaN → ""  # YENİ
            stop_code = ""  # YENİ
            if stop_code_raw:  # YENİ
                try:  # YENİ
                    stop_code = str(int(float(stop_code_raw)))  # YENİ
                except (ValueError, TypeError):  # YENİ
                    stop_code = ""  # YENİ
            hatlar[route].append((stop_id, lat, lon, stop_name, stop_code))  # YENİ

    for hat_adi, duraklar in hatlar.items():  # YENİ
        # stop_code'a göre sırala; boş olanları sona at  # YENİ
        duraklar.sort(key=lambda d: (d[4] == "", d[4]))  # YENİ

        # Ardışık mesafe kontrolü: 2 km üstü varsa nearest-neighbor'a geç  # YENİ
        siralama_hatali = False  # YENİ
        for i in range(len(duraklar) - 1):  # YENİ
            mesafe = _haversine(duraklar[i][1], duraklar[i][2],  # YENİ
                                duraklar[i + 1][1], duraklar[i + 1][2])  # YENİ
            if mesafe > 2.0:  # YENİ
                siralama_hatali = True  # YENİ
                break  # YENİ

        if siralama_hatali:  # YENİ
            duraklar = _nearest_neighbor_sirala(duraklar)  # YENİ

        # YENİ: Cache'e sadece ileri yönü yaz
        if hat_stop_cache is not None:  # YENİ
            # Nearest-neighbor sıralaması karşılıklı durakları (aynı isim,  # YENİ
            # farklı stop_id) yanyana koyar. İleri yön listesi oluşturmak  # YENİ
            # için: ardışık aynı isimli durak çiftlerinden sadece ilkini al  # YENİ
            # + başlangıçtan en uzak noktaya kadar kes.  # YENİ
            ileri: list[tuple] = []  # YENİ
            for d in duraklar:  # YENİ
                if ileri and d[3] == ileri[-1][3]:  # YENİ — aynı stop_name
                    continue  # YENİ — karşı yön durağı, atla
                ileri.append(d)  # YENİ
            # En uzak durak = geri dönüş noktası  # YENİ
            if len(ileri) >= 4:  # YENİ
                bas_lat, bas_lon = ileri[0][1], ileri[0][2]  # YENİ
                en_uzak_idx = 0  # YENİ
                en_uzak_mesafe = 0.0  # YENİ
                for idx, d in enumerate(ileri):  # YENİ
                    mesafe = _haversine(bas_lat, bas_lon, d[1], d[2])  # YENİ
                    if mesafe > en_uzak_mesafe:  # YENİ
                        en_uzak_mesafe = mesafe  # YENİ
                        en_uzak_idx = idx  # YENİ
                ileri = ileri[:en_uzak_idx + 1]  # YENİ
            hat_stop_cache[hat_adi] = [d[0] for d in ileri]  # YENİ

        # Node'ları grafa ekle  # YENİ
        for stop_id, lat, lon, stop_name, _ in duraklar:  # YENİ
            try:  # YENİ
                graf.istasyon_ekle(  # YENİ
                    stop_id,  # YENİ
                    metadata={  # YENİ
                        "name": stop_name,  # YENİ
                        "lat": lat,  # YENİ
                        "lon": lon,  # YENİ
                        "type": "otobus",  # YENİ
                    },  # YENİ
                )  # YENİ
            except ValueError:  # YENİ
                pass  # YENİ

        # İleri yön kenarları  # YENİ
        for i in range(len(duraklar) - 1):  # YENİ
            sid_a, lat_a, lon_a = duraklar[i][0], duraklar[i][1], duraklar[i][2]  # YENİ
            sid_b, lat_b, lon_b = duraklar[i + 1][0], duraklar[i + 1][1], duraklar[i + 1][2]  # YENİ
            mesafe_km = _haversine(lat_a, lon_a, lat_b, lon_b)  # YENİ
            sure = round((mesafe_km / 22) * 60)  # YENİ
            if sure <= 0:  # YENİ
                sure = 2.5  # YENİ
            sure = max(1, int(round(sure))) if sure != 2.5 else 3  # YENİ
            try:  # YENİ
                graf.hat_ekle(sid_a, sid_b, "otobüs", hat_adi, sure, "#FF6600")  # YENİ
                eklenen_kenar += 1  # YENİ
            except (ValueError, Exception):  # YENİ
                pass  # YENİ

        # Ters yön kenarları  # YENİ
        for i in range(len(duraklar) - 1, 0, -1):  # YENİ
            sid_a, lat_a, lon_a = duraklar[i][0], duraklar[i][1], duraklar[i][2]  # YENİ
            sid_b, lat_b, lon_b = duraklar[i - 1][0], duraklar[i - 1][1], duraklar[i - 1][2]  # YENİ
            mesafe_km = _haversine(lat_a, lon_a, lat_b, lon_b)  # YENİ
            sure = round((mesafe_km / 22) * 60)  # YENİ
            if sure <= 0:  # YENİ
                sure = 2.5  # YENİ
            sure = max(1, int(round(sure))) if sure != 2.5 else 3  # YENİ
            try:  # YENİ
                graf.hat_ekle(sid_a, sid_b, "otobüs", hat_adi, sure, "#FF6600")  # YENİ
                eklenen_kenar += 1  # YENİ
            except (ValueError, Exception):  # YENİ
                pass  # YENİ

    return eklenen_kenar  # YENİ


# ── Demo çalıştırma ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("İBB GTFS verisi yükleniyor...\n")

    try:
        graf = istanbul_grafi_olustur(
            gtfs_klasoru="data/gtfs",
            sadece_rayli=True,
            verbose=True,
        )
    except FileNotFoundError as hata:
        print(f"\nHATA: {hata}")
        sys.exit(1)

    print()

    v = graf.istasyon_sayisi()
    e = graf.hat_sayisi()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     İSTANBUL TOPLU TAŞIMA MULTİGRAFI — İBB GTFS    ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  İstasyon sayısı    |V| = {v:<6}                  ║")
    print(f"║  Hat (kenar) sayısı |E| = {e:<6}                  ║")
    print( "║  Kaynak: data.ibb.gov.tr (GTFS, 2023)               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    hat_tipleri_sayisi: dict[str, int] = defaultdict(int)
    for hat_verisi in graf.to_dict()["hatlar"]:
        hat_tipleri_sayisi[hat_verisi["hat_tipi"]] += 1

    print("Hat tipine göre kenar istatistikleri:")
    for etiket in ["Metro", "Tramvay", "Tren", "Vapur", "Teleferik", "Füniküler", "Diğer"]:
        sayi = hat_tipleri_sayisi.get(etiket, 0)
        if sayi > 0:
            print(f"  {etiket:<22}: {sayi:>5} kenar")
    print()

    # degree(v) = in_degree + out_degree = len(komsuluk[v])
    hub_analizi: dict[str, int] = {
        ist: len(graf.komsuluk[ist]) for ist in graf.istasyonlar
    }
    top_10 = sorted(hub_analizi.items(), key=lambda x: x[1], reverse=True)[:10]

    print("En çok bağlantılı 10 istasyon (hub analizi):")
    for sira, (istasyon, baglanti) in enumerate(top_10, start=1):
        print(f"  {sira:>2}. {istasyon:<32} — {baglanti:>3} bağlantı")
    print()

    cift_kenarlari: dict[tuple, list[str]] = defaultdict(list)
    for hat_verisi in graf.to_dict()["hatlar"]:
        anahtar = tuple(sorted([hat_verisi["baslangic"], hat_verisi["bitis"]]))
        cift_kenarlari[anahtar].append(hat_verisi["hat_adi"])

    multigraf_cifler = {k: v for k, v in cift_kenarlari.items() if len(v) >= 2}

    print(f"Multigraf örnekleri ({len(multigraf_cifler)} paralel kenar çifti):")
    ornekler = sorted(multigraf_cifler.items(), key=lambda x: -len(x[1]))[:5]
    for (ist_a, ist_b), hatlar in ornekler:
        print(f"  {ist_a} ↔ {ist_b}")
        for hat in hatlar:
            print(f"    • {hat}")
    print()

    json_dosyasi = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "istanbul_graf.json"
    )
    if os.path.exists(json_dosyasi):
        boyut_kb = os.path.getsize(json_dosyasi) / 1024
        print(f"JSON dosyası: data/istanbul_graf.json  ({boyut_kb:.1f} KB)")

    # ── İstenen özet doğrulama bloğu ──────────────────────────────
    print()
    print("=== GRAF BİLGİSİ ===")
    print(f"Toplam istasyon sayısı: {graf.istasyon_sayisi()}")
    print(f"Toplam kenar sayısı: {graf.hat_sayisi()}")
