# -*- coding: utf-8 -*-
# YENİ
"""
data/walking_edge_yukleyici.py — Yakın duraklar arası yürüme kenarı enjeksiyonu.

Algoritma: Grid/Bucket yaklaşımı
    Her node 0.001° ≈ 111m x 111m hücreye atanır.
    Sadece aynı + 8 komşu hücre taranır → O(n) ortalama.
    Haversine ile kesin mesafe doğrulanır.
"""  # YENİ

from __future__ import annotations  # YENİ

import math  # YENİ
from collections import defaultdict  # YENİ
from typing import TYPE_CHECKING  # YENİ

if TYPE_CHECKING:  # YENİ
    from models.graf import Graf  # YENİ

# YENİ
GRID_BOYUT = 0.001  # ~111m x ~111m hücre  # YENİ
KOMSULAR = [(-1, -1), (-1, 0), (-1, 1),  # YENİ
            (0,  -1), (0,  0), (0,  1),  # YENİ
            (1,  -1), (1,  0), (1,  1)]  # YENİ

# YENİ: Boğaz'ı aşan yürüme kenarlarını engelle
KARA_ENGELI_CIFTLER: set[frozenset] = {  # YENİ
    frozenset({"Üsküdar", "Beşiktaş"}),  # YENİ
    frozenset({"Üsküdar", "Kabataş"}),  # YENİ
    frozenset({"Üsküdar", "Eminönü"}),  # YENİ
    frozenset({"Kadıköy", "Beşiktaş"}),  # YENİ
    frozenset({"Kadıköy", "Eminönü"}),  # YENİ
    frozenset({"Kadıköy", "Karaköy"}),  # YENİ
}  # YENİ


def _grid_anahtari(lat: float, lon: float) -> tuple[int, int]:  # YENİ
    """Koordinatı grid hücre anahtarına çevirir."""  # YENİ
    return (int(lat / GRID_BOYUT), int(lon / GRID_BOYUT))  # YENİ


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:  # YENİ
    """İki koordinat arası mesafeyi METRE olarak döndürür."""  # YENİ
    R = 6_371_000  # YENİ
    dlat = math.radians(lat2 - lat1)  # YENİ
    dlon = math.radians(lon2 - lon1)  # YENİ
    a = (math.sin(dlat / 2) ** 2  # YENİ
         + math.cos(math.radians(lat1))  # YENİ
         * math.cos(math.radians(lat2))  # YENİ
         * math.sin(dlon / 2) ** 2)  # YENİ
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))  # YENİ


def walking_edges_ekle(graf: "Graf", max_metre: float = 100.0) -> int:  # YENİ
    """
    Graf içindeki tüm node'lar arasında max_metre altında olanları
    yürüme kenarıyla bağlar.

    - Grid/bucket yaklaşımıyla O(n) ortalama karmaşıklık.
    - node_koord() None döndürenleri atlar.
    - Zaten doğrudan bağlı (herhangi bir hat ile) çiftleri atlar.
    - Hem a→b hem b→a kenarı eklenir.
    - Yinelenen kenarlar ValueError ile yutulur.

    Dönüş: eklenen kenar sayısı
    """  # YENİ
    # ── 1. Grid inşa et ──────────────────────────────────────────────────────  # YENİ
    grid: dict[tuple[int, int], list[str]] = defaultdict(list)  # YENİ
    node_koordlari: dict[str, tuple[float, float]] = {}  # YENİ

    for node_id in graf.istasyonlar:  # YENİ
        koord = graf.node_koord(node_id)  # YENİ
        if koord is None:  # YENİ
            continue  # YENİ
        lat, lon = koord  # YENİ
        if lat == 0.0 and lon == 0.0:  # YENİ
            continue  # YENİ
        node_koordlari[node_id] = (lat, lon)  # YENİ
        grid[_grid_anahtari(lat, lon)].append(node_id)  # YENİ

    # ── 2. Mevcut komşuluk setini önbelleğe al ───────────────────────────────  # YENİ
    # Zaten doğrudan bağlı çiftleri O(1) ile kontrol etmek için.  # YENİ
    baglantilar: set[tuple[str, str]] = set()  # YENİ
    for node_a, hatlar in graf.komsuluk.items():  # YENİ
        for hat in hatlar:  # YENİ
            node_b = hat.diger_uc(node_a)  # YENİ
            baglantilar.add((node_a, node_b))  # YENİ
            baglantilar.add((node_b, node_a))  # YENİ

    # ── 3. Grid komşuluk taraması ────────────────────────────────────────────  # YENİ
    max_km = max_metre / 1000.0  # YENİ
    islenen_ciftler: set[frozenset] = set()  # YENİ
    eklenen_kenar = 0  # YENİ

    for node_a, (lat_a, lon_a) in node_koordlari.items():  # YENİ
        gx, gy = _grid_anahtari(lat_a, lon_a)  # YENİ

        for dx, dy in KOMSULAR:  # YENİ
            aday_hucre = (gx + dx, gy + dy)  # YENİ
            for node_b in grid.get(aday_hucre, []):  # YENİ
                if node_b == node_a:  # YENİ
                    continue  # YENİ
                cift = frozenset((node_a, node_b))  # YENİ
                if cift in islenen_ciftler:  # YENİ
                    continue  # YENİ
                islenen_ciftler.add(cift)  # YENİ

                lat_b, lon_b = node_koordlari[node_b]  # YENİ
                mesafe_m = _haversine_m(lat_a, lon_a, lat_b, lon_b)  # YENİ
                if mesafe_m > max_metre:  # YENİ
                    continue  # YENİ

                # Zaten doğrudan bağlıysa yürüme kenarı gereksiz  # YENİ
                if (node_a, node_b) in baglantilar:  # YENİ
                    continue  # YENİ

                # YENİ: Boğaz engeli — stop_name bazlı kontrol
                meta_a = graf.node_meta(node_a) or {}  # YENİ
                meta_b = graf.node_meta(node_b) or {}  # YENİ
                name_a = meta_a.get("stop_name", "")  # YENİ
                name_b = meta_b.get("stop_name", "")  # YENİ
                if frozenset({name_a, name_b}) in KARA_ENGELI_CIFTLER:  # YENİ
                    continue  # YENİ

                mesafe_km = mesafe_m / 1000.0  # YENİ
                sure_dk = (mesafe_km / 5.0) * 60  # YENİ
                sure = max(1, int(round(sure_dk)))  # YENİ

                # İleri yön: a → b  # YENİ
                try:  # YENİ
                    graf.hat_ekle(node_a, node_b, "yürüme", "YURUME", sure, "#888888")  # YENİ
                    eklenen_kenar += 1  # YENİ
                except (ValueError, Exception):  # YENİ
                    pass  # YENİ

                # Ters yön: b → a  # YENİ
                try:  # YENİ
                    graf.hat_ekle(node_b, node_a, "yürüme", "YURUME", sure, "#888888")  # YENİ
                    eklenen_kenar += 1  # YENİ
                except (ValueError, Exception):  # YENİ
                    pass  # YENİ

    return eklenen_kenar  # YENİ
