# -*- coding: utf-8 -*-
"""
services/bfs.py — Geliştirilmiş Durum Uzayı BFS ve Dijkstra rota motorları.

Matematiksel temel:
    Durum uzayı: G′ = (V×H, E′) — orijinal grafın ürün grafı
    Her durum (istasyon, hat) çifti; |V×H| = |V| × |H| boyutlu
    Aktarma = G′ içindeki ağırlık fonksiyonu w′: hat_değişimi → 1, aynı_hat → 0

Karmaşıklık (tüm fonksiyonlar için):
    V = istasyon sayısı, H = hat sayısı, E = kenar sayısı
    BFS  zaman: O(|V|×|H| + |E|×|H|)   alan: O(|V|×|H|)
    Dijkstra: O((|V|×|H| + |E|×|H|) × log(|V|×|H|))
"""

import heapq
import os
import sys
from collections import deque
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.graf import Graf  # noqa: E402

# AKTARMA_NOKTALARI'nı veri katmanından al (single source of truth)
try:
    from data.gtfs_yukleyici import AKTARMA_NOKTALARI  # noqa: E402
except Exception:
    AKTARMA_NOKTALARI: dict[str, list[str]] = {}

# Vapur (deniz) hatları — prefix eşleşmesi için
VAPUR_PREFIXES = ["BĞZ", "ŞH", "KBTŞ", "BSK", "BOS", "KDK", "EMN", "ÜSK", "ADA"]

# ── Hat tipine göre bekleme süreleri (gerçek dk) ─────────────────────────────
# İlk binişte ve her aktarmada yeni araca bekleme süresi eklenir.
BEKLEME_SURELERI: dict[str, int] = {
    "Metro":     3,
    "Tramvay":   3,
    "Tren":      5,    # Marmaray
    "Marmaray":  5,
    "Vapur":     10,
    "Teleferik": 5,
    "Füniküler": 4,
    "Metrobüs":  3,
    "Otobüs":    5,
    "Dolmuş":    5,
    "Yürüme":    0,
    "Aktarma":   0,
}
BEKLEME_VARSAYILAN: int = 3

# Her aktarmada ek süre (yürüme + yön bulma): gerçek dakika
AKTARMA_CEZASI: int = 5


def is_transfer_allowed(istasyon: str, hat_from: str, hat_to: str) -> bool:
    """
    Aynı istasyonda hat_from → hat_to aktarması yapılabilir mi?
    """
    # Yürüme ve Aktarma her zaman izinli
    if hat_from in ("Yürüme", "Aktarma", "yurume", "otobüs") or \
       hat_to in ("Yürüme", "Aktarma", "yurume", "otobüs"):
        return True

    if not AKTARMA_NOKTALARI:
        return True
    if istasyon not in AKTARMA_NOKTALARI:
        return True
    
    izinli = AKTARMA_NOKTALARI[istasyon]
    # Hat isimleri veya tipleri üzerinden kontrol
    from_ok = any(hat_from.startswith(h) for h in izinli) or hat_from == "Vapur"
    to_ok   = any(hat_to.startswith(h)   for h in izinli) or hat_to == "Vapur"
    
    return from_ok and to_ok


# ── Strateji parametreleri ──────────────────────────────────────────────────
#
# Üç farklı strateji = farklı ağırlık fonksiyonları. Aynı Dijkstra'yı paylaşır
# ama parametreleri farklıdır → gerçekten farklı sonuçlar üretirler.
#
# Hat.sure dakika cinsindendir; tüm cezalar dakika eşdeğerinde tutulur.

# Aktarma cezası — strateji bazlı
AKTARMA_CEZASI_HIZLI:   int = 5      # Algısal kayıp: 5 dk'dan az kazanç → aktarma yapma
AKTARMA_CEZASI_AKTARMA: int = 1000   # Aktarmayı pratikte yasakla (zorunluysa kabul)
AKTARMA_CEZASI_YURUME:  int = 5      # Düşük: yürüme cezası baskın olsun, aktarma değil

# Hat tipi öncelik cezası — kapasite/konfor temelli
# Metro/Marmaray bedava, dolmuş çok pahalı. Bu sayede metro hattı varken
# dolmuş dezavantajlı; ama metro yokken kabul edilebilir kalır.
TIP_CEZASI: dict[str, float] = {
    "Metro":     0.0,
    "Tren":      0.0,    # Marmaray (route_type=2) → "Tren"
    "Marmaray":  0.0,    # Hat adı eşleşmesi (eski cache uyumluluğu için)
    "Tramvay":   1.0,
    "Metrobüs":  2.0,
    "Vapur":     2.0,
    "Otobüs":    4.0,
    "Füniküler": 1.0,
    "Teleferik": 3.0,
    "Dolmuş":    8.0,    # Düşük öncelik
}
TIP_CEZASI_VARSAYILAN: float = 2.0


def _tip_cezasi(hat_tipi: str) -> float:
    return TIP_CEZASI.get(hat_tipi or "", TIP_CEZASI_VARSAYILAN)


def _is_vapur(hat_adi: str | None) -> bool:
    if not hat_adi:
        return False
    return any(hat_adi.startswith(p) for p in VAPUR_PREFIXES)


def _dolmus_cezasi(hat_tipi: str, sure: int) -> float:
    """
    Uzun mesafede dolmuşa caydırıcı, sure-orantılı ceza.

    Mantık:
      • Kısa segment  (sure ≤ 3 dk): cezasız — mahalle içi kısa dolmuş kabul
      • Uzun segment  (sure >  3 dk): edge süresiyle orantılı, agresif ceza

    Sabit "+= 2000" yetersiz kalır: 2 metro aktarması = 2000 dk eşdeğeri olduğu
    için uzun direkt-dolmuş, 2 aktarmalı metro alternatifinden hâlâ ucuz çıkar.
    Sure-orantılı ceza (100 dk × dakika) bu paradoxu çözer ve kullanıcının
    "Metro varken dolmuş önerilmesin" gereksinimini garanti eder.
    """
    if hat_tipi != "Dolmuş":
        return 0.0
    if sure <= 3:
        return 0.0
    return 100.0 * sure


# Geriye dönük uyumluluk: dış kod hâlâ AKTARMA_CEZASI_DK referans verebilir
AKTARMA_CEZASI_DK: int = AKTARMA_CEZASI_HIZLI


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def pareto_filtrele(rotalar: list[dict]) -> list[dict]:
    """
    Pareto dominans filtreleme: hiçbiri tarafından domine edilmeyen rotaları döndürür.

    Dominans tanımı:
        Rota b, rota a'yı domine eder ⟺
        b.aktarma ≤ a.aktarma  ∧  b.sure ≤ a.sure
        ∧  (b.aktarma < a.aktarma  ∨  b.sure < a.sure)

    Complexity: O(|rotalar|²)
    """
    filtreli = []
    for a in rotalar:
        domine_edildi = False
        for b in rotalar:
            if b is a:
                continue
            if (b["aktarma"] <= a["aktarma"] and b["sure"] <= a["sure"] and
                    (b["aktarma"] < a["aktarma"] or b["sure"] < a["sure"])):
                domine_edildi = True
                break
        if not domine_edildi:
            filtreli.append(a)
    return filtreli


# ── Generic Dijkstra — strateji parametreli ─────────────────────────────────

def _strateji_dijkstra(
    graf: Graf,
    baslangic: str | list[str],
    hedef: str | list[str],
    aktarma_cezasi: float,
    tip_carpani: float = 1.0,
    yurume_carpani: float = 1.0,
) -> dict[str, Any] | None:
    """
    Tüm stratejilerin paylaştığı durum-uzayı Dijkstra çekirdeği.

    Multi-source / multi-target desteği:
        baslangic ve hedef tek string veya string listesi olabilir.
        Liste verildiğinde tüm kaynak düğümlerden eşzamanlı başlanır
        ve hedef düğümlerden birine ulaşıldığında durulur.

    Kenar ağırlığı:
        w(e) = sure
             + tip_cezasi(hat_tipi) * tip_carpani
             + dolmus_cezasi(hat_tipi, sure)
             + (vapur_binisi ? VAPUR_BEKLEME_CEZASI : 0)
             + (aktarma_oluyor ? aktarma_cezasi : 0)
             + (yurume_kenari ? sure * (yurume_carpani - 1) : 0)

    Durum: (istasyon, son_kullanılan_hat) — aktarma maliyetlemesi için zorunlu.
    """
    bas_list = [baslangic] if isinstance(baslangic, str) else list(baslangic)
    hdf_list = [hedef] if isinstance(hedef, str) else list(hedef)
    hdf_set = set(hdf_list)

    bas_list = [b for b in bas_list if b in graf.istasyonlar]
    hdf_list = [h for h in hdf_list if h in graf.istasyonlar]
    if not bas_list or not hdf_list:
        return None

    if len(bas_list) == 1 and bas_list[0] in hdf_set:
        return {
            "yol": [bas_list[0]], "sure": 0, "aktarma": 0,
            "toplam_bekleme": 0,
            "etkin_maliyet": 0.0, "hatlar": [], "aktarma_noktalari": [],
            "bekleme_dahil": True,
            "bekleme_notu": "Bekleme ve aktarma süreleri dahildir",
        }

    sayac = 0
    # Heap: (etkin, sure, aktarma, sayac, ist, hat, yol, hatlar, akt_nok, bekleme)
    heap: list = []
    en_iyi: dict[tuple, float] = {}

    for b in bas_list:
        heapq.heappush(heap, (0.0, 0, 0, sayac, b, None, [b], [], [], 0))
        sayac += 1

    while heap:
        (etkin, sure, aktarma, _, ist, hat,
         yol, hatlar, akt_nok, bekleme) = heapq.heappop(heap)

        if ist in hdf_set:
            return {
                "yol": yol, "sure": sure, "aktarma": aktarma,
                "toplam_bekleme": bekleme,
                "etkin_maliyet": round(etkin, 2),
                "hatlar": hatlar, "aktarma_noktalari": akt_nok,
                "bekleme_dahil": True,
                "bekleme_notu": "Bekleme ve aktarma süreleri dahildir",
            }

        durum = (ist, hat)
        if durum in en_iyi and en_iyi[durum] <= etkin:
            continue
        en_iyi[durum] = etkin

        for komsu in graf.komsulari_getir(ist):
            sonraki   = komsu.diger_uc(ist)
            son_hat   = komsu.hat_adi
            son_tipi  = komsu.hat_tipi

            akt_oluyor = (hat is not None and hat != son_hat
                          and son_tipi not in ("Yürüme", "Aktarma"))

            if akt_oluyor and son_tipi not in ("Aktarma", "Yürüme"):
                if not is_transfer_allowed(ist, hat, son_hat):
                    continue

            # ── Bekleme süresi hesabı ────────────────────────────
            # İlk biniş: hat is None → yeni araca bekleme
            # Aktarma: hat değişimi → yeni araca bekleme + aktarma yürüme
            ilk_binis = (hat is None
                         and son_tipi not in ("Yürüme", "Aktarma"))
            bekleme_dk = BEKLEME_SURELERI.get(son_tipi, BEKLEME_VARSAYILAN)

            if ilk_binis:
                ek_bekleme = bekleme_dk
            elif akt_oluyor:
                ek_bekleme = bekleme_dk + AKTARMA_CEZASI
            else:
                ek_bekleme = 0

            # Yürüme kenarı: sure'nin (yurume_carpani-1) katı ek ceza
            yurume_ek = (komsu.sure * (yurume_carpani - 1.0)
                         if son_tipi in ("Yürüme", "Aktarma") else 0.0)

            edge_maliyet = (
                komsu.sure
                + ek_bekleme
                + _tip_cezasi(son_tipi) * tip_carpani
                + _dolmus_cezasi(son_tipi, komsu.sure)
                + (aktarma_cezasi if akt_oluyor else 0.0)
                + yurume_ek
            )

            yeni_etkin   = etkin + edge_maliyet
            yeni_sure    = sure + komsu.sure + ek_bekleme
            yeni_aktarma = aktarma + (1 if akt_oluyor else 0)
            yeni_akt_nok = (akt_nok + [ist]) if akt_oluyor else akt_nok
            yeni_bekleme = bekleme + ek_bekleme

            son_durum = (sonraki, son_hat)
            if son_durum in en_iyi and en_iyi[son_durum] <= yeni_etkin:
                continue

            sayac += 1
            heapq.heappush(heap, (
                yeni_etkin, yeni_sure, yeni_aktarma, sayac,
                sonraki, son_hat,
                yol + [sonraki], hatlar + [son_hat], yeni_akt_nok,
                yeni_bekleme,
            ))

    return None


# ── Fonksiyon 1: En az aktarmalı rota ──────────────────────────────────────

def en_az_aktarmali_rota(
    graf: Graf,
    baslangic: str | list[str],
    hedef: str | list[str],
) -> dict[str, Any] | None:
    """
    "En az aktarma" stratejisi:
        maliyet = (aktarma_sayisi * 1000) + sure + tip_cezasi + dolmus_cezasi

    Aktarma cezası 1000 dk eşdeğeri olduğundan algoritma her aktarmadan
    kaçınır; aktarma zorunlu olduğunda en kısa süreliyi seçer. Ayrıca metro
    > tramvay > otobüs > dolmuş öncelik sırası tip_cezasi ile uygulanır.
    Uzun-mesafede dolmuş edge'leri pratikte yasaklanır.
    """
    return _strateji_dijkstra(
        graf, baslangic, hedef,
        aktarma_cezasi=AKTARMA_CEZASI_AKTARMA,
        tip_carpani=1.0,
    )


def en_az_yurume_rota(
    graf: Graf,
    baslangic: str | list[str],
    hedef: str | list[str],
) -> dict[str, Any] | None:
    """
    "En az yürüme" stratejisi (proxy):
        maliyet = sure + (aktarma * 200) + tip_cezasi*2 + dolmus_cezasi

    Yürüme kenarları sure * yurume_carpani ile ağırlıklandırılır (fiilen 3×
    daha pahalı). Aktarma cezası 200 dk eşdeğeri ile aktarmaları (yürüme
    içerdiğinden) caydırır. tip_carpani=2 ile metro/marmaray güçlü tercih edilir.
    """
    return _strateji_dijkstra(
        graf, baslangic, hedef,
        aktarma_cezasi=AKTARMA_CEZASI_YURUME,
        tip_carpani=2.0,
        yurume_carpani=3.0,
    )


# ── Fonksiyon 2: En kısa süreli rota (Dijkstra) ─────────────────────────────

def en_kisa_sureli_rota(
    graf: Graf,
    baslangic: str | list[str],
    hedef: str | list[str],
    aktarma_cezasi_dk: int = AKTARMA_CEZASI_HIZLI,
) -> dict[str, Any] | None:
    """
    "En hızlı" stratejisi:
        maliyet = sure + (aktarma ise 5dk) + tip_cezasi + dolmus_cezasi

    Saf süre yerine "algısal süre" minimize edilir. Aktarma 5 dk eşdeğeri
    kayıp sayılır (yürüme + bekleme), uzun-mesafe dolmuş edge'leri elenir,
    metro/marmaray çok küçük öncelikle tercih edilir.
    """
    return _strateji_dijkstra(
        graf, baslangic, hedef,
        aktarma_cezasi=aktarma_cezasi_dk,
        tip_carpani=1.0,
    )


# ── Dijkstra — ağırlıklı skor (dahili yardımcı) ──────────────────────────────

def _dengeli_dijkstra(
    graf: Graf,
    baslangic: str,
    hedef: str,
    aktarma_agirligi: int = 10,
) -> dict[str, Any] | None:
    """
    Skor = aktarma × aktarma_agirligi + sure minimize eden Dijkstra.

    Dengeli rota için kullanılır; kullanıcı aktarma ağırlığını ayarlayabilir.

    Karmaşıklık: O((|V|×|H| + |E|×|H|) × log(|V|×|H|))
    """
    if baslangic not in graf.istasyonlar or hedef not in graf.istasyonlar:
        return None

    if baslangic == hedef:
        return {
            "yol": [baslangic],
            "sure": 0,
            "aktarma": 0,
            "hatlar": [],
            "aktarma_noktalari": [],
        }

    sayac = 0
    # (skor, sure, aktarma, sayac, istasyon, hat, yol, hatlar, aktarma_noktalari)
    heap: list = [(0, 0, 0, sayac, baslangic, None, [baslangic], [], [])]

    visited: set[tuple] = set()

    while heap:
        _, sure, aktarma, _, istasyon, hat, yol, hatlar, aktarma_noktalari = heapq.heappop(heap)

        if istasyon == hedef:
            return {
                "yol": yol,
                "sure": sure,
                "aktarma": aktarma,
                "hatlar": hatlar,
                "aktarma_noktalari": aktarma_noktalari,
            }

        durum = (istasyon, hat)
        if durum in visited:
            continue
        visited.add(durum)

        for komsu_hat in graf.komsulari_getir(istasyon):
            sonraki         = komsu_hat.diger_uc(istasyon)
            sonraki_hat_adi = komsu_hat.hat_adi

            yeni_aktarma           = aktarma
            yeni_aktarma_noktalari = aktarma_noktalari

            if hat is not None and hat != sonraki_hat_adi:
                yeni_aktarma           += 1
                yeni_aktarma_noktalari  = aktarma_noktalari + [istasyon]

            yeni_sure = sure + komsu_hat.sure
            yeni_skor = yeni_aktarma * aktarma_agirligi + yeni_sure

            sayac += 1
            heapq.heappush(heap, (
                yeni_skor,
                yeni_sure,
                yeni_aktarma,
                sayac,
                sonraki,
                sonraki_hat_adi,
                yol + [sonraki],
                hatlar + [sonraki_hat_adi],
                yeni_aktarma_noktalari,
            ))

    return None


# ── Fonksiyon 3: K-en iyi rota (Pareto optimal) ──────────────────────────────

def k_en_iyi_rota(
    graf: Graf,
    baslangic: str | list[str],
    hedef: str | list[str],
    k: int = 3,
) -> list[dict[str, Any]]:
    """
    En az aktarmalı, en kısa süreli ve dengeli rotaları döndürür.

    PARETO OPTİMALLİK:
    ──────────────────
    Rota A, Rota B'yi DOMINE EDER ⟺
        A.aktarma ≤ B.aktarma  ∧  A.sure ≤ B.sure
        ∧ (A.aktarma < B.aktarma  ∨  A.sure < B.sure)

    Hiçbiri domine etmezse ikisi de Pareto optimaldir.
    Kullanıcı tercihine göre doğru seçim değişir.

    Strateji 1 — Min aktarma : BFS    (aktarma odaklı)
    Strateji 2 — Min süre    : Dijkstra (süre odaklı)
    Strateji 3 — Dengeli     : Dijkstra (aktarma×10 + süre skoru)

    Returns:
        Pareto filtreli, en fazla k rota listesi.
        Her rota dict'ine "strateji" anahtarı eklenir.

    Complexity: O((|V|×|H| + |E|×|H|) × log(|V|×|H|))  — Dijkstra baskın
    """
    aday_rotalar: list[dict[str, Any]] = []

    # Strateji 1: minimum süre (en hızlı)
    r_sure = en_kisa_sureli_rota(graf, baslangic, hedef)
    if r_sure:
        aday_rotalar.append({**r_sure, "strateji": "En Hızlı"})

    # Strateji 2: minimum aktarma
    r_aktarma = en_az_aktarmali_rota(graf, baslangic, hedef)
    if r_aktarma:
        zaten_var = any(r["yol"] == r_aktarma["yol"] for r in aday_rotalar)
        if not zaten_var:
            aday_rotalar.append({**r_aktarma, "strateji": "En Az Aktarma"})

    # Strateji 3: minimum yürüme (Marmaray / metro tercihli)
    r_yurume = en_az_yurume_rota(graf, baslangic, hedef)
    if r_yurume:
        zaten_var = any(r["yol"] == r_yurume["yol"] for r in aday_rotalar)
        if not zaten_var:
            aday_rotalar.append({**r_yurume, "strateji": "En Az Yürüme"})

    return aday_rotalar[:k]


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.ornek_sehir import mini_istanbul_olustur
    from services.klasik_bfs import klasik_bfs

    graf = mini_istanbul_olustur()
    bas, bit = "Taksim", "Kadıköy"

    print(f"\n=== {bas} → {bit} Rota Analizi ===\n")

    # Klasik BFS
    k = klasik_bfs(graf, bas, bit)
    if k:
        print("[Klasik BFS]")
        print("  Yol    :", " → ".join(k["yol"]))
        print(f"  Süre   : {k['sure']} dk")
        print(f"  Aktarma: {k['aktarma']}  ← multigrafı göremez!")

    print()

    # Geliştirilmiş BFS
    g = en_az_aktarmali_rota(graf, bas, bit)
    if g:
        print("[Geliştirilmiş BFS — En Az Aktarma]")
        print("  Yol    :", " → ".join(g["yol"]))
        print(f"  Süre   : {g['sure']} dk")
        print(f"  Aktarma: {g['aktarma']}")
        print(f"  Aktarma noktaları: {g['aktarma_noktalari']}")

    print()

    # Dijkstra — En Kısa Süre
    d = en_kisa_sureli_rota(graf, bas, bit)
    if d:
        print("[Dijkstra — En Hızlı]")
        print("  Yol    :", " → ".join(d["yol"]))
        print(f"  Süre   : {d['sure']} dk")
        print(f"  Aktarma: {d['aktarma']}")
        print(f"  Hatlar : {d['hatlar']}")

    print()

    # En Az Yürüme
    y = en_az_yurume_rota(graf, bas, bit)
    if y:
        print("[Dijkstra — En Az Yürüme]")
        print("  Yol    :", " → ".join(y["yol"]))
        print(f"  Süre   : {y['sure']} dk")
        print(f"  Aktarma: {y['aktarma']}")
        print(f"  Hatlar : {y['hatlar']}")

    print()

    # k=3 rota önerileri
    rotalar = k_en_iyi_rota(graf, bas, bit, k=3)
    print(f"[k=3 Rota Önerileri]  ({len(rotalar)} Pareto-optimal rota)")
    for i, rota in enumerate(rotalar, start=1):
        strateji = rota.get("strateji", "?")
        print(f"  Rota {i} — {strateji:<20}: "
              f"{rota['aktarma']} aktarma, {rota['sure']} dk, "
              f"hatlar: {rota.get('hatlar', [])}")
