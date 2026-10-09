# -*- coding: utf-8 -*-
"""
services/router.py — GTFS graph.pkl üzerinde Dijkstra rota motoru.

Mevcut bfs.py'ye dokunmadan çalışır.
app.py bunu import eder.
"""

import heapq
import pickle
import os
from typing import Any


def tr_lower(s: str) -> str:
    if not s:
        return ""
    return s.replace("İ", "i").replace("I", "ı").lower().replace("̇", "")


_TR_UPPER_MAP = str.maketrans(
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ",
    "abcçdefgğhıijklmnoöprsştuüvyz",
)


def _tr_title(s: str) -> str:
    if not s:
        return ""
    parts = []
    for kelime in s.split():
        if not kelime:
            continue
        alpha_idx = next((i for i, c in enumerate(kelime) if c.isalpha()), -1)
        if alpha_idx == -1:
            parts.append(kelime)
            continue
        prefix = kelime[:alpha_idx]
        rest = kelime[alpha_idx:]
        ilk = rest[0]
        if ilk == "I":
            yeni = "I"
        elif ilk == "İ":
            yeni = "İ"
        elif ilk == "i":
            yeni = "İ"
        elif ilk == "ı":
            yeni = "I"
        else:
            yeni = ilk.upper()
        parts.append(prefix + yeni + rest[1:].translate(_TR_UPPER_MAP))
    return " ".join(parts)

# ── Graph yükle (modül başlangıcında 1 kere) ─────────────────────────────────
_GRAPH_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "iett_graph.pkl")

_graph: dict = {}
_stop_meta: dict = {}
_loaded = False


def _load():
    global _graph, _stop_meta, _loaded
    if _loaded:
        return
    if not os.path.exists(_GRAPH_PATH):
        raise FileNotFoundError(
            f"graph.pkl bulunamadı: {_GRAPH_PATH}\n"
            "Önce çalıştır: python3 preprocess.py"
        )
    print(f"[router] graph.pkl yükleniyor → {_GRAPH_PATH}")
    with open(_GRAPH_PATH, "rb") as f:
        data = pickle.load(f)
    _graph    = data["graph"]
    _stop_meta = data["stop_meta"]

    # Aynı isimli + 80m altı yürüme kenarlarını filtrele (karşı kaldırım)
    import math as _m
    def _hav(la1,lo1,la2,lo2):
        R=6371000; dl=_m.radians(la2-la1); dlo=_m.radians(lo2-lo1)
        a=_m.sin(dl/2)**2+_m.cos(_m.radians(la1))*_m.cos(_m.radians(la2))*_m.sin(dlo/2)**2
        return R*2*_m.atan2(_m.sqrt(a),_m.sqrt(1-a))

    temizlenen = 0
    for sid in list(_graph.keys()):
        meta_a = _stop_meta.get(sid, {})
        isim_a = meta_a.get("name", "")
        lat_a, lon_a = meta_a.get("lat", 0), meta_a.get("lon", 0)
        yeni_edges = []
        for e in _graph[sid]:
            if e[2] == "YURUME":
                meta_b = _stop_meta.get(e[0], {})
                isim_b = meta_b.get("name", "")
                lat_b, lon_b = meta_b.get("lat", 0), meta_b.get("lon", 0)
                # Koordinatsız ama aynı isimli → karşı kaldırım, filtrele
                if isim_a and isim_a == isim_b:
                    temizlenen += 1
                    continue
                if lat_a and lat_b:
                    mesafe = _hav(lat_a, lon_a, lat_b, lon_b)
                    if mesafe < 5:
                        temizlenen += 1
                        continue
            yeni_edges.append(e)
        _graph[sid] = yeni_edges

    # Eksik koordinatları stops.csv'den tamamla
    import csv as _csv
    _stops_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "gtfs", "iett_stops.csv")
    if os.path.exists(_stops_csv):
        with open(_stops_csv, encoding="utf-8-sig", newline="") as _sf:
            for _row in _csv.DictReader(_sf):
                _sid = (_row.get("stop_id") or "").strip()
                if _sid in _graph and not _stop_meta.get(_sid):
                    try:
                        _lat = float(_row.get("stop_lat") or 0)
                        _lon = float(_row.get("stop_lon") or 0)
                    except (ValueError, TypeError):
                        _lat = _lon = 0.0
                    _stop_meta[_sid] = {
                        "name": (_row.get("stop_name") or "").strip(),
                        "lat": _lat,
                        "lon": _lon,
                    }

    # İlçe bilgisini ilce_cache.json'dan yükle (preprocess.py Nominatim cache)
    import json as _json
    _ilce_cache_yolu = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "data", "ilce_cache.json")
    _ilce_cache_raw: dict = {}
    if os.path.exists(_ilce_cache_yolu):
        try:
            with open(_ilce_cache_yolu, encoding="utf-8") as _cf:
                for _k, _v in _json.load(_cf).items():
                    _ilce_cache_raw[_k] = _v
        except Exception:
            pass

    _ilce_doldurulan = 0
    for _sid, _meta in _stop_meta.items():
        if _meta.get("ilce"):
            continue
        _lat_m = _meta.get("lat") or 0
        _lon_m = _meta.get("lon") or 0
        if _lat_m and _lon_m:
            _anahtar = f"{round(_lat_m, 2)},{round(_lon_m, 2)}"
            _ilce = _ilce_cache_raw.get(_anahtar)
            if _ilce:
                _meta["ilce"] = _ilce
                _ilce_doldurulan += 1

    _loaded   = True
    print(f"[router] {len(_graph):,} durak, hazır. ({temizlenen} karşı kaldırım kenarı temizlendi, {_ilce_doldurulan} ilçe cache'ten dolduruldu)")


# ── Sabitler ─────────────────────────────────────────────────────────────────

import math as _math

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """İki koordinat arası kuş uçuşu mesafe (km)."""
    R = 6371
    dlat = _math.radians(lat2 - lat1)
    dlon = _math.radians(lon2 - lon1)
    a = (_math.sin(dlat/2)**2
         + _math.cos(_math.radians(lat1))
         * _math.cos(_math.radians(lat2))
         * _math.sin(dlon/2)**2)
    return R * 2 * _math.atan2(_math.sqrt(a), _math.sqrt(1-a))


# Coğrafi olarak yanlış konumlandırılmış bilinen duraklar (Edge Case Hardcoding)
# İstanbul sınırı içinde ama yanlış ilçeye fırlatılmış kirli GTFS verisi
_YANLIS_KOORDINATLI_DURAKLAR = {
    "291476",  # SANCAKTEPE (41.20, 28.72) — Çatalca
    "291477",  # SANCAKTEPE (41.21, 28.72) — Çatalca
    "284538",  # SANCAKTEPE (41.07, 28.08) — Silivri
    "284539",  # SANCAKTEPE (41.07, 28.08) — Silivri
    "284581",  # SANCAKTEPE MEVKİİ (41.08, 28.21) — yanlış konum
    "284523",  # SANCAKTEPE MEVKİİ (41.08, 28.21) — yanlış konum
    "284773",  # KADIKÖY — sınır dışı, komşusuz
    "579305",  # MALTEPE (41.031, 28.916) — Avrupa yakası, yanlış konum
    "579306",  # MALTEPE (41.031, 28.916) — Avrupa yakası, yanlış konum
}

def en_iyi_id_sec(ids: list[str]) -> list[str]:
    # Kara listedeki hatalı durakları filtrele
    temiz_ids = [sid for sid in ids if sid not in _YANLIS_KOORDINATLI_DURAKLAR]
    # Temizlik sonrası liste boşalırsa orijinali kullan (sistem çökmesin)
    if temiz_ids:
        ids = temiz_ids
    """
    Birden fazla stop_id aynı durağa karşılık geliyorsa en mantıklıyı seç.

    Sancaktepe gibi durumlarda: İETT GTFS'te birden fazla 'SANCAKTEPE' durağı
    olabilir — biri gerçek Sancaktepe (41.0°N, 29.2°E civarı), biri yanlış
    koordinatlı (41.3°N gibi Arnavutköy tarafı).

    Seçim kriteri: Grafta en fazla komşusu olan (en aktif) durağı tercih et.
    Eşit komşu sayısında İstanbul merkezi (41.01, 28.97) koordinatına en yakını seç.
    """
    _load()
    if len(ids) <= 1:
        return ids

    # İstanbul coğrafi merkezi (yaklaşık)
    IST_LAT, IST_LON = 41.01, 28.97

    skorlar = []
    for sid in ids:
        komsu_sayisi = len(_graph.get(sid, []))
        meta = _stop_meta.get(sid, {})
        lat = meta.get("lat") or 0
        lon = meta.get("lon") or 0
        if lat and lon:
            ist_uzaklik = _haversine_km(lat, lon, IST_LAT, IST_LON)
        else:
            ist_uzaklik = 9999
        skorlar.append((sid, komsu_sayisi, ist_uzaklik))

    # Önce komşu sayısı (çok → iyi), sonra İstanbul'a uzaklık (az → iyi)
    skorlar.sort(key=lambda x: (-x[1], x[2]))

    # Sadece en iyi grubu döndür (komşu sayısı en yüksek olanlar)
    en_yuksek_komsu = skorlar[0][1]
    en_iyiler = [s[0] for s in skorlar if s[1] >= max(1, en_yuksek_komsu - 2)]
    return en_iyiler[:3]  # max 3 aday yeterli

def _heuristic(sid: str, hedef_koordinat: tuple | None) -> float:
    """A* heuristic: hedefe kuş uçuşu mesafe → tahmini dakika (30 km/h ortalama)."""
    if not hedef_koordinat:
        return 0.0
    m = _stop_meta.get(sid, {})
    lat, lon = m.get("lat"), m.get("lon")
    if not lat or not lon:
        return 0.0
    h_lat, h_lon = hedef_koordinat
    km = _haversine_km(lat, lon, h_lat, h_lon)
    return km / 30 * 60  # 30 km/h → dakika

# Aktarma cezaları (dakika cinsinden)
AKTARMA_CEZASI = {
    "hizli":   5,
    "aktarma": 999,
    "yurume":  5,
}

# Hat tipi öncelik cezası
TIP_CEZASI = {
    "Metro":     0,
    "Tren":      0,
    "Tramvay":   1,
    "Metrobüs":  2,
    "Vapur":     2,
    "Otobüs":    4,
    "Füniküler": 1,
    "Teleferik": 3,
    "Dolmuş":    8,
    "Yürüme":   15,  # Yürüme son çare olsun
}

# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _tip_ceza(hat_tipi: str) -> float:
    return TIP_CEZASI.get(hat_tipi, 2.0)


def stop_meta(stop_id: str) -> dict:
    _load()
    return _stop_meta.get(stop_id, {"name": stop_id, "lat": None, "lon": None})


def tum_duraklar() -> list[dict]:
    """Frontend autocomplete için tüm durak listesi."""
    global _stop_meta
    _load()
    result = []
    for sid, meta in _stop_meta.items():
        if sid in _YANLIS_KOORDINATLI_DURAKLAR:
            continue
        if meta.get("lat") and meta.get("lon"):
            result.append({
                "stop_id":   sid,
                "stop_name": meta["name"],
                "lat":       meta["lat"],
                "lon":       meta["lon"],
            })
    return sorted(result, key=lambda x: x["stop_name"])


def durak_id_set() -> set[str]:
    """İETT stop_id kümesini döndürür."""
    _load()
    return set(_stop_meta.keys())


def durak_meta_list() -> list[dict]:
    """İETT durak meta listesini (ilçe dahil) döndürür."""
    _load()
    result = []
    for sid, meta in _stop_meta.items():
        if sid in _YANLIS_KOORDINATLI_DURAKLAR:
            continue
        result.append({
            "stop_id": sid,
            "stop_name": meta.get("name", ""),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
            "ilce": meta.get("ilce"),
        })
    return result


def durak_turleri(stop_id: str) -> list[str]:
    """İETT stop_id için hat türlerini döndürür (Yürüme hariç)."""
    _load()
    turler = set()
    for e in _graph.get(stop_id, []):
        hat_tipi = e[3] if len(e) > 3 else None
        if not hat_tipi or hat_tipi == "Yürüme":
            continue
        turler.add(hat_tipi)
    return sorted(turler)


# ── Dijkstra çekirdeği ───────────────────────────────────────────────────────

def dijkstra(
    baslangic_ids: list[str],
    hedef_ids: list[str],
    strateji: str = "hizli",
) -> dict[str, Any] | None:
    """
    Multi-source Dijkstra.

    Graph edge formatı: (next_stop_id, sure, hat_adi, hat_tipi, renk)

    State: (stop_id, hat_adi) — aktarma tespiti için
    """
    _load()

    hedef_set = set(hedef_ids)
    akt_ceza  = AKTARMA_CEZASI.get(strateji, 5)

    # A* için hedef koordinatını bul
    _hedef_koord = None
    for _hid in hedef_ids:
        _hm = _stop_meta.get(_hid, {})
        if _hm.get("lat") and _hm.get("lon"):
            _hedef_koord = (_hm["lat"], _hm["lon"])
            break

    # (etkin_maliyet, sure, aktarma_sayisi, sayac,
    #  stop_id, hat_adi, yol, hat_dizisi, aktarma_noktalari)
    heap = []
    sayac = 0
    for sid in baslangic_ids:
        if sid in _graph or sid in hedef_set:
            heapq.heappush(heap, (0.0, 0, 0, sayac, sid, None, [sid], [], [], []))
            sayac += 1

    en_iyi: dict[tuple, float] = {}

    while heap:
        (etkin, sure, aktarma, _, sid, hat,
         yol, hat_dizisi, akt_nok, renk_dizisi) = heapq.heappop(heap)

        if sid in hedef_set:
            return _format_sonuc(yol, hat_dizisi, akt_nok, sure, aktarma, etkin, strateji, renk_dizisi)

        durum = (sid, hat)
        if en_iyi.get(durum, float("inf")) <= etkin:
            continue
        en_iyi[durum] = etkin

        for (sonraki, edge_sure, hat_adi, hat_tipi, renk) in _graph.get(sid, []):
            yurume_kenari = hat_tipi == "Yürüme" or hat_adi == "YURUME"

            # Yürüme: aktarma sayılmaz ama yüksek sabit ceza alır
            akt_oluyor = hat is not None and hat != hat_adi and not yurume_kenari

            # Yürüme kenarı için strateji bazlı ekstra ceza
            if yurume_kenari:
                # Parabolik yürüme cezası: kısa OK, uzun pahalı
                if strateji == "yurume":
                    yurume_ceza = 0
                elif strateji == "aktarma":
                    yurume_ceza = int(30 + ((max(0, edge_sure - 2)) ** 2.2)) if edge_sure > 2 else 30
                else:  # hizli
                    yurume_ceza = int(5 + ((max(0, edge_sure - 2)) ** 2.2)) if edge_sure > 2 else 5
            else:
                yurume_ceza = 0

            ek = (akt_ceza if akt_oluyor else 0) + _tip_ceza(hat_tipi) + yurume_ceza
            _h = _heuristic(sonraki, _hedef_koord)
            yeni_etkin  = etkin + edge_sure + ek + _h
            yeni_sure   = sure + edge_sure
            yeni_aktarma = aktarma + (1 if akt_oluyor else 0)

            son_durum = (sonraki, hat_adi)
            if en_iyi.get(son_durum, float("inf")) <= yeni_etkin:
                continue

            sayac += 1
            heapq.heappush(heap, (
                yeni_etkin, yeni_sure, yeni_aktarma, sayac,
                sonraki, hat_adi,
                yol + [sonraki],
                hat_dizisi + [hat_adi],
                akt_nok + ([sid] if akt_oluyor else []),
                renk_dizisi + [renk],
            ))

    return None


def _format_sonuc(yol, hat_dizisi, akt_nok, sure, aktarma, etkin, strateji, hat_renk_dizisi=None) -> dict:
    """Ham Dijkstra sonucunu frontend uyumlu formata çevir."""
    _load()

    yol_isimli = [_tr_title(_stop_meta.get(sid, {}).get("name", sid)) for sid in yol]
    akt_nok_isimli = [_tr_title(_stop_meta.get(sid, {}).get("name", sid)) for sid in akt_nok]

    # Koordinatlar (harita çizimi için)
    koordinatlar = []
    for sid in yol:
        m = _stop_meta.get(sid, {})
        lat, lon = m.get("lat"), m.get("lon")
        if lat and lon:
            koordinatlar.append([lat, lon])

    # Adım adım tarif
    adimlar = _adim_tarif_olustur(yol, yol_isimli, hat_dizisi)

    STRATEJI_BASLIK = {
        "hizli":   "En Hızlı",
        "aktarma": "En Az Aktarma",
        "yurume":  "En Az Yürüme",
    }

    return {
        "yol":               yol_isimli,
        "yol_stop_ids":      yol,
        "sure":              sure,
        "aktarma":           aktarma,
        "etkin_maliyet":     round(etkin, 1),
        "hatlar":            hat_dizisi,
        "aktarma_noktalari": akt_nok_isimli,
        "koordinatlar":      koordinatlar,
        "adimlar":           adimlar,
        "strateji":          STRATEJI_BASLIK.get(strateji, strateji),
        "bekleme_dahil":     False,
        "hat_renkleri":      hat_renk_dizisi or [],
    }


def _adim_tarif_olustur(yol_ids, yol_isimli, hat_dizisi) -> list[dict]:
    """
    Google Maps tarzı adım adım tarif.

    Çıktı:
    [
      {"tip": "bin",     "durak": "Kadıköy", "hat": "E-10", "hat_tipi": "Otobüs"},
      {"tip": "devam",   "durak_sayisi": 5,  "hat": "E-10"},
      {"tip": "aktarma", "durak": "Taksim",  "hat_den": "E-10", "hat_e": "M2"},
      {"tip": "in",      "durak": "Şişli"},
    ]
    """
    if not yol_ids or not hat_dizisi:
        return []

    adimlar = []
    n = len(hat_dizisi)

    # İlk biniş — ilk hat YURUME ise ilk gerçek hattı bul
    if yol_isimli:
        ilk_hat = ""
        for h in hat_dizisi:
            if h and h != "YURUME":
                ilk_hat = h
                break
        adimlar.append({
            "tip":      "bin",
            "durak":    yol_isimli[0],
            "stop_id":  yol_ids[0],
            "hat":      ilk_hat or (hat_dizisi[0] if hat_dizisi else ""),
        })

    # Orta segmentler
    segment_baslangic = 0
    for i in range(1, n):
        if hat_dizisi[i] != hat_dizisi[i - 1]:
            # Aktarma noktası
            durak_idx = i  # aktarma yapılan durak yol'da i. eleman
            durak_adi = yol_isimli[durak_idx] if durak_idx < len(yol_isimli) else "?"

            # Bu segmentte kaç durak geçildi
            seg_durak = durak_idx - segment_baslangic
            if seg_durak > 1:
                adimlar.append({
                    "tip":          "devam",
                    "hat":          hat_dizisi[i - 1],
                    "durak_sayisi": seg_durak,
                })

            adimlar.append({
                "tip":      "aktarma",
                "durak":    durak_adi,
                "stop_id":  yol_ids[durak_idx] if durak_idx < len(yol_ids) else "",
                "hat_den":  hat_dizisi[i - 1],
                "hat_e":    hat_dizisi[i],
            })
            segment_baslangic = durak_idx

    # Son segment durak sayısı
    son_seg = n - segment_baslangic
    if son_seg > 1:
        adimlar.append({
            "tip":          "devam",
            "hat":          hat_dizisi[-1],
            "durak_sayisi": son_seg,
        })

    # Son durakta in
    if len(yol_isimli) > 1:
        adimlar.append({
            "tip":     "in",
            "durak":   yol_isimli[-1],
            "stop_id": yol_ids[-1] if yol_ids else "",
        })

    # Post-processing: Son adım YURUME ise ve önceki durakla aynı isimse temizle
    # Örn: "X durağında in → X'e yürü" → sadece "X'te in" kalır
    while len(adimlar) >= 2:
        son = adimlar[-1]
        onceki = adimlar[-2]
        # Son adım yürüme aktarması mı?
        if (onceki.get("tip") == "aktarma" and
            (onceki.get("hat_e") == "YURUME" or onceki.get("hat_den") == "YURUME")):
            # Yürüme adımını ve öncesini temizle, son "in" adımını güncelle
            adimlar.pop(-2)  # aktarma adımını sil
            break
        # Son devam adımı YURUME mi?
        if son.get("tip") == "devam" and son.get("hat") == "YURUME":
            adimlar.pop()
            break
        break

    return adimlar


# ── Durak arama (autocomplete) ───────────────────────────────────────────────

def durak_ara(sorgu: str, max_sonuc: int = 10) -> list[dict]:
    """
    stop_name içinde case-insensitive arama.
    Türkçe karakter normalize edilir.
    """
    _load()
    global _stop_meta

    def _norm(s):
        return (tr_lower(s)
                .replace("ı", "i").replace("ğ", "g").replace("ş", "s")
                .replace("ç", "c").replace("ö", "o").replace("ü", "u"))

    q = _norm(sorgu.strip())
    if not q:
        return []

    results = []
    seen_names = set()
    seen_coords = set()
    for sid, meta in _stop_meta.items():
        name = meta.get("name", "")
        if not name:
            continue
        if _norm(name).startswith(q):
            lat = meta.get("lat")
            lon = meta.get("lon")
            coord_key = (round(lat, 4), round(lon, 4)) if lat and lon else None
            # Aynı koordinatta birden fazla durak varsa sadece birini al
            # Ama farklı koordinattaki aynı isimli durakları hepsini al
            if coord_key and coord_key in seen_coords:
                continue
            if coord_key:
                seen_coords.add(coord_key)
            seen_names.add(name)
            results.append({
                "stop_id":   sid,
                "stop_name": name,
                "lat":       lat,
                "lon":       lon,
            })
        if len(results) >= max_sonuc * 3:
            break

    # Önce prefix match, sonra alfabetik
    results.sort(key=lambda x: (not _norm(x["stop_name"]).startswith(q), x["stop_name"]))
    return results[:max_sonuc]


# ── Stop isimden ID'ye çözümleme ─────────────────────────────────────────────

def _mesafe(lat1, lon1, lat2, lon2) -> float:
    """İki koordinat arası yaklaşık mesafe (derece cinsinden)."""
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5


def isim_to_ids_koordinatli(stop_name: str, lat: float, lon: float, max_sonuc: int = 1) -> list[str]:
    """
    stop_name + koordinat → en yakın stop_id listesi
    Aynı isimde birden fazla durak varsa koordinata en yakını seç.

    Önce tam eşleşme (case-insensitive, Türkçe karakter korunur) dener.
    Bulamazsa normalize fallback kullanır.
    Bu sayede BEYLIKDÜZÜ sorgusu yanlış koordinattaki BEYLİKDÜZÜ'ye gitmiyor.
    """
    global _stop_meta
    _load()

    q_strip = stop_name.strip()
    q_base = stop_name.split("(")[0].strip() if "(" in stop_name else q_strip

    def _norm(s):
        return (tr_lower(s)
                .replace("ı", "i").replace("ğ", "g").replace("ş", "s")
                .replace("ç", "c").replace("ö", "o").replace("ü", "u"))

    adaylar = []

    # ── Adım 1: Tam case-insensitive eşleşme (Türkçe karakter korunur) ────────
    for sid, meta in _stop_meta.items():
        name = meta.get("name", "")
        if tr_lower(name) == tr_lower(q_strip) or tr_lower(name) == tr_lower(q_base):
            m_lat = meta.get("lat") or 0
            m_lon = meta.get("lon") or 0
            if m_lat and m_lon:
                mesafe = _mesafe(lat, lon, m_lat, m_lon)
                adaylar.append((mesafe, sid))

    # ── Adım 2: Fallback — tam normalize eşleşme ─────────────────────────────
    if not adaylar:
        q_norm = _norm(q_strip)
        q_base_norm = _norm(q_base)
        for sid, meta in _stop_meta.items():
            name_norm = _norm(meta.get("name", ""))
            if name_norm == q_norm or name_norm == q_base_norm:
                m_lat = meta.get("lat") or 0
                m_lon = meta.get("lon") or 0
                if m_lat and m_lon:
                    mesafe = _mesafe(lat, lon, m_lat, m_lon)
                    adaylar.append((mesafe, sid))

    adaylar.sort(key=lambda x: x[0])
    return [sid for _, sid in adaylar[:max_sonuc]] if adaylar else []


def iett_stop_exists(stop_id: str) -> bool:
    """Stop_id İETT graph'ında var mı?"""
    _load()
    return stop_id in _graph

def isim_to_ids(stop_name: str) -> list[str]:
    """
    stop_name → [stop_id, ...] (aynı isimde birden fazla durak olabilir)
    Parantezli isimler desteklenir: "BÜLBÜL SOKAK (Pendik)" → "BÜLBÜL SOKAK"

    Öncelik sırası:
    1. Tam string eşleşmesi (büyük/küçük harf dahil, normalize etmeden)
       → Bu sayede BEYLIKDÜZÜ ile BEYLİKDÜZÜ birbirini karıştırmaz
    2. Büyük/küçük harf fark etmez ama Türkçe karakter korunarak eşleşme
    3. Son çare: tam Türkçe normalize ile eşleşme
    """
    global _stop_meta
    _load()

    q_strip = stop_name.strip()
    q_base = stop_name.split("(")[0].strip() if "(" in stop_name else q_strip

    # ── Adım 1: Tam eşleşme (case-insensitive ama Türkçe karakter korunur) ────
    # Örn: "BEYLIKDÜZÜ" → sadece tam "BEYLIKDÜZÜ" eşleşir, "BEYLİKDÜZÜ" eşleşmez
    ids_exact = []
    for sid, meta in _stop_meta.items():
        name = meta.get("name", "")
        if tr_lower(name) == tr_lower(q_strip) or tr_lower(name) == tr_lower(q_base):
            ids_exact.append(sid)

    if ids_exact:
        # Tam eşleşmede de birden fazla olabilir (ör: SANCAKTEPE) — en iyisini seç
        return en_iyi_id_sec(ids_exact)

    # ── Adım 2: Türkçe normalize ile eşleşme (fallback) ─────────────────────
    # Kullanıcı farklı karakter seti girdiyse (i/İ/ı karışıklığı vb.) bu yakalar
    def _norm(s):
        return (tr_lower(s)
                .replace("ı", "i").replace("ğ", "g").replace("ş", "s")
                .replace("ç", "c").replace("ö", "o").replace("ü", "u"))

    q = _norm(q_strip)
    q_base_norm = _norm(q_base)

    # Normalize eşleşme — ama tam eşleşmeyi tercih et
    # Aynı normalize forma sahip farklı Türkçe yazımları varsa
    # (ör: BEYLIKDÜZÜ vs BEYLİKDÜZÜ) sadece birini seçmek yerine hepsini döndür
    # — çünkü bunlar gerçekten farklı duraklar olabilir (farklı koordinatlar)
    ids_norm = []
    seen_names_norm = set()
    for sid, meta in _stop_meta.items():
        name = meta.get("name", "")
        name_norm = _norm(name)
        if name_norm == q or name_norm == q_base_norm:
            ids_norm.append(sid)
            seen_names_norm.add(name)

    # Birden fazla ID varsa en mantıklısını seç (Sancaktepe gibi durumlar için)
    return en_iyi_id_sec(ids_norm)
