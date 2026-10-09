# -*- coding: utf-8 -*-
"""
preprocess.py — İETT otobüs GTFS → iett_graph.pkl

Sadece iett_ prefix'li dosyaları okur.
Raylı sistem dosyaları (routes.csv, stops.csv...) DOKUNULMAZ.

ÇALIŞTIR (1 kere, ~5-10 dk):
    cd ~/Desktop/akilli_sehir_navigasyon
    python3 preprocess.py

Üretir: data/iett_graph.pkl
"""
import csv, json, os, pickle, sys, time
import urllib.request as _urllib

BASE    = os.path.dirname(os.path.abspath(__file__))
GTFS    = os.path.join(BASE, "data", "gtfs")
OUT_PKL = os.path.join(BASE, "data", "iett_graph.pkl")
ILCE_CACHE_PATH = os.path.join(BASE, "data", "ilce_cache.json")

ROUTES     = os.path.join(GTFS, "iett_routes.csv")
TRIPS      = os.path.join(GTFS, "iett_trips.csv")
STOPS      = os.path.join(GTFS, "iett_stops.csv")
STOP_TIMES = os.path.join(GTFS, "iett_stop_times.csv")

print("=" * 60)
print("İETT Otobüs GTFS Preprocessing")
print("=" * 60)
for n, p in [("iett_routes.csv", ROUTES), ("iett_trips.csv", TRIPS),
             ("iett_stops.csv", STOPS), ("iett_stop_times.csv", STOP_TIMES)]:
    durum = "✅" if os.path.exists(p) else "❌ BULUNAMADI"
    print(f"  {n:<22}: {durum}")
print()

eksik = [n for n, p in [("iett_routes.csv", ROUTES), ("iett_trips.csv", TRIPS),
                         ("iett_stops.csv", STOPS), ("iett_stop_times.csv", STOP_TIMES)]
         if not os.path.exists(p)]
if eksik:
    print("HATA — Şu dosyalar bulunamadı:", eksik)
    sys.exit(1)

os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

ROUTE_TYPE = {
    0: ("Tramvay",   "#E30613"),
    1: ("Metro",     "#1A4F8A"),
    2: ("Tren",      "#6B3FA0"),
    3: ("Otobüs",    "#FFB800"),
    4: ("Vapur",     "#00A0B0"),
    5: ("Füniküler", "#E87722"),
    6: ("Teleferik", "#E87722"),
}
AVG_SURE = {
    "Metro": 2, "Tramvay": 2, "Tren": 3,
    "Otobüs": 3, "Vapur": 8, "Füniküler": 3, "Teleferik": 4,
}

# Gerçekte sefer yapmayan / iptal edilen hatlar
IPTAL_HATLAR = {"AND2K", "AND2S", "AND2Y"}  # short_name bazlı

# ── İlçe cache (Nominatim) ────────────────────────────────────────────────
_ILCE_CACHE: dict[tuple[float, float], str | None] = {}


def _ilce_cache_yukle() -> None:
    if not os.path.exists(ILCE_CACHE_PATH):
        return
    try:
        with open(ILCE_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            lat_s, lon_s = k.split(",")
            _ILCE_CACHE[(float(lat_s), float(lon_s))] = v
    except Exception:
        pass


def _ilce_cache_kaydet() -> None:
    try:
        with open(ILCE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({f"{k[0]},{k[1]}": v for k, v in _ILCE_CACHE.items()}, f,
                      ensure_ascii=False, indent=2)
    except OSError:
        pass


def _ilce_bul(lat: float, lon: float) -> str | None:
    """Nominatim reverse geocode — 1km grid cache ile ilçe bul."""
    anahtar = (round(lat, 2), round(lon, 2))
    if anahtar in _ILCE_CACHE:
        return _ILCE_CACHE[anahtar]
    try:
        url = (
            "https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&accept-language=tr"
        )
        req = _urllib.Request(url, headers={"User-Agent": "istanbul-nav/1.0"})
        with _urllib.urlopen(req, timeout=8) as r:
            veri = json.loads(r.read())
        adres = veri.get("address", {})
        ilce = (
            adres.get("district")
            or adres.get("town")
            or adres.get("city_district")
            or adres.get("suburb")
            or adres.get("county")
            or None
        )
        _ILCE_CACHE[anahtar] = ilce
        time.sleep(1.1)
        return ilce
    except Exception:
        _ILCE_CACHE[anahtar] = None
        return None

# ── 1) routes ────────────────────────────────────────────────────────────────
print("▶ 1/4  iett_routes.csv...")
route_map = {}
with open(ROUTES, encoding="utf-8-sig", newline="") as f:
    sample = f.read(512); f.seek(0)
    delim = ";" if sample.count(";") > sample.count(",") else ","
    for row in csv.DictReader(f, delimiter=delim):
        rid = str(row.get("route_id", "")).strip()
        rt  = int(row.get("route_type", 3) or 3)
        ht, renk = ROUTE_TYPE.get(rt, ("Otobüs", "#FFB800"))
        sn  = str(row.get("route_short_name", "")).strip() or rid
        if rid and sn not in IPTAL_HATLAR:
            route_map[rid] = {"short_name": sn, "hat_tipi": ht, "renk": renk}
print(f"   {len(route_map):,} hat")

# ── 2) trips ─────────────────────────────────────────────────────────────────
print("▶ 2/4  iett_trips.csv...")
trip_to_route = {}
with open(TRIPS, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        tid = str(row.get("trip_id", "")).strip()
        rid = str(row.get("route_id", "")).strip()
        if tid and rid in route_map:
            trip_to_route[tid] = route_map[rid]
print(f"   {len(trip_to_route):,} trip")

# ── 3) stops ─────────────────────────────────────────────────────────────────
print("▶ 3/4  iett_stops.csv...")
stop_meta = {}
with open(STOPS, encoding="utf-8-sig", newline="") as f:
    sample = f.read(512); f.seek(0)
    delim = ";" if sample.count(";") > sample.count(",") else ","
    for row in csv.DictReader(f, delimiter=delim):
        sid = str(row.get("stop_id", "")).strip()
        try:
            lat = float(row.get("stop_lat") or 0)
            lon = float(row.get("stop_lon") or 0)
        except (ValueError, TypeError):
            lat = lon = 0.0
        if sid:
            stop_meta[sid] = {
                "name": str(row.get("stop_name", "")).strip(),
                "lat": lat, "lon": lon,
            }
print(f"   {len(stop_meta):,} durak")

# İlçe bilgisi ekle (precompute)
print("   İlçe bilgisi hazırlanıyor (1km grid cache)...")
_ilce_cache_yukle()
_anahtarlar = {
    (round(m["lat"], 2), round(m["lon"], 2))
    for m in stop_meta.values()
    if m.get("lat") and m.get("lon") and m["lat"] != 0.0
}
_eksik = [k for k in sorted(_anahtarlar) if k not in _ILCE_CACHE]
for lat_k, lon_k in _eksik:
    _ilce_bul(lat_k, lon_k)
for sid, meta in stop_meta.items():
    lat = meta.get("lat") or 0.0
    lon = meta.get("lon") or 0.0
    if lat and lon:
        key = (round(lat, 2), round(lon, 2))
        meta["ilce"] = _ILCE_CACHE.get(key)
    else:
        meta["ilce"] = None
_ilce_cache_kaydet()

# ── 4) stop_times → graph ────────────────────────────────────────────────────
print("▶ 4/4  iett_stop_times.csv → graph (6M satır, birkaç dk)...")
t0 = time.time()

graph: dict = {}
processed = skipped = rows = 0
cur_tid = cur_info = None
cur_stops = []

def _haversine(sid1, sid2):
    """İki durak arası km cinsinden mesafe."""
    m1 = stop_meta.get(sid1, {})
    m2 = stop_meta.get(sid2, {})
    lat1, lon1 = m1.get("lat", 0), m1.get("lon", 0)
    lat2, lon2 = m2.get("lat", 0), m2.get("lon", 0)
    if not all([lat1, lon1, lat2, lon2]):
        return None
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Ortalama hız (km/dk)
HIZ = {"Metro": 0.6, "Tramvay": 0.4, "Tren": 0.8, "Otobüs": 0.35, "Vapur": 0.5, "Füniküler": 0.3}

def flush(tid, info, stops):
    global processed, skipped
    if not info:
        skipped += 1
        return
    avg_sure = AVG_SURE.get(info["hat_tipi"], 3)
    hiz = HIZ.get(info["hat_tipi"], 0.35)
    sn, ht, rk = info["short_name"], info["hat_tipi"], info["renk"]
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        km = _haversine(a, b)
        if km and km > 0:
            sure = max(1, round(km / hiz))
        else:
            sure = avg_sure
        if a not in graph:
            graph[a] = []
        graph[a].append((b, sure, sn, ht, rk))
    processed += 1

with open(STOP_TIMES, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        rows += 1
        if rows % 1_000_000 == 0:
            print(f"   {rows:,} satır | {processed:,} trip | {time.time()-t0:.0f}s", end="\r")
        tid = str(row.get("trip_id", "")).strip()
        sid = str(row.get("stop_id", "")).strip()
        if tid != cur_tid:
            if cur_tid:
                flush(cur_tid, cur_info, cur_stops)
            cur_tid  = tid
            cur_info = trip_to_route.get(tid)
            cur_stops = [sid]
        else:
            cur_stops.append(sid)

if cur_tid:
    flush(cur_tid, cur_info, cur_stops)

print(f"\n   {rows:,} satır | {processed:,} trip | {skipped:,} atlandı | {time.time()-t0:.1f}s")

# Deduplicate
total_before = sum(len(v) for v in graph.values())
for sid in graph:
    seen = set(); uniq = []
    for e in graph[sid]:
        k = (e[0], e[2])
        if k not in seen:
            seen.add(k); uniq.append(e)
    graph[sid] = uniq
total_after = sum(len(v) for v in graph.values())
print(f"   Deduplicate: {total_before:,} → {total_after:,} kenar")


# ── 5) Yürüme bağlantıları (Overpass — tek sorgu) ───────────────────────────
print("▶ 5/5  Yürüme bağlantıları (Overpass tek sorgu)...")
import math, urllib.request, json, time as _time

YURUME_ESIK_KM  = 0.5   # 500m
YURUME_HIZ_M_DK = 80    # 80 m/dk
OVERPASS_URL    = "https://overpass-api.de/api/interpreter"

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── Adım 1: Lokal GeoJSON dosyasından yaya yollarını yükle ──────────────────
GEOJSON_YOL = os.path.join(os.path.expanduser("~"), "Desktop", "export.geojson")
yaya_nodelar = []
if os.path.exists(GEOJSON_YOL):
    print(f"   GeoJSON yükleniyor: {GEOJSON_YOL}")
    with open(GEOJSON_YOL, encoding="utf-8") as _gf:
        _gdata = json.load(_gf)
    for feat in _gdata.get("features", []):
        geom = feat.get("geometry", {})
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])
        if gtype == "LineString":
            for lon, lat in coords:
                yaya_nodelar.append({"lat": lat, "lon": lon})
        elif gtype == "MultiLineString":
            for line in coords:
                for lon, lat in line:
                    yaya_nodelar.append({"lat": lat, "lon": lon})
    print(f"   ✅ {len(yaya_nodelar):,} yaya yolu node'u yüklendi.")
else:
    print(f"   ⚠️  GeoJSON bulunamadı ({GEOJSON_YOL}) — kuş uçuşu fallback kullanılacak")

# ── Adım 2: Koordinatlı durakları listele ────────────────────────────────────
koordinatli = [
    (sid, m["lat"], m["lon"])
    for sid, m in stop_meta.items()
    if m.get("lat") and m.get("lon") and m["lat"] != 0.0
]
print(f"   {len(koordinatli):,} koordinatlı durak taranıyor...")

def _en_yakin_yaya_m(lat1, lon1, lat2, lon2):
    """Yaya node'larından geçen en kısa mesafe tahmini."""
    if not yaya_nodelar:
        return _haversine_m(lat1, lon1, lat2, lon2) * 1.3

    # BBox içindeki node'ları filtrele
    min_lat = min(lat1, lat2) - 0.005
    max_lat = max(lat1, lat2) + 0.005
    min_lon = min(lon1, lon2) - 0.005
    max_lon = max(lon1, lon2) + 0.005
    yakin = [n for n in yaya_nodelar
             if min_lat <= n["lat"] <= max_lat and min_lon <= n["lon"] <= max_lon]

    if not yakin:
        return _haversine_m(lat1, lon1, lat2, lon2) * 1.3

    # En yakın başlangıç ve bitiş node'u
    def en_yakin_node(tlat, tlon):
        return min(yakin, key=lambda n: (n["lat"]-tlat)**2 + (n["lon"]-tlon)**2)

    n1 = en_yakin_node(lat1, lon1)
    n2 = en_yakin_node(lat2, lon2)
    return _haversine_m(n1["lat"], n1["lon"], n2["lat"], n2["lon"]) * 1.2

yurume_kenar = 0
for i, (sid_a, lat_a, lon_a) in enumerate(koordinatli):
    for sid_b, lat_b, lon_b in koordinatli[i+1:]:
        kus_m = _haversine_m(lat_a, lon_a, lat_b, lon_b)
        if kus_m > YURUME_ESIK_KM * 1000 or sid_a == sid_b:
            continue

        # Aynı isimli + 80m altı = karşı kaldırım, bağlama
        isim_a = stop_meta.get(sid_a, {}).get("name", "")
        isim_b = stop_meta.get(sid_b, {}).get("name", "")
        if isim_a == isim_b and kus_m < 80:
            continue

        # GPS hatası / duplicate nokta
        if kus_m < 5:
            continue


        gercek_m = _en_yakin_yaya_m(lat_a, lon_a, lat_b, lon_b)
        if gercek_m > YURUME_ESIK_KM * 1000:
            continue

        sure_dk = max(1, round(gercek_m / YURUME_HIZ_M_DK))
        if sure_dk > 3:  # 3dk = ~240m, üstünü ekleme
            continue

        if sid_a not in graph: graph[sid_a] = []
        if sid_b not in graph: graph[sid_b] = []

        mevcut_a = {(e[0], e[2]) for e in graph[sid_a]}
        if (sid_b, "YURUME") not in mevcut_a:
            graph[sid_a].append((sid_b, sure_dk, "YURUME", "Yürüme", "#888888"))
            yurume_kenar += 1

        mevcut_b = {(e[0], e[2]) for e in graph[sid_b]}
        if (sid_a, "YURUME") not in mevcut_b:
            graph[sid_b].append((sid_a, sure_dk, "YURUME", "Yürüme", "#888888"))
            yurume_kenar += 1

    if i % 500 == 0:
        print(f"   {i}/{len(koordinatli)} durak | {yurume_kenar} yürüme kenarı", end="\r")

print(f"\n   ✅ {yurume_kenar} yürüme kenarı eklendi.")


# ── Kaydet ───────────────────────────────────────────────────────────────────
print("\n▶ Kaydediliyor...")
with open(OUT_PKL, "wb") as f:
    pickle.dump({"graph": graph, "stop_meta": stop_meta}, f,
                protocol=pickle.HIGHEST_PROTOCOL)

size = os.path.getsize(OUT_PKL) / 1024 / 1024
print(f"   iett_graph.pkl → {OUT_PKL}  ({size:.1f} MB)")
print()
print("=" * 60)
print("✅ TAMAMLANDI")
print(f"   {len(graph):,} durak")
print(f"   {total_after:,} bağlantı kenarı")
print(f"   Raylı sistem (routes.csv vb.) → DOKUNULMADI ✅")
print("=" * 60)
print("\nSıradaki adım:  python3 app.py")
