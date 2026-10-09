# -*- coding: utf-8 -*-
"""
app.py — İBB Akıllı Şehir Navigasyonu Flask API.
"""
import csv
import json
import os
import sys
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Türkçe İ/i uyumlu string helper'ları ──────────────────────────────────────
def tr_lower(s: str) -> str:
    if not s:
        return ""
    return s.replace("İ", "i").replace("I", "ı").lower().replace("̇", "")


_TR_UPPER_MAP = str.maketrans(
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ",
    "abcçdefgğhıijklmnoöprsştuüvyz",
)


def tr_title(s: str) -> str:
    if not s:
        return ""
    def _cap_word(w: str) -> str:
        if not w:
            return w
        alpha_idx = next((i for i, c in enumerate(w) if c.isalpha()), -1)
        if alpha_idx == -1:
            return w
        prefix = w[:alpha_idx]
        rest = w[alpha_idx:]
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
        return prefix + yeni + rest[1:].translate(_TR_UPPER_MAP)
    parts = []
    for kelime in s.split():
        # Capitalize after hyphens too (e.g. "Beşiktaş-Üsküdar")
        sub_parts = kelime.split("-")
        parts.append("-".join(_cap_word(sub) for sub in sub_parts))
    return " ".join(parts)


import re as _re

def _temiz_durak_adi(name: str) -> str:
    """'X (X)' → 'X' — parantez içi ilçe adı, asıl adla aynıysa sil."""
    if not name:
        return name
    m = _re.match(r'^(.+?)\s*\((.+?)\)$', name)
    if m and tr_lower(m.group(1).strip()) == tr_lower(m.group(2).strip()):
        return m.group(1).strip()
    return name


_ILCE_CACHE: dict[tuple[float, float], str | None] = {}


def _ilce_cache_yukle() -> None:
    yol = os.path.join(os.path.dirname(__file__), "data", "ilce_cache.json")
    if not os.path.exists(yol):
        return
    try:
        with open(yol, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            lat_s, lon_s = k.split(",")
            _ILCE_CACHE[(float(lat_s), float(lon_s))] = v
    except Exception:
        pass


def _ilce_cache_bul(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    return _ILCE_CACHE.get((round(float(lat), 2), round(float(lon), 2)))


def _base_durak_adi(name: str) -> str:
    return name.split("(")[0].strip() if name else ""


def _durak_ilce_cikar(name: str) -> str | None:
    if not name:
        return None
    m = _re.match(r'^(.+?)\s*\((.+?)\)$', name)
    return m.group(2).strip() if m else None


def _norm_durak_adi(name: str) -> str:
    s = tr_lower(_base_durak_adi(name))
    return (s.replace("ı", "i").replace("ğ", "g").replace("ş", "s")
              .replace("ç", "c").replace("ö", "o").replace("ü", "u"))


from models.graf import Graf
from data.gtfs_yukleyici import (
    canonical_name, canonical_map_olustur,
    get_clean_stop_list, durak_ara,
    otobus_hatlari_yukle, _haversine,
    durak_adini_temizle,
    disambiguate_stop_names,
)
from services.bfs import (
    en_az_aktarmali_rota,
    en_az_yurume_rota,
    en_kisa_sureli_rota,
    k_en_iyi_rota,
)

# ── Hat ismi sözlüğü — teknik kodları okunabilir isimlere çevir ─────────────────
HAT_ISIMLERI = {
    # ── Füniküler ────────────────────────────────────────────────────
    "F1":                "Taksim-Kabataş Füniküler",
    "F2":                "Kabataş-Kadıköy Füniküler",
    "F3":                "Füniküler",
    # ── Teleferik ───────────────────────────────────────────────────
    "TF1":               "Teleferik",
    "TF2":               "Teleferik",
    # ── Marmaray ────────────────────────────────────────────────────
    "Marmaray":          "Marmaray",
    "Marmaray1":         "Marmaray",
    "Marmaray2":         "Marmaray",
    # ── Vapur — Eminönü ekseni ──────────────────────────────────────
    "EMN-KDK":           "Eminönü-Kadıköy Vapuru",
    "EMN_KDK":           "Eminönü-Kadıköy Vapuru",
    "EMN_KDK2":          "Eminönü-Kadıköy Vapuru",
    "EMN-KDK-ADA":       "Eminönü-Kadıköy-Adalar Vapuru",
    "EMN-ADA":           "Eminönü-Adalar Vapuru",
    "EMN-ADA-BOST":      "Eminönü-Adalar-Bostancı Vapuru",
    "EMN-ÜSK":           "Eminönü-Üsküdar Vapuru",
    "EMN_USK":           "Eminönü-Üsküdar Vapuru",
    "EMN-BBK":           "Eminönü-Büyükada Vapuru",
    "SRY-EMN":           "Sarayburnu-Eminönü Vapuru",
    "RKVK-EMN":          "Rumelikavağı-Eminönü Vapuru",
    # ── Vapur — Kadıköy ekseni ──────────────────────────────────────
    "KDK-EMN":           "Kadıköy-Eminönü Vapuru",
    "KDK-KRK-EMN":       "Kadıköy-Karaköy-Eminönü Vapuru",
    "KRK-EMN-KDK":       "Karaköy-Eminönü-Kadıköy Vapuru",
    "KDK-BŞK":           "Kadıköy-Beşiktaş Vapuru",
    "BSK_KDK":           "Beşiktaş-Kadıköy Vapuru",
    "KDK-BŞK-İST-SRY":   "Kadıköy-Beşiktaş-İstinye-Sarıyer Vapuru",
    "KDK-HLC":           "Kadıköy-Haliç Vapuru",
    "KDK2_K.KÖY_EMN":    "Kadıköy-Eminönü Vapuru",
    "KDK_EMN_K.KOY":     "Kadıköy-Eminönü Vapuru",
    "K.KOY_KDK":         "Kabataş-Kadıköy Vapuru",
    "K.KÖY_KDK2":        "Kabataş-Kadıköy Vapuru",
    "B.KOY_KDK":         "Bebek-Kadıköy Vapuru",
    "K.KOY_USK":         "Kabataş-Üsküdar Vapuru",
    "K.KOY_B.ADA":       "Kabataş-Büyükada Vapuru",
    "K.ADA_K.KOY_EMN":   "Adalar-Kabataş-Eminönü Vapuru",
    # ── Vapur — Kabataş ekseni ──────────────────────────────────────
    "KBTŞ-EMN-KDK-ADA":  "Kabataş-Eminönü-Kadıköy-Adalar Vapuru",
    "KBT-EMN":           "Kabataş-Eminönü Vapuru",
    "KBTŞ-EMN":          "Kabataş-Eminönü Vapuru",
    "KBT-ADA":           "Kabataş-Adalar Vapuru",
    "ÜSK-KBTŞ":          "Üsküdar-Kabataş Vapuru",
    "KCS-BŞK":           "Küçüksu-Beşiktaş Vapuru",
    "ASYN-KCS":          "Aşiyan-Küçüksu Vapuru",
    "BYK-ÜSK":           "Büyükdere-Üsküdar Vapuru",
    "AKV-ÜSK":           "Akıntıburnu-Üsküdar Vapuru",
    # ── Vapur — Üsküdar ekseni ──────────────────────────────────────
    "ÜSK-EMN":           "Üsküdar-Eminönü Vapuru",
    "ÜSK-BŞK":           "Üsküdar-Beşiktaş Vapuru",
    "ÜSK - ORT":         "Üsküdar-Ortaköy Vapuru",
    "ÜSK-EYP":           "Üsküdar-Eyüp Vapuru",
    "AKV-ÜSK":           "Akıntıburnu-Üsküdar Vapuru",
    # ── Vapur — Bostancı ekseni ─────────────────────────────────────
    "BOS-ADA":           "Bostancı-Adalar Vapuru",
    "BOS-ADA_RING":      "Bostancı-Adalar Ring Vapuru",
    "BOS-KRK-KBTŞ":      "Bostancı-Karaköy-Kabataş Vapuru",
    "BOS-KRK":           "Bostancı-Karaköy Vapuru",
    "KRK-BOS":           "Karaköy-Bostancı Vapuru",
    "KBTŞ-KRK-BOS":      "Kabataş-Karaköy-Bostancı Vapuru",
    "BOSTANCI - BEŞİKTAŞ": "Bostancı-Beşiktaş Vapuru",
    "BOSTANCI-B.KÖY":    "Bostancı-Bebek Vapuru",
    # ── Vapur — Adalar ──────────────────────────────────────────────
    "ADA - BOS":         "Adalar-Bostancı Vapuru",
    "ADA-EMN":           "Adalar-Eminönü Vapuru",
    "B.CKMC_B.ADA":      "Büyükçekmece-Büyükada Vapuru",
    "B.KOY_B.ADA":       "Bebek-Büyükada Vapuru",
    "BŞK-ADA":           "Beşiktaş-Adalar Vapuru",
    "BŞK-ADA_2":         "Beşiktaş-Adalar Vapuru",
    "BŞK-BYKADA":        "Beşiktaş-Büyükada Vapuru",
    "BEŞİKTAŞ - HEYBELİADA": "Beşiktaş-Heybeliada Vapuru",
    "BEŞİKTAŞ-BURGAZADA":    "Beşiktaş-Burgazada Vapuru",
    "BYKADA-HYBADA":     "Büyükada-Heybeliada Vapuru",
    # ── Vapur — Boğaz hatları ───────────────────────────────────────
    "BĞZ1":              "Boğaz Hattı 1",
    "BĞZ2":              "Boğaz Hattı 2",
    "BĞZ-1":             "Boğaz Hattı 1",
    "BĞZ-2":             "Boğaz Hattı 2",
    "KISA BĞZ":          "Kısa Boğaz Hattı",
    "UZUN-BĞZ":          "Uzun Boğaz Hattı",
    "BSK-HLC":           "Beşiktaş-Haliç Vapuru",
    "SRY-AKV":           "Sarıyer-Akıntıburnu Vapuru",
    "SRY-RMK-AKV":       "Sarıyer-Rumeli Kavağı-Akıntıburnu Vapuru",
    "LALE FST":          "Lale Festivali Vapuru",
    # ── Vapur — Anadolu/Avrupa karşı ────────────────────────────────
    "USK_K.KOY_EMN":     "Üsküdar-Kabataş-Eminönü Vapuru",
    "SİRKECİ - HAREM":   "Sirkeci-Harem Vapuru",
    "İST - ÇBK":         "İstinye-Çubuklu Vapuru",
    "KÇS-İST":           "Küçüksu-İstinye Vapuru",
    "KRK-KDK":           "Karaköy-Kadıköy Vapuru",
    "EMGN-ARNK":         "Eminönü-Arnavutköy Vapuru",
    "EMGN-BBK":          "Eminönü-Bebek Vapuru",
    "EMGN-ÇNGK":         "Eminönü-Çengelköy Vapuru",
    "EMGN-İST-ÇNGK":     "Eminönü-İstinye-Çengelköy Vapuru",
    "ÇNGK-EMGN":         "Çengelköy-Eminönü Vapuru",
    "ÇNGK-iST":          "Çengelköy-İstinye Vapuru",
    "ERGVN":             "Ergene Vapuru",
    "ARNK - İST":        "Arnavutköy-İstinye Vapuru",
    "BŞK-BYKADA":        "Beşiktaş-Büyükada Vapuru",
    # ── Yürüme ──────────────────────────────────────────────────────
    "YURUME":            "Yürüme",
    "yurume":            "Yürüme",
}

# ── İETT Otobüs Router (YENİ) ─────────────────────────────────────────────────
from services.router import (
    dijkstra as iett_dijkstra,
    durak_ara as iett_durak_ara,
    durak_id_set as iett_durak_id_set,
    durak_meta_list as iett_durak_meta_list,
    durak_turleri as iett_durak_turleri,
    isim_to_ids as iett_isim_to_ids,
    isim_to_ids_koordinatli as iett_isim_to_ids_koord,
    iett_stop_exists,
)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)
app.config["JSON_AS_ASCII"] = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["JSON_SORT_KEYS"] = False

GRAF: Graf
GRAF_DICT: dict
ISTASYON_KOORD: dict[str, tuple[float, float]] = {}
STOP_ID_TO_NAME: dict[str, str] = {}
STOP_NAME_TO_IDS: dict[str, list[str]] = {}
HAT_STOP_CACHE: dict[str, list[str]] = {}
DURAK_KATALOG: list[dict] = []
DURAK_KATALOG_INDEX: dict[str, list[dict]] = {}
DURAK_SECIM_INDEX: dict[str, list[dict]] = {}
DURAK_ADLARI: list[str] = []
DURAK_ADLARI_RAYLI: list[str] = []


def _stop_koordinatlari_yukle() -> dict[str, tuple[float, float]]:
    yol = os.path.join(os.path.dirname(__file__), "data", "gtfs", "stops.csv")
    eslesme: dict[str, tuple[float, float]] = {}
    if not os.path.exists(yol):
        print(f"  uyarı: {yol} bulunamadı, koordinatsız çalışılacak")
        return eslesme
    try:
        with open(yol, encoding="utf-8-sig", newline="") as f:
            ornek = f.read(2048)
            f.seek(0)
            try:
                lehce = csv.Sniffer().sniff(ornek, delimiters=",;\t")
            except csv.Error:
                lehce = csv.excel
            okuyucu = csv.DictReader(f, dialect=lehce)
            if okuyucu.fieldnames:
                okuyucu.fieldnames = [c.lstrip("\ufeff") for c in okuyucu.fieldnames]
            for satir in okuyucu:
                ad = (satir.get("stop_name") or "").strip()
                lat_s = (satir.get("stop_lat") or "").strip()
                lon_s = (satir.get("stop_lon") or "").strip()
                if not ad or not lat_s or not lon_s:
                    continue
                try:
                    eslesme[ad] = (float(lat_s), float(lon_s))
                except ValueError:
                    continue
    except Exception as hata:
        print(f"  uyarı: stops.csv okunamadı: {hata}")
    return eslesme


def _graf_yukle() -> tuple[Graf, dict]:
    json_yolu = os.path.join(os.path.dirname(__file__), "data", "istanbul_graf.json")
    _cache_gecerli = False

    if os.path.exists(json_yolu):
        try:
            with open(json_yolu, encoding="utf-8") as f:
                graf_dict = json.load(f)
            if graf_dict.get("istasyonlar") and graf_dict["istasyonlar"][0].isdigit():
                if len(graf_dict["istasyonlar"]) < 1000:
                    print(f"JSON cache {len(graf_dict['istasyonlar'])} istasyon (<1000) → yeniden üretilecek.")
                    os.remove(json_yolu)
                else:
                    _cache_gecerli = True
            else:
                print("JSON cache stop_name bazlı → yeniden üretilecek.")
                os.remove(json_yolu)
        except Exception:
            pass

    if _cache_gecerli:
        print(f"Graf cache'ten yükleniyor → {json_yolu}")
        graf = Graf()
        for sid in graf_dict["istasyonlar"]:
            graf.istasyon_ekle(sid)
        for h in graf_dict["hatlar"]:
            try:
                graf.hat_ekle(
                    h["baslangic"], h["bitis"],
                    h["hat_tipi"], h["hat_adi"], h["sure"], h["renk"],
                )
            except ValueError:
                pass

        _stops_csv = os.path.join(os.path.dirname(__file__), "data", "gtfs", "stops.csv")
        if os.path.exists(_stops_csv):
            import csv as _csv
            with open(_stops_csv, encoding="utf-8-sig", newline="") as _f:
                for _row in _csv.DictReader(_f):
                    _sid = (_row.get("stop_id") or "").strip()
                    _sn = (_row.get("stop_name") or "").strip()
                    if _sid in graf.istasyonlar and _sn:
                        _temiz = durak_adini_temizle(_sn, _sid)
                        try:
                            _lat = float((_row.get("stop_lat") or 0))
                            _lon = float((_row.get("stop_lon") or 0))
                        except (ValueError, TypeError):
                            _lat, _lon = 0.0, 0.0
                        graf._node_meta[_sid] = {
                            "stop_id": _sid, "stop_name": _temiz,
                            "stop_lat": _lat, "stop_lon": _lon,
                        }

        _otobus_csv = os.path.join(os.path.dirname(__file__), "data", "gtfs", "iett_stops.csv")
        if os.path.exists(_otobus_csv):
            import csv as _csv2
            with open(_otobus_csv, encoding="utf-8-sig", newline="") as _f2:
                for _row in _csv2.DictReader(_f2):
                    _sid = (_row.get("stop_id") or "").strip()
                    _sn = (_row.get("stop_name") or "").strip()
                    if _sid in graf.istasyonlar and _sid not in graf._node_meta:
                        try:
                            _lat = float((_row.get("stop_lat") or 0))
                            _lon = float((_row.get("stop_lon") or 0))
                        except (ValueError, TypeError):
                            _lat, _lon = 0.0, 0.0
                        graf._node_meta[_sid] = {
                            "stop_id": _sid, "stop_name": _sn,
                            "stop_lat": _lat, "stop_lon": _lon,
                        }
    else:
        print("JSON cache yok -> GTFS'ten üretiliyor...")
        from data.gtfs_yukleyici import istanbul_grafi_olustur
        try:
            graf = istanbul_grafi_olustur(
                gtfs_klasoru=os.path.join("data", "gtfs"),
                sadece_rayli=True,
                verbose=False,
            )
        except (FileNotFoundError, UnicodeDecodeError, ValueError, KeyError) as e:
            print(f"GTFS yüklenemedi ({type(e).__name__}) -> mini örnek graf yükleniyor.")
            from data.ornek_sehir import mini_istanbul_olustur
            graf = mini_istanbul_olustur()

    otobus_csv = os.path.join(os.path.dirname(__file__), "data", "gtfs", "iett_stops.csv")
    if os.path.exists(otobus_csv):
        eklenen = otobus_hatlari_yukle(otobus_csv, graf, hat_stop_cache=HAT_STOP_CACHE)
        print(f"  Otobüs entegrasyonu: {eklenen} kenar eklendi.")
    else:
        print(f"  HATA: Otobüs CSV bulunamadı: {otobus_csv}")

    from data.walking_edge_yukleyici import walking_edges_ekle
    walk_count = walking_edges_ekle(graf, max_metre=100.0)
    print(f"  {walk_count} yürüme kenarı eklendi.")

    graf_dict = graf.to_dict()
    if not _cache_gecerli:
        try:
            with open(json_yolu, "w", encoding="utf-8") as _jf:
                json.dump(graf_dict, _jf, ensure_ascii=False)
            print(f"  Cache yazıldı -> {json_yolu}")
        except OSError as _e:
            print(f"  Cache yazılamadı: {_e}")

    print(f"Graf yükleniyor... {graf.istasyon_sayisi()} istasyon, {graf.hat_sayisi()} kenar hazır.")
    return graf, graf_dict


GRAF, GRAF_DICT = _graf_yukle()

for _sid in GRAF.istasyonlar:
    _meta = GRAF.node_meta(_sid)
    if _meta:
        _sname = _meta.get("stop_name") or _meta.get("name") or ""
        if _sname:
            STOP_ID_TO_NAME[_sid] = _sname
            STOP_NAME_TO_IDS.setdefault(_sname, []).append(_sid)

disambiguate_stop_names(GRAF, STOP_NAME_TO_IDS, STOP_ID_TO_NAME)

# Büyük harfli + Title Case çakışmalarını disambiguate et
# Örn: 'BAHÇELİEVLER' (otobüs/Pendik) vs 'Bahçelievler' (raylı/Bahçelievler)
from data.gtfs_yukleyici import _ilce_bul, turkce_normalize

def _turkce_title(s: str) -> str:
    """Türkçe karakterleri doğru şekilde Title Case'e çevirir."""
    tr_map = str.maketrans("ABCDEFGHIİJKLMNOÖPRSŞTUÜVYZ",
                           "abcdefghıijklmnoöprsştuüvyz")
    sonuc = []
    for i, ch in enumerate(s):
        if i == 0 or s[i-1] == " ":
            # Büyük harfe çevir
            if ch == "i": sonuc.append("İ")
            elif ch == "ı": sonuc.append("I")
            else: sonuc.append(ch.upper())
        else:
            sonuc.append(ch.translate(tr_map))
    return "".join(sonuc)

_tum_isimler = set(STOP_ID_TO_NAME.values())
# Normalize edilmiş isim → orijinal isim eşleşmesi
_norm_to_orig: dict[str, str] = {}
for _isim in _tum_isimler:
    _norm_to_orig[turkce_normalize(_isim)] = _isim

for _sid, _name in list(STOP_ID_TO_NAME.items()):
    # Sadece TAM büyük harfli olanları işle
    if not _name or _name != _name.upper() or not _name.replace(" ", "").isalpha():
        if not (_name and all(c.isupper() or not c.isalpha() for c in _name)):
            continue
    # Normalize karşılığı olan başka bir isim var mı?
    # Büyük→küçük harf karşılaştırması (Türkçe İ→i dahil)
    _name_lower = tr_lower(_name)
    _eslesme_orig = None
    for _diger in _tum_isimler:
        if _diger != _name and tr_lower(_diger) == _name_lower:
            _eslesme_orig = _diger
            break
    if not _eslesme_orig:
        continue
    # Koordinat al
    _meta = GRAF.node_meta(_sid)
    if not _meta:
        continue
    _lat = _meta.get("lat") or _meta.get("stop_lat") or 0.0
    _lon = _meta.get("lon") or _meta.get("stop_lon") or 0.0
    if _lat == 0.0:
        continue
    # İlçe bul
    _ilce = _ilce_bul(_lat, _lon)
    if not _ilce:
        continue
    _yeni = f"{_eslesme_orig} ({_ilce})"
    if _yeni == _name:
        continue
    STOP_ID_TO_NAME[_sid] = _yeni
    STOP_NAME_TO_IDS.setdefault(_yeni, [])
    if _sid not in STOP_NAME_TO_IDS[_yeni]:
        STOP_NAME_TO_IDS[_yeni].append(_sid)
    if _name in STOP_NAME_TO_IDS:
        STOP_NAME_TO_IDS[_name] = [s for s in STOP_NAME_TO_IDS[_name] if s != _sid]
        if not STOP_NAME_TO_IDS[_name]:
            del STOP_NAME_TO_IDS[_name]

# _CLEAN_STOP_LIST'i güncelle — yeni disambiguated isimleri ekle

_tum_stop_names: set[str] = set(STOP_ID_TO_NAME.values())
_tum_stop_names.update(STOP_ID_TO_NAME.values())  # büyük harfli disambiguate sonrası güncelle
CANONICAL_MAP: dict[str, list[str]] = canonical_map_olustur(_tum_stop_names)

for _dname in list(_tum_stop_names):
    if "(" in _dname and ")" in _dname:
        _canon = canonical_name(_dname)
        if _canon:
            CANONICAL_MAP.setdefault(_canon, [])
            if _dname not in CANONICAL_MAP[_canon]:
                CANONICAL_MAP[_canon].append(_dname)
        CANONICAL_MAP[_dname] = [_dname]
        STOP_NAME_TO_IDS.setdefault(_dname, STOP_NAME_TO_IDS.get(_dname, []))

_disambiguated_isimleri: set[str] = {n for n in _tum_stop_names if "(" in n and ")" in n}
_disambiguated_canonicals: set[str] = set()
for _dn in _disambiguated_isimleri:
    _cn = canonical_name(_dn)
    if _cn:
        _disambiguated_canonicals.add(_cn)

_CLEAN_STOP_LIST: list[str] = sorted(
    {cn for cn in get_clean_stop_list(_tum_stop_names) if cn not in _disambiguated_canonicals}
    | _disambiguated_isimleri
)
# Sorunlu durakları çıkar
# NOT: Hem büyük-İ hem büyük-I yazımını temizle (BEYLIKDÜZÜ / BEYLİKDÜZÜ karışıklığı)
_BEYLIKDUZU_VARYANTLARI = {"BEYLIKDÜZÜ", "BEYLİKDÜZÜ", "Beylikdüzü", "Beylikdüzü"}
_CLEAN_STOP_LIST = [ad for ad in _CLEAN_STOP_LIST if ad not in _BEYLIKDUZU_VARYANTLARI]

# İETT durakları datalist'e eklenmez — dinamik /api/durak-ara ile aranır (daha hızlı)

_CLEAN_STOP_LIST = sorted({_temiz_durak_adi(tr_title(ad)) for ad in _CLEAN_STOP_LIST})

ISTASYON_KOORD = _stop_koordinatlari_yukle()
print(f"  {len(CANONICAL_MAP)} canonical isim, {len(ISTASYON_KOORD)} koordinat yüklendi.")
print(f"  {len(STOP_ID_TO_NAME)} stop_id→name, {len(STOP_NAME_TO_IDS)} name→ids eşleşmesi.")
print(f"  {len(_disambiguated_isimleri)} disambiguated isim UI listesine eklendi.")

_ilce_cache_yukle()


def _rayli_turleri_hazirla(iett_ids: set[str]) -> dict[str, list[str]]:
    tur_map: dict[str, list[str]] = {}
    for sid in GRAF.istasyonlar:
        if sid in iett_ids:
            continue
        turler = set()
        for hat in GRAF.komsuluk.get(sid, []):
            hat_tipi = hat.hat_tipi
            if hat_tipi in ("Yürüme", "Aktarma"):
                continue
            if hat_tipi:
                turler.add(hat_tipi)
        if turler:
            tur_map[sid] = sorted(turler)
    return tur_map


def _durak_katalog_olustur() -> None:
    global DURAK_KATALOG, DURAK_KATALOG_INDEX, DURAK_SECIM_INDEX, DURAK_ADLARI, DURAK_ADLARI_RAYLI
    try:
        iett_ids = iett_durak_id_set()
        iett_meta = iett_durak_meta_list()
    except Exception:
        iett_ids = set()
        iett_meta = []
    rayli_tur_map = _rayli_turleri_hazirla(iett_ids)

    katalog: list[dict] = []

    def _vapur_ismini_sadellestir(ad, ilce, turler):
        if "Vapur" not in turler:
            return ad
        # Sonekleri ve bilinen kurum eklerini temizle
        temiz = ad
        for ek in [" Şh.", " Şh", " ŞH.", " ŞH", " İdo", " İDO", " Turyol", " Dentur", " İskelesi", " İskele"]:
            temiz = temiz.replace(ek, "")
        
        temiz = temiz.strip()
        
        # "A-B" formatını çöz (örn: Beşiktaş-Kadıköy)
        if "-" in temiz:
            parcalar = [p.strip() for p in temiz.split("-")]
            # Eğer parçalardan biri ilçeyle eşleşiyorsa onu al
            for p in parcalar:
                if tr_lower(p) == tr_lower(ilce):
                    return p
            # Eğer ilçe eşleşmezse bilinen büyük merkezleri kontrol et
            merkezler = ["Beşiktaş", "Kadıköy", "Üsküdar", "Eminönü", "Karaköy", "Kabataş", "Bostancı", "Adalar", "Bakırköy", "Yenikapı", "Sirkeci", "Harem"]
            for p in parcalar:
                if p in merkezler:
                    return p
            # Hiçbiri tutmazsa ilk parçayı al (genelde bulunulan yerdir)
            return parcalar[0]
        return temiz

    # Raylı duraklar (İETT stop_id'leri hariç)
    for sid, name in STOP_ID_TO_NAME.items():
        if sid in iett_ids:
            continue
        meta = GRAF.node_meta(sid) or {}
        lat = meta.get("stop_lat") or meta.get("lat")
        lon = meta.get("stop_lon") or meta.get("lon")
        
        ilce = _durak_ilce_cikar(name) or meta.get("category") or _ilce_cache_bul(lat, lon) or "İstanbul"
        turler = rayli_tur_map.get(sid, [])
        if not turler:
            turler = ["Raylı"]
        
        # Temel ismi al (parantez içi ilçe bilgisini atarak)
        base = _temiz_durak_adi(tr_title(_base_durak_adi(name)))
        
        # Vapur ise ismi sadeleştir (Beşiktaş-Kadıköy -> Beşiktaş)
        # Böylece "Beşiktaş" aramasına dahil olur ve "Vapur" seçeneği çıkar.
        base = _vapur_ismini_sadellestir(base, ilce, turler)
        
        katalog.append({
            "stop_id": sid,
            "ad": base,
            "ilce": ilce,
            "turler": turler,
            "sistem": "rayli",
            "lat": lat,
            "lon": lon,
        })

    # İETT duraklar
    for d in iett_meta:
        sid = d.get("stop_id")
        if not sid:
            continue
        name = tr_title(d.get("stop_name") or "")
        lat = d.get("lat")
        lon = d.get("lon")
        ilce = d.get("ilce") or _ilce_cache_bul(lat, lon) or "İstanbul"
        
        try:
            turler = iett_durak_turleri(sid)
        except Exception:
            turler = []
        if not turler:
            turler = ["Otobüs"]
        
        base = _temiz_durak_adi(tr_title(_base_durak_adi(name)))
        base = _vapur_ismini_sadellestir(base, ilce, turler)
        
        katalog.append({
            "stop_id": sid,
            "ad": base,
            "ilce": ilce,
            "turler": turler,
            "sistem": "iett",
            "lat": lat,
            "lon": lon,
        })

    secim_map: dict[tuple, dict] = {}
    katalog_index: dict[str, list[dict]] = {}
    for item in katalog:
        base_norm = _norm_durak_adi(item["ad"])
        katalog_index.setdefault(base_norm, []).append(item)
        for tur in item.get("turler") or []:
            key = (base_norm, item["ilce"], tur, item["sistem"])
            sec = secim_map.get(key)
            if not sec:
                sec = {
                    "ad": item["ad"],
                    "ilce": item["ilce"],
                    "tur": tur,
                    "sistem": item["sistem"],
                    "stop_ids": [],
                }
                secim_map[key] = sec
            sec["stop_ids"].append(item["stop_id"])

    secim_index: dict[str, list[dict]] = {}
    for (base_norm, _, _, _), sec in secim_map.items():
        sec["stop_ids"] = sorted(set(sec["stop_ids"]))
        sec["display"] = (
            f"{sec['ad']} ({sec['ilce']})" if sec.get("ilce") else sec["ad"]
        )
        secim_index.setdefault(base_norm, []).append(sec)

    for base_norm in secim_index:
        secim_index[base_norm].sort(key=lambda s: (s.get("ilce", ""), s.get("tur", ""), s.get("sistem", "")))

    DURAK_KATALOG = katalog
    DURAK_KATALOG_INDEX = katalog_index
    DURAK_SECIM_INDEX = secim_index
    DURAK_ADLARI = sorted({sec["ad"] for sec in secim_map.values()})
    DURAK_ADLARI_RAYLI = sorted({e["ad"] for e in katalog if e.get("sistem") == "rayli"})


_durak_katalog_olustur()


def _durak_ara_disambiguated(sorgu: str, max_sonuc: int = 10) -> list[str]:
    if not sorgu or not sorgu.strip():
        return []
    from data.gtfs_yukleyici import turkce_normalize
    sorgu_temiz = tr_lower(sorgu.strip())
    sorgu_ascii = turkce_normalize(sorgu)
    sonuclar: list[str] = []
    for ad in DURAK_ADLARI:
        ad_lower = tr_lower(ad)
        ad_ascii = turkce_normalize(ad)
        if ad_lower.startswith(sorgu_temiz) or ad_ascii.startswith(sorgu_ascii):
            sonuclar.append(ad)
            if len(sonuclar) >= max_sonuc:
                break
    return sonuclar


# ── Endpoints — Raylı Sistem ──────────────────────────────────────────────────

@app.route("/")
def anasayfa():
    return render_template("index.html")


@app.route("/api/istasyonlar", methods=["GET"])
def api_istasyonlar():
    try:
        return jsonify(DURAK_ADLARI_RAYLI)
    except Exception as hata:
        return jsonify({"hata": f"İstasyon listesi alınamadı: {hata}"}), 500


@app.route("/api/durak-ara", methods=["GET"])
def api_durak_ara():
    try:
        sorgu_raw = request.args.get("q", "")
        try:
            sorgu = sorgu_raw.encode("latin-1").decode("utf-8").strip()
        except (UnicodeDecodeError, UnicodeEncodeError):
            sorgu = sorgu_raw.strip()
        fmt   = request.args.get("fmt", "isim")  # "isim" veya "full"
        if not sorgu:
            return jsonify([])

        sorgu_base = _base_durak_adi(sorgu)

        if fmt == "full":
            base_norm = _norm_durak_adi(sorgu_base)
            entries = DURAK_KATALOG_INDEX.get(base_norm, [])
            sonuclar = []
            for e in entries:
                display = f"{e['ad']} ({e['ilce']})" if e.get("ilce") else e["ad"]
                sonuclar.append({
                    "stop_id": e.get("stop_id"),
                    "stop_name": display,
                    "lat": e.get("lat"),
                    "lon": e.get("lon"),
                    "ilce": e.get("ilce"),
                    "turler": e.get("turler", []),
                    "sistem": e.get("sistem"),
                })
            return jsonify(sonuclar[:10])

        sonuclar = _durak_ara_disambiguated(sorgu, max_sonuc=10)
        if not sonuclar and sorgu_base != sorgu:
            sonuclar = _durak_ara_disambiguated(sorgu_base, max_sonuc=10)
        return jsonify(sonuclar[:10])
    except Exception as hata:
        return jsonify({"hata": f"Arama hatası: {hata}"}), 500


@app.route("/api/durak-secim", methods=["GET"])
def api_durak_secim():
    try:
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"ad": "", "secenekler": [], "ilceler": []})
        base = _temiz_durak_adi(tr_title(_base_durak_adi(q)))
        secenekler = DURAK_SECIM_INDEX.get(_norm_durak_adi(base), [])
        ilceler = sorted({s.get("ilce", "Bilinmeyen") for s in secenekler})
        return jsonify({"ad": base, "secenekler": secenekler, "ilceler": ilceler})
    except Exception as hata:
        return jsonify({"hata": f"Seçim hatası: {hata}"}), 500


@app.route("/api/iett-duraklar", methods=["GET"])
def api_iett_duraklar():
    """İETT durakları koordinatlı — state.koordinatlar için."""
    try:
        from services.router import tum_duraklar, _YANLIS_KOORDINATLI_DURAKLAR
        duraklar = tum_duraklar()
        # İstanbul sınırları ve blacklist filtresi
        return jsonify([{
            "ad": tr_title(d["stop_name"]),
            "lat": d["lat"],
            "lon": d["lon"]
        } for d in duraklar
          if d.get("lat") and d.get("lon")
          and d["stop_id"] not in _YANLIS_KOORDINATLI_DURAKLAR
          and 40.7 <= d["lat"] <= 41.5
          and 27.9 <= d["lon"] <= 29.9])
    except Exception as e:
        return jsonify([])


@app.route("/api/graf", methods=["GET"])
def api_graf():
    try:
        istasyonlar_zenginlestirilmis = []
        for sid in GRAF_DICT["istasyonlar"]:
            meta = GRAF.node_meta(sid)
            if meta:
                # STOP_ID_TO_NAME'deki disambiguated UI ismi öncelikli
                sname = (STOP_ID_TO_NAME.get(sid)
                         or meta.get("stop_name")
                         or meta.get("name")
                         or sid)
                lat = meta.get("stop_lat") if meta.get("stop_lat") is not None else meta.get("lat")
                lon = meta.get("stop_lon") if meta.get("stop_lon") is not None else meta.get("lon")
            else:
                sname = STOP_ID_TO_NAME.get(sid, sid)
                lat_lon = ISTASYON_KOORD.get(sname)
                if not lat_lon:
                    base = sname.split("(")[0].strip() if "(" in sname else sname
                    lat_lon = ISTASYON_KOORD.get(base)
                lat = lat_lon[0] if lat_lon else None
                lon = lat_lon[1] if lat_lon else None
            istasyonlar_zenginlestirilmis.append({
                "ad": sname, "stop_id": sid, "lat": lat, "lon": lon,
            })
        return jsonify({
            "istasyonlar": istasyonlar_zenginlestirilmis,
            "hatlar": GRAF_DICT["hatlar"],
        })
    except Exception as hata:
        return jsonify({"hata": f"Graf verisi alınamadı: {hata}"}), 500


_STRATEJI_BASLIK = {
    "hizli":   "En Hızlı",
    "aktarma": "En Az Aktarma",
    "yurume":  "En Az Yürüme",
}
_STRATEJI_FN = {
    "hizli":   en_kisa_sureli_rota,
    "aktarma": en_az_aktarmali_rota,
    "yurume":  en_az_yurume_rota,
}


def _is_yurume(h: str) -> bool:
    return h in ("YURUME", "yurume", "Yürüme")


def _yurume_adim_temizle(adimlar: list[dict]) -> list[dict]:
    if not adimlar:
        return adimlar
    temiz = []
    i = 0

    def _isle_yurume_blogu(durak_den: str, j: int) -> tuple[str, str | None, dict | None, int]:
        """YURUME bloğunu tara: (durak_e, sonraki_hat, in_adimi, yeni_j) döndür."""
        durak_e = durak_den
        sonraki_hat = None
        in_adimi = None
        while j < len(adimlar):
            nxt = adimlar[j]
            if nxt.get("tip") == "aktarma" and _is_yurume(nxt.get("hat_den", "")):
                durak_e = nxt.get("durak", durak_e)
                sonraki_hat = nxt.get("hat_e")
                j += 1
                break
            if nxt.get("tip") == "in":
                durak_e = nxt.get("durak", durak_e)
                in_adimi = nxt
                j += 1
                break
            if nxt.get("tip") in ("bin", "aktarma"):
                h = nxt.get("hat") or nxt.get("hat_e", "")
                if h and not _is_yurume(h):
                    durak_e = nxt.get("durak", durak_e)
                    sonraki_hat = nxt.get("hat", nxt.get("hat_e"))
                    break
            j += 1
        return durak_e, sonraki_hat, in_adimi, j

    while i < len(adimlar):
        a = adimlar[i]

        # CASE 1: bin, hat=YURUME → yürüme başlangıcı (rota yürüyerek açılıyor)
        if a.get("tip") == "bin" and _is_yurume(a.get("hat", "")):
            durak_den = a.get("durak", "")
            durak_e, sonraki_hat, in_adimi, j = _isle_yurume_blogu(durak_den, i + 1)
            if durak_den != durak_e:
                temiz.append({"tip": "yurume", "durak_den": durak_den, "durak_e": durak_e})
            if in_adimi:
                temiz.append(in_adimi)
            elif sonraki_hat:
                temiz.append({"tip": "bin", "durak": durak_e, "stop_id": "", "hat": sonraki_hat})
            i = j
            continue

        # CASE 2: devam, hat=YURUME → atla
        if a.get("tip") == "devam" and _is_yurume(a.get("hat", "")):
            i += 1
            continue

        # CASE 3: aktarma, hat_den=YURUME → yürüyerek bu noktaya gelinmiş, şimdi hat_e'ye bin
        # router.py bazen {bin, hat=X, durak=A} + {aktarma, YURUME→X, durak=B} üretir.
        # A=yürüyüşün başlangıcı, B=gerçek biniş noktası — önceki bin'i düzelt.
        if a.get("tip") == "aktarma" and _is_yurume(a.get("hat_den", "")):
            durak_e = a.get("durak", "")
            sonraki_hat = a.get("hat_e")
            if temiz and temiz[-1].get("tip") == "bin" and temiz[-1].get("hat") == sonraki_hat:
                durak_den = temiz[-1].get("durak", "")
                temiz.pop()
                if durak_den != durak_e:
                    temiz.append({"tip": "yurume", "durak_den": durak_den, "durak_e": durak_e})
                temiz.append({"tip": "bin", "durak": durak_e, "stop_id": a.get("stop_id", ""), "hat": sonraki_hat})
            i += 1
            continue

        # CASE 4: aktarma, hat_e=YURUME → aktarma noktasından yürüme başlıyor
        if a.get("tip") == "aktarma" and _is_yurume(a.get("hat_e", "")):
            durak_den = a.get("durak", "")
            durak_e, sonraki_hat, in_adimi, j = _isle_yurume_blogu(durak_den, i + 1)
            if durak_den != durak_e:
                temiz.append({"tip": "yurume", "durak_den": durak_den, "durak_e": durak_e})
            if in_adimi:
                temiz.append(in_adimi)
            elif sonraki_hat:
                temiz.append({"tip": "bin", "durak": durak_e, "stop_id": "", "hat": sonraki_hat})
            i = j
            continue

        temiz.append(a)
        i += 1

    # Son `in` adımının hat'ı YURUME ise geriye bakıp gerçek hattı bul
    if temiz and temiz[-1].get("tip") == "in":
        if not temiz[-1].get("hat") or _is_yurume(temiz[-1].get("hat", "")):
            for adim in reversed(temiz[:-1]):
                h = adim.get("hat") or adim.get("hat_e")
                if h and not _is_yurume(h):
                    temiz[-1]["hat"] = h
                    break
    return temiz


def _hat_zinciri_ozeti(rota: dict) -> list[str]:
    sira: list[str] = []
    for h in rota.get("hatlar", []):
        if not sira or sira[-1] != h:
            sira.append(h)
    return sira


@app.route("/api/rota", methods=["POST"])
def api_rota():
    try:
        veri = request.get_json(silent=True) or {}
        baslangic = (veri.get("baslangic") or "").strip()
        hedef     = (veri.get("hedef")     or "").strip()
        strateji  = (veri.get("strateji")  or "aktarma").strip().lower()
        bas_stop_ids = veri.get("bas_stop_ids") or []
        hdf_stop_ids = veri.get("hdf_stop_ids") or []

        if not baslangic or not hedef:
            return jsonify({"hata": "Başlangıç ve hedef istasyonları belirtin."}), 400

        def _resolve_stop_ids(name: str) -> list[str] | None:
            if name in GRAF.istasyonlar:
                return [name]
            canon_names = CANONICAL_MAP.get(name)
            if canon_names:
                ids = []
                for sn in canon_names:
                    ids.extend(STOP_NAME_TO_IDS.get(sn, []))
                if ids:
                    return ids
            direct_ids = STOP_NAME_TO_IDS.get(name)
            if direct_ids:
                return direct_ids
            name_norm = tr_lower(name)
            for sn, sids in STOP_NAME_TO_IDS.items():
                if tr_lower(sn) == name_norm:
                    return sids
            for cn, cnames in CANONICAL_MAP.items():
                if tr_lower(cn) == name_norm:
                    ids = []
                    for sn in cnames:
                        ids.extend(STOP_NAME_TO_IDS.get(sn, []))
                    if ids:
                        return ids
            return None

        if bas_stop_ids and hdf_stop_ids:
            bas_nodes = [sid for sid in bas_stop_ids if sid in GRAF.istasyonlar]
            hdf_nodes = [sid for sid in hdf_stop_ids if sid in GRAF.istasyonlar]
        else:
            bas_nodes = _resolve_stop_ids(baslangic)
            hdf_nodes = _resolve_stop_ids(hedef)

        if not bas_nodes:
            return jsonify({"hata": f"Başlangıç istasyonu bulunamadı: '{baslangic}'"}), 400
        if not hdf_nodes:
            return jsonify({"hata": f"Hedef istasyonu bulunamadı: '{hedef}'"}), 400
        if bas_stop_ids and hdf_stop_ids:
            ortak = any(sid in hdf_stop_ids for sid in bas_stop_ids)
            if ortak:
                return jsonify({"hata": "Başlangıç ve hedef aynı olamaz."}), 400
        elif baslangic == hedef:
            return jsonify({"hata": "Başlangıç ve hedef aynı olamaz."}), 400
        if strateji not in _STRATEJI_FN:
            return jsonify({"hata": f"Geçersiz strateji: '{strateji}'"}), 400

        rota = _STRATEJI_FN[strateji](GRAF, bas_nodes, hdf_nodes)
        if not rota:
            return jsonify({"hata": "Bu iki istasyon arasında bağlantı bulunamadı."}), 404

        rota["yol"] = [_temiz_durak_adi(tr_title(STOP_ID_TO_NAME.get(sid, sid))) for sid in rota.get("yol", [])]
        rota["aktarma_noktalari"] = [
            _temiz_durak_adi(tr_title(STOP_ID_TO_NAME.get(sid, sid))) for sid in rota.get("aktarma_noktalari", [])
        ]

        zincir = _hat_zinciri_ozeti(rota)
        print(f"[ROTA] {baslangic} → {hedef} [{strateji}] sure={rota['sure']}dk aktarma={rota['aktarma']} hatlar={zincir}")

        rota = {**rota, "strateji": _STRATEJI_BASLIK[strateji]}
        return jsonify({"baslangic": baslangic, "hedef": hedef, "rotalar": [rota]})

    except Exception as hata:
        return jsonify({"hata": f"Sunucu hatası: {hata}"}), 500


@app.route("/api/hat-profil", methods=["GET"])
def api_hat_profil():
    try:
        hat_kodu = request.args.get("hat", "").strip().upper()
        yon      = request.args.get("yon", "ileri").strip()

        if not hat_kodu:
            return jsonify({"hata": "hat parametresi gerekli."}), 400

        stop_ids = HAT_STOP_CACHE.get(hat_kodu)
        if not stop_ids:
            for k, v in HAT_STOP_CACHE.items():
                if k.upper() == hat_kodu:
                    stop_ids = v
                    hat_kodu = k
                    break
        if not stop_ids:
            return jsonify({"hata": f"Hat bulunamadı: '{hat_kodu}'"}), 404

        if yon == "reverse":
            stop_ids = list(reversed(stop_ids))

        duraklar = []
        koordinatlar = []
        mesafeler = [0.0]
        toplam_km = 0.0

        for i, sid in enumerate(stop_ids):
            meta = GRAF.node_meta(sid) or {}
            koord = GRAF.node_koord(sid)
            lat, lon = koord if koord else (None, None)
            duraklar.append({
                "stop_id": sid,
                "stop_name": meta.get("stop_name") or meta.get("name", sid),
            })
            koordinatlar.append([lat, lon])
            if i > 0 and lat is not None and koordinatlar[i - 1][0] is not None:
                p = koordinatlar[i - 1]
                d = _haversine(p[0], p[1], lat, lon)
                toplam_km += d
            mesafeler.append(round(toplam_km, 3))

        return jsonify({
            "hat": hat_kodu, "yon": yon,
            "durak_sayisi": len(duraklar),
            "toplam_km": round(toplam_km, 2),
            "duraklar": duraklar,
            "mesafeler": mesafeler,
            "koordinatlar": koordinatlar,
        })
    except Exception as hata:
        return jsonify({"hata": f"Hat profil hatası: {hata}"}), 500


# ── Endpoints — İETT Otobüs (YENİ) ───────────────────────────────────────────

@app.route("/api/iett-rota", methods=["POST"])
def api_iett_rota():
    try:
        veri      = request.get_json(silent=True) or {}
        baslangic = (veri.get("baslangic") or "").strip()
        hedef     = (veri.get("hedef")     or "").strip()
        strateji  = (veri.get("strateji")  or "hizli").strip().lower()
        bas_stop_ids = veri.get("bas_stop_ids") or []
        hdf_stop_ids = veri.get("hdf_stop_ids") or []

        if not baslangic or not hedef:
            return jsonify({"hata": "Başlangıç ve hedef belirtin."}), 400
        if bas_stop_ids and hdf_stop_ids:
            ortak = any(sid in hdf_stop_ids for sid in bas_stop_ids)
            if ortak:
                return jsonify({"hata": "Başlangıç ve hedef aynı olamaz."}), 400
        elif baslangic == hedef:
            return jsonify({"hata": "Başlangıç ve hedef aynı olamaz."}), 400

        if bas_stop_ids and hdf_stop_ids:
            bas_ids = [sid for sid in bas_stop_ids if iett_stop_exists(sid)]
            hdf_ids = [sid for sid in hdf_stop_ids if iett_stop_exists(sid)]
        else:
            bas_ids = iett_isim_to_ids(baslangic)
            hdf_ids = iett_isim_to_ids(hedef)

        if not bas_ids:
            return jsonify({"hata": f"Durak bulunamadı: '{baslangic}'"}), 400
        if not hdf_ids:
            return jsonify({"hata": f"Durak bulunamadı: '{hedef}'"}), 400

        rota = iett_dijkstra(bas_ids, hdf_ids, strateji=strateji)
        if not rota:
            return jsonify({"hata": "Bağlantı bulunamadı."}), 404

        print(f"[İETT] {baslangic} → {hedef} [{strateji}] sure={rota['sure']}dk aktarma={rota['aktarma']}")
        return jsonify({"baslangic": baslangic, "hedef": hedef, "rotalar": [rota]})

    except Exception as hata:
        return jsonify({"hata": f"Sunucu hatası: {hata}"}), 500


@app.route("/api/iett-durak-ara", methods=["GET"])
def api_iett_durak_ara():
    try:
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify([])
        return jsonify(iett_durak_ara(q, max_sonuc=10))
    except Exception as hata:
        return jsonify({"hata": str(hata)}), 500


# ── Çalıştırma ────────────────────────────────────────────────────────────────



@app.route("/api/akilli-rota", methods=["POST"])
def api_akilli_rota():
    try:
        veri      = request.get_json(silent=True) or {}
        baslangic = (veri.get("baslangic") or "").strip()
        hedef     = (veri.get("hedef")     or "").strip()
        strateji  = (veri.get("strateji")  or "aktarma").strip().lower()
        bas_stop_ids = veri.get("bas_stop_ids") or []
        hdf_stop_ids = veri.get("hdf_stop_ids") or []
        bas_sistem = (veri.get("bas_sistem") or "").strip().lower()
        hdf_sistem = (veri.get("hdf_sistem") or "").strip().lower()
        bas_label = (veri.get("bas_label") or baslangic).strip()
        hdf_label = (veri.get("hdf_label") or hedef).strip()

        if not baslangic or not hedef:
            return jsonify({"hata": "Başlangıç ve hedef belirtin."}), 400

        STRATEJI_BASLIK = {"hizli": "En Hızlı", "aktarma": "En Az Aktarma", "yurume": "En Az Yürüme"}
        fn = {"hizli": en_kisa_sureli_rota, "aktarma": en_az_aktarmali_rota, "yurume": en_az_yurume_rota}.get(strateji, en_az_aktarmali_rota)

        def _resolve(name):
            if name in GRAF.istasyonlar: return [name]
            canon = CANONICAL_MAP.get(name)
            if canon:
                ids = []
                for sn in canon: ids.extend(STOP_NAME_TO_IDS.get(sn, []))
                if ids: return ids
            direct = STOP_NAME_TO_IDS.get(name)
            if direct: return direct
            name_norm = tr_lower(name)
            for sn, sids in STOP_NAME_TO_IDS.items():
                if tr_lower(sn) == name_norm:
                    return sids
            for cn, names in CANONICAL_MAP.items():
                if tr_lower(cn) == name_norm:
                    ids = []
                    for sn in names: ids.extend(STOP_NAME_TO_IDS.get(sn, []))
                    if ids: return ids
            return None

        secim_var = bool(bas_stop_ids and hdf_stop_ids and bas_sistem and hdf_sistem)

        # Her iki sistemde hesapla
        bas_rail = None
        hdf_rail = None
        bas_ids = None
        hdf_ids = None

        if secim_var:
            # Her iki sistemin ID listelerini çıkar (sistem karışık olabilir)
            bas_rail = [sid for sid in bas_stop_ids if sid in GRAF.istasyonlar]
            hdf_rail = [sid for sid in hdf_stop_ids if sid in GRAF.istasyonlar]
            bas_ids  = [sid for sid in bas_stop_ids if iett_stop_exists(sid)]
            hdf_ids  = [sid for sid in hdf_stop_ids if iett_stop_exists(sid)]
        else:
            bas_rail = _resolve(baslangic)
            hdf_rail = _resolve(hedef)

        def _rayli_adim_olustur(yol_names, hatlar):
            """yol isimleri + hat listesinden adım-adım tarif üretir."""
            if len(yol_names) < 2 or not hatlar:
                return []
            # Aktarma sanal kenarlarını atlayarak temiz durak+hat listesi oluştur
            clean_stops = []
            clean_hats = []
            for i in range(len(hatlar)):
                hat = hatlar[i]
                if hat.startswith("aktarma_") or hat == "Aktarma":
                    continue
                if not clean_stops:
                    clean_stops.append(yol_names[i] if i < len(yol_names) else "")
                nxt = yol_names[i + 1] if i + 1 < len(yol_names) else ""
                clean_stops.append(nxt)
                clean_hats.append(hat)
            if len(clean_stops) < 2:
                return []
            adimlar = [{"tip": "bin", "durak": clean_stops[0], "hat": clean_hats[0]}]
            current_hat = clean_hats[0]
            seg_start = 0
            for i in range(1, len(clean_stops)):
                is_last = (i == len(clean_stops) - 1)
                next_hat = clean_hats[i] if i < len(clean_hats) else None
                if is_last:
                    devam = i - seg_start - 1
                    if devam > 0:
                        adimlar.append({"tip": "devam", "hat": current_hat, "durak_sayisi": devam})
                    adimlar.append({"tip": "in", "durak": clean_stops[i], "hat": current_hat})
                elif next_hat != current_hat:
                    devam = i - seg_start - 1
                    if devam > 0:
                        adimlar.append({"tip": "devam", "hat": current_hat, "durak_sayisi": devam})
                    adimlar.append({"tip": "aktarma", "durak": clean_stops[i], "hat_den": current_hat, "hat_e": next_hat})
                    current_hat = next_hat
                    seg_start = i
            return adimlar

        def _rayli_isle(rota_r):
            orijinal_yol_ids = list(rota_r.get("yol", []))
            rota_r["yol"] = [_temiz_durak_adi(tr_title(STOP_ID_TO_NAME.get(s, s))) for s in orijinal_yol_ids]
            rota_r["yol_stop_ids"] = orijinal_yol_ids
            rota_r["aktarma_noktalari"] = [_temiz_durak_adi(tr_title(STOP_ID_TO_NAME.get(s, s))) for s in rota_r.get("aktarma_noktalari", [])]
            rota_r["kaynak"] = "rayli"
            rota_r["adimlar"] = _rayli_adim_olustur(rota_r["yol"], rota_r.get("hatlar", []))
            koordlar = []
            for i, sid in enumerate(orijinal_yol_ids):
                meta = GRAF.node_meta(sid)
                if meta:
                    lat = meta.get("stop_lat") or meta.get("lat")
                    lon = meta.get("stop_lon") or meta.get("lon")
                    if lat and lon:
                        koordlar.append([lat, lon])
                        continue
                stop_name = rota_r["yol"][i] if i < len(rota_r["yol"]) else sid
                if stop_name in ISTASYON_KOORD:
                    lat, lon = ISTASYON_KOORD[stop_name]
                    koordlar.append([lat, lon])
                elif sid in ISTASYON_KOORD:
                    lat, lon = ISTASYON_KOORD[sid]
                    koordlar.append([lat, lon])
            rota_r["koordinatlar"] = koordlar

        rota_rail_hizli = None
        rota_rail_aktarma = None
        if bas_rail and hdf_rail and len(bas_rail) > 0 and len(hdf_rail) > 0:
            rota_rail_hizli = en_kisa_sureli_rota(GRAF, bas_rail, hdf_rail)
            if rota_rail_hizli:
                _rayli_isle(rota_rail_hizli)
            rota_rail_aktarma = en_az_aktarmali_rota(GRAF, bas_rail, hdf_rail)
            if rota_rail_aktarma:
                _rayli_isle(rota_rail_aktarma)

        # Koordinat varsa en yakın durağı seç, yoksa isim eşleştir
        if not secim_var:
            bas_lat = veri.get("bas_lat")
            bas_lon = veri.get("bas_lon")
            hdf_lat = veri.get("hdf_lat")
            hdf_lon = veri.get("hdf_lon")

            # max_sonuc=5: aynı isimde birden fazla durak (her iki yön) Dijkstra'ya verilir
            # → yanlış yön durağı seçildiğinde oluşan "53 durak" sorununu önler
            if bas_lat and bas_lon:
                bas_ids = iett_isim_to_ids_koord(baslangic, bas_lat, bas_lon, max_sonuc=5)
                if not bas_ids:
                    bas_ids = iett_isim_to_ids(baslangic)
            else:
                bas_ids = iett_isim_to_ids(baslangic)

            if hdf_lat and hdf_lon:
                hdf_ids = iett_isim_to_ids_koord(hedef, hdf_lat, hdf_lon, max_sonuc=5)
            else:
                hdf_ids = iett_isim_to_ids(hedef)

        # İETT'de olmayan stop_id'leri filtrele
        if hdf_ids:
            hdf_ids = [hid for hid in hdf_ids if iett_stop_exists(hid)]
        if bas_ids:
            bas_ids = [bid for bid in bas_ids if iett_stop_exists(bid)]

        if secim_var:
            # Cross-sistem: başlangıç raylı ama hedef İETT (veya tersi) — her ikisi de boş olmamalı
            bas_ok = bool(bas_rail or bas_ids)
            hdf_ok = bool(hdf_rail or hdf_ids)
            if not bas_ok:
                return jsonify({"hata": f"Seçilen başlangıç durağı bulunamadı: '{bas_label}'"}), 400
            if not hdf_ok:
                return jsonify({"hata": f"Seçilen hedef durağı bulunamadı: '{hdf_label}'"}), 400

        rota_iett = None  # artık kullanılmıyor, iett_hizli/iett_aktarmasiz bunu karşılıyor

        # Kazananı seç — çoklu-hedef skor sistemi
        def skor(rota, mod):
            sure = rota.get("sure", 0)
            aktarma = rota.get("aktarma", 0)
            yurume_sure = 0
            adimlar = rota.get("adimlar", [])
            for a in adimlar:
                if a.get("tip") == "yurume":
                    yurume_sure += a.get("sure", 2)

            if mod == "aktarma":
                # Aktarma minimize etme: çok yüksek ceza
                return (aktarma * 1000) + sure + yurume_sure * 2.0
            
            if mod == "yurume":
                return (yurume_sure * 10) + sure + (aktarma * 10)

            # hizli: süre öncelikli, aktarma cezası minimal (2dk)
            return sure + (aktarma * 2) + yurume_sure * 1.2

        # ── Aday Toplama ──────────────────────────────────────────────────
        adaylar = []

        # 1. Raylı/Vapur Adayları (En iyi 5 Pareto-optimal rota)
        if bas_rail and hdf_rail:
            r_adaylar = k_en_iyi_rota(GRAF, bas_rail, hdf_rail, k=5)
            for r in r_adaylar:
                _rayli_isle(r)
                adaylar.append(r)

        # 2. İETT Adayları
        if bas_ids and hdf_ids:
            # Hem hızlı hem aktarmasız IETT seçeneklerini ekle
            i_hizli = iett_dijkstra(bas_ids, hdf_ids, strateji="hizli")
            if i_hizli:
                i_hizli["kaynak"] = "iett"
                adaylar.append(i_hizli)
            
            i_akt = iett_dijkstra(bas_ids, hdf_ids, strateji="aktarma")
            if i_akt and (not i_hizli or i_akt["yol"] != i_hizli["yol"]):
                i_akt["kaynak"] = "iett"
                adaylar.append(i_akt)

        # ── Cross-sistem aktarma: bir taraf raylı, diğer taraf İETT ──────────
        # Strateji: başlangıç-sistemden gelen rotayı bitiren yürüme köprüsü ile
        # karşı sistemdeki en yakın duraktaki rotaya bağla.
        # Basit yaklaşım: İETT grafikte bas→hdf_iett_koord, rayli grafte bas_rayli→hdf
        rota_cross_hizli = None
        rota_cross_aktarma = None
        _bas_is_rayli = bool(bas_rail) and not bool(bas_ids)
        _hdf_is_rayli = bool(hdf_rail) and not bool(hdf_ids)
        _bas_is_iett  = bool(bas_ids)  and not bool(bas_rail)
        _hdf_is_iett  = bool(hdf_ids)  and not bool(hdf_rail)
        _cross = (_bas_is_rayli and _hdf_is_iett) or (_bas_is_iett and _hdf_is_rayli)

        if _cross:
            # Raylı tarafın koordinatını al, İETT grafikte o koordinata en yakın durağa
            # rota bağla (yürüme mesafesi ~300m içinde olan durakları köprü say)
            import math as _cross_math

            def _koord_bul_rayli(ids):
                for _sid in ids:
                    _m = GRAF.node_meta(_sid)
                    if _m:
                        _lat = _m.get("stop_lat") or _m.get("lat")
                        _lon = _m.get("stop_lon") or _m.get("lon")
                        if _lat and _lon:
                            return float(_lat), float(_lon)
                return None, None

            def _yakin_iett_ids(lat, lon, max_m=500):
                """Koordinata en yakın İETT durak ID listesi döndür."""
                from services.router import tum_duraklar as _tum
                en_yakinlar = []
                for _d in _tum():
                    _dlat = _d["lat"] - lat
                    _dlon = _d["lon"] - lon
                    _dist = _cross_math.sqrt(_dlat**2 + _dlon**2) * 111000
                    if _dist <= max_m:
                        en_yakinlar.append((_dist, _d["stop_id"]))
                en_yakinlar.sort()
                return [sid for _, sid in en_yakinlar[:5]]

            def _yakin_rayli_ids(lat, lon, max_m=500):
                """Koordinata en yakın raylı sistem durak ID listesi döndür."""
                en_yakinlar = []
                for _sid in GRAF.istasyonlar:
                    _m = GRAF.node_meta(_sid)
                    if not _m:
                        continue
                    _lat = _m.get("stop_lat") or _m.get("lat")
                    _lon = _m.get("stop_lon") or _m.get("lon")
                    if not _lat or not _lon:
                        continue
                    _dlat = float(_lat) - lat
                    _dlon = float(_lon) - lon
                    _dist = _cross_math.sqrt(_dlat**2 + _dlon**2) * 111000
                    if _dist <= max_m:
                        en_yakinlar.append((_dist, _sid))
                en_yakinlar.sort()
                return [sid for _, sid in en_yakinlar[:5]]

            if _bas_is_iett and _hdf_is_rayli:
                # Başlangıç İETT → Hedef raylı
                # Adım 1: Raylı hedefe yakın İETT durakları bul → İETT'de bas→yakin_iett
                hdf_koord = _koord_bul_rayli(hdf_rail)
                if hdf_koord[0]:
                    yakin_iett = _yakin_iett_ids(*hdf_koord, max_m=600)
                    if yakin_iett:
                        _cx_h = iett_dijkstra(bas_ids, yakin_iett, strateji="hizli")
                        if _cx_h:
                            _cx_h["kaynak"] = "cross"
                            _cx_h["strateji"] = STRATEJI_BASLIK.get("hizli", "En Hızlı")
                            # Hedef raylı durak adını son durağa ekle
                            _cx_h["cross_hedef_ids"] = hdf_rail
                            rota_cross_hizli = _cx_h
                        _cx_a = iett_dijkstra(bas_ids, yakin_iett, strateji="aktarma")
                        if _cx_a:
                            _cx_a["kaynak"] = "cross"
                            _cx_a["strateji"] = STRATEJI_BASLIK.get("aktarma", "En Az Aktarma")
                            _cx_a["cross_hedef_ids"] = hdf_rail
                            rota_cross_aktarma = _cx_a
            elif _bas_is_rayli and _hdf_is_iett:
                # Başlangıç raylı → Hedef İETT
                bas_koord = _koord_bul_rayli(bas_rail)
                if bas_koord[0]:
                    yakin_iett_bas = _yakin_iett_ids(*bas_koord, max_m=600)
                    if yakin_iett_bas:
                        _cx_h = iett_dijkstra(yakin_iett_bas, hdf_ids, strateji="hizli")
                        if _cx_h:
                            _cx_h["kaynak"] = "cross"
                            _cx_h["strateji"] = STRATEJI_BASLIK.get("hizli", "En Hızlı")
                            _cx_h["cross_bas_ids"] = bas_rail
                            rota_cross_hizli = _cx_h
                        _cx_a = iett_dijkstra(yakin_iett_bas, hdf_ids, strateji="aktarma")
                        if _cx_a:
                            _cx_a["kaynak"] = "cross"
                            _cx_a["strateji"] = STRATEJI_BASLIK.get("aktarma", "En Az Aktarma")
                            _cx_a["cross_bas_ids"] = bas_rail
                            rota_cross_aktarma = _cx_a

        if rota_cross_hizli: adaylar.append(rota_cross_hizli)
        if rota_cross_aktarma: adaylar.append(rota_cross_aktarma)

        tum_rotalar = adaylar

        if not tum_rotalar:
            # Hata mesajında hangi sistem(ler)in denlendiğini belirt
            _denenenler = []
            if bas_rail or hdf_rail: _denenenler.append("Raylı")
            if bas_ids or hdf_ids:   _denenenler.append("İETT Otobüs")
            if _cross:               _denenenler.append("Cross-sistem")
            _msg = f"'{bas_label}' ile '{hdf_label}' arasında rota bulunamadı."
            if _denenenler:
                _msg += f" (Denenen: {', '.join(_denenenler)})"
            return jsonify({"hata": _msg}), 404

        # Tüm adaylar arasından en iyi olanı seç — sistem fark etmez
        en_hizli  = min(tum_rotalar, key=lambda r: skor(r, "hizli"))
        en_az_akt = min(tum_rotalar, key=lambda r: skor(r, "aktarma"))

        if strateji == "hizli":
            kazanan = en_hizli
        else:
            kazanan = en_az_akt

        if not kazanan:
            return jsonify({"hata": "Seçilen duraklar arasında bağlantı bulunamadı."}), 404

        # Kazananın strateji etiketini kullanıcının seçimine göre override et
        kazanan["strateji"] = STRATEJI_BASLIK.get(strateji, strateji)
        # aktarma_noktalari'nden YURUME geçişlerini temizle
        hatlar_raw = kazanan.get("hatlar", [])
        yol_raw = kazanan.get("yol", [])
        temiz_akt_nok = []
        for akt_ad in kazanan.get("aktarma_noktalari", []):
            if akt_ad in yol_raw:
                i = yol_raw.index(akt_ad)
                h_once = hatlar_raw[i-1] if i > 0 and i-1 < len(hatlar_raw) else ""
                if _is_yurume(h_once):
                    continue
            temiz_akt_nok.append(akt_ad)
        kazanan["aktarma_noktalari"] = temiz_akt_nok

        kazanan["adimlar"] = _yurume_adim_temizle(kazanan.get("adimlar", []))

        # Renk tabloları (segment ve hat_renkleri için ortak kullanım)
        HAT_TIPI_RENK = {
            "Metro":     "#1A4F8A",
            "Tramvay":   "#E30613",
            "Tren":      "#6D4C41",
            "Marmaray":  "#6D4C41",  # koyu kahve — Marmaray'a özgü, gri değil
            "Metrobüs":  "#8CC63F",
            "Vapur":     "#00A0B0",
            "Füniküler": "#E87722",
            "Teleferik": "#E87722",
            "Otobüs":    "#F59E0B",
            "Dolmuş":    "#F59E0B",
        }
        HAT_RENK = {
            "Taksim-Kabataş Füniküler":  "#E87722",
            "Kabataş-Kadıköy Vapuru":    "#00A0B0",
            "Eminönü-Kadıköy Vapuru":    "#00A0B0",
            "Eminönü-Üsküdar Vapuru":    "#00A0B0",
            "Kadıköy-Eminönü Vapuru":    "#00A0B0",
            "Üsküdar-Eminönü Vapuru":    "#00A0B0",
            "Kabataş-Eminönü Vapuru":    "#00A0B0",
        }
        hat_renk_map = {h["hat_adi"]: h["renk"] for h in GRAF_DICT.get("hatlar", [])}
        hat_tipi_map = {h["hat_adi"]: h["hat_tipi"] for h in GRAF_DICT.get("hatlar", [])}

        _MARMARAY_RENK = "#6D4C41"  # koyu kahve — Marmaray'a özgü

        def _hat_renk(h: str, fallback: str = "#F59E0B") -> str:
            if _is_yurume(h):
                return "#888888"
            if h.startswith("aktarma_"):
                return fallback
            # Marmaray: grafta hat_tipi="Metro" kayıtlı, isimle yakala
            if h in ("Marmaray", "Marmaray1", "Marmaray2") or h.startswith("Marmaray"):
                return _MARMARAY_RENK
            # Önce readable isimle HAT_RENK'e bak (hem orijinal hem çevrilmiş)
            readable = HAT_ISIMLERI.get(h, h)
            if readable in HAT_RENK:
                return HAT_RENK[readable]
            if h in HAT_RENK:
                return HAT_RENK[h]
            # Graf'tan hat tipine göre renk (raylı hatlar: M1, T1, vb.)
            tipi = hat_tipi_map.get(h, "")
            if tipi and tipi in HAT_TIPI_RENK:
                return HAT_TIPI_RENK[tipi]
            # İETT otobüs: rakam içeren hat adı (133N, 122D, 66 vb.) → #F59E0B
            if any(c.isdigit() for c in h):
                return "#F59E0B"
            if h in hat_renk_map:
                return hat_renk_map[h]
            return fallback

        # Segmentleri hizalı paketle — koordinatları koru, YURUME dahil
        if "hatlar" in kazanan:
            hatlar = kazanan.get("hatlar", [])
            koordlar = kazanan.get("koordinatlar", [])
            orijinal_renkler = kazanan.get("hat_renkleri", [])
            son_renk = "#1A4F8A"
            yeni_renkler = []
            for i, h in enumerate(hatlar):
                if _is_yurume(h):
                    yeni_renkler.append("#888888")
                elif h.startswith("aktarma_"):
                    yeni_renkler.append(son_renk)
                else:
                    # Orijinal rengi fallback olarak kullan (İETT router.py renklerini korur)
                    orig = orijinal_renkler[i] if i < len(orijinal_renkler) else son_renk
                    renk = _hat_renk(h, fallback=orig)
                    yeni_renkler.append(renk)
                    son_renk = renk
            kazanan["hat_renkleri"] = yeni_renkler
            # Segment mesafe eşiği: aynı hat içinde >40km atlama varsa segment atla
            def _koord_mesafe(a, b):
                if not a or not b or len(a) < 2 or len(b) < 2:
                    return 0
                import math
                dlat = a[0] - b[0]; dlon = a[1] - b[1]
                return math.sqrt(dlat*dlat + dlon*dlon) * 111

            segmentler = []
            for i in range(len(hatlar)):
                h = hatlar[i]
                # Aktarma sanal kenarları poliline'a ekleme
                if h.startswith("aktarma_") or h == "Aktarma":
                    continue
                if i + 1 < len(koordlar) and koordlar[i] and koordlar[i+1]:
                    mesafe = _koord_mesafe(koordlar[i], koordlar[i+1])
                    if mesafe > 40:  # 40km'den büyük atlama → hatalı koordinat, atla
                        continue
                    segmentler.append({
                        "coords": [koordlar[i], koordlar[i+1]],
                        "hat": h,
                        "renk": yeni_renkler[i],
                        "yurume": _is_yurume(h),
                    })
            kazanan["segmentler"] = segmentler

        # Hat isimlerini okunabilir yap
        if "hatlar" in kazanan:
            kazanan["hatlar"] = [HAT_ISIMLERI.get(h, h) for h in kazanan["hatlar"]]
        if "adimlar" in kazanan:
            for adim in kazanan["adimlar"]:
                for alan in ("hat", "hat_den", "hat_e"):
                    if alan in adim:
                        adim[alan] = HAT_ISIMLERI.get(adim[alan], adim[alan])
                for alan in ("durak", "durak_den", "durak_e"):
                    if alan in adim and adim[alan]:
                        adim[alan] = _temiz_durak_adi(tr_title(adim[alan]))

        # Debug: tüm adayları logla
        for r in tum_rotalar:
            _hatlar = r.get("hatlar", [])
            _unique = list(dict.fromkeys(h for h in _hatlar if not _is_yurume(h) and not h.startswith("aktarma_")))
            _seg_say = len(r.get("segmentler", r.get("koordinatlar", [])))
            print(f"  [ADAY] kaynak={r.get('kaynak','?'):5s} sure={r.get('sure',0):3d}dk "
                  f"akt={r.get('aktarma',0)} hatlar={_unique} "
                  f"skor_h={skor(r,'hizli'):.0f} skor_a={skor(r,'aktarma'):.0f}")
        _kazanan_hatlar = list(dict.fromkeys(
            HAT_ISIMLERI.get(h, h) for h in kazanan.get("hatlar", [])
            if not _is_yurume(h) and not h.startswith("aktarma_")
        ))
        print(f"[AKILLI] {bas_label}→{hdf_label} [{strateji}] ✓ kaynak={kazanan.get('kaynak')} "
              f"sure={kazanan['sure']}dk aktarma={kazanan['aktarma']} hatlar={_kazanan_hatlar}")
        return jsonify({"baslangic": bas_label, "hedef": hdf_label, "rotalar": [kazanan]})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"hata": f"Sunucu hatası: {e}"}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
