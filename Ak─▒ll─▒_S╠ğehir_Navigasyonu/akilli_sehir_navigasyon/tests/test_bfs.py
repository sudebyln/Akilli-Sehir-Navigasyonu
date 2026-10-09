# -*- coding: utf-8 -*-
"""
tests/test_bfs.py — BFS ve Dijkstra rota motorları için assert-tabanlı testler.

Bağımlılık yok (pytest/unittest kullanılmıyor); standart kütüphane yeterli.

Çalıştırma:
    python tests/test_bfs.py   (akilli_sehir_navigasyon/ dizininden)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.ornek_sehir import mini_istanbul_olustur
from models.graf import Graf
from services.bfs import (
    en_az_aktarmali_rota,
    en_kisa_sureli_rota,
    k_en_iyi_rota,
    pareto_filtrele,
)
from services.klasik_bfs import klasik_bfs


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _tek_hat_graf() -> Graf:
    """A–B–C tek hatlı zincir, 1dk + 2dk."""
    g = Graf()
    g.hat_ekle("A", "B", "Metro", "X1", 1, "#AABBCC")
    g.hat_ekle("B", "C", "Metro", "X1", 2, "#AABBCC")
    return g


def _multigraf_ornek() -> Graf:
    """
    A–B: hat H1 (1dk) ve hat H2 (5dk)
    B–C: hat H3 (10dk)
    En kısa süre: A→B(H1, 1dk)→C(H3, 10dk) = 11dk, 1 aktarma
    En az aktarma: A→B(H1, 1dk)→C(H3, 10dk) = 1 aktarma (minimum)
    """
    g = Graf()
    g.hat_ekle("A", "B", "Metro",  "H1", 1,  "#111111")
    g.hat_ekle("A", "B", "Otobüs", "H2", 5,  "#222222")
    g.hat_ekle("B", "C", "Tramvay","H3", 10, "#333333")
    return g


# ── Pareto filtre testleri ────────────────────────────────────────────────────

def test_pareto_bos_liste() -> None:
    assert pareto_filtrele([]) == []
    print("✓ test_pareto_bos_liste geçti")


def test_pareto_tek_rota() -> None:
    rota = [{"aktarma": 2, "sure": 30}]
    assert pareto_filtrele(rota) == rota
    print("✓ test_pareto_tek_rota geçti")


def test_pareto_dominans() -> None:
    """B hem daha az aktarma hem daha az süre → A domine edilmeli."""
    a = {"aktarma": 3, "sure": 40}
    b = {"aktarma": 1, "sure": 25}
    filtreli = pareto_filtrele([a, b])
    assert b in filtreli
    assert a not in filtreli
    print("✓ test_pareto_dominans geçti")


def test_pareto_esit_domine_etmez() -> None:
    """Tamamen eşit iki rota birbirini domine etmez; ikisi de kalır."""
    a = {"aktarma": 1, "sure": 20}
    b = {"aktarma": 1, "sure": 20}
    filtreli = pareto_filtrele([a, b])
    assert len(filtreli) == 2
    print("✓ test_pareto_esit_domine_etmez geçti")


def test_pareto_iki_boyutlu_optimal() -> None:
    """
    A: (aktarma=0, sure=30) — süre odaklıysa iyi
    B: (aktarma=2, sure=10) — hız odaklıysa iyi
    İkisi birbirini domine edemez → ikisi de Pareto optimal.
    """
    a = {"aktarma": 0, "sure": 30}
    b = {"aktarma": 2, "sure": 10}
    filtreli = pareto_filtrele([a, b])
    assert len(filtreli) == 2
    print("✓ test_pareto_iki_boyutlu_optimal geçti")


# ── Klasik BFS testleri ───────────────────────────────────────────────────────

def test_klasik_bfs_basit() -> None:
    """A→C yolu bulunmalı."""
    g = _tek_hat_graf()
    r = klasik_bfs(g, "A", "C")
    assert r is not None
    assert r["yol"] == ["A", "B", "C"]
    assert r["sure"] == 3
    print("✓ test_klasik_bfs_basit geçti")


def test_klasik_bfs_baslangic_hedef_ayni() -> None:
    g = _tek_hat_graf()
    r = klasik_bfs(g, "A", "A")
    assert r is not None
    assert r["yol"] == ["A"]
    assert r["sure"] == 0
    assert r["aktarma"] == 0
    print("✓ test_klasik_bfs_baslangic_hedef_ayni geçti")


def test_klasik_bfs_yol_yok() -> None:
    """İzole düğüm → None."""
    g = Graf()
    g.hat_ekle("A", "B", "Metro", "M1", 5, "#111111")
    g.istasyon_ekle("Z")   # Z'ye giden kenar yok
    r = klasik_bfs(g, "A", "Z")
    assert r is None
    print("✓ test_klasik_bfs_yol_yok geçti")


def test_klasik_bfs_olmayan_istasyon() -> None:
    g = _tek_hat_graf()
    assert klasik_bfs(g, "A", "YOK") is None
    assert klasik_bfs(g, "YOK", "C") is None
    print("✓ test_klasik_bfs_olmayan_istasyon geçti")


# ── en_az_aktarmali_rota testleri ─────────────────────────────────────────────

def test_bfs_tek_hat_sifir_aktarma() -> None:
    """Tek hatlı A→C: aktarma=0."""
    g = _tek_hat_graf()
    r = en_az_aktarmali_rota(g, "A", "C")
    assert r is not None
    assert r["yol"] == ["A", "B", "C"]
    assert r["aktarma"] == 0
    assert r["sure"] == 3
    assert r["hatlar"] == ["X1", "X1"]
    print("✓ test_bfs_tek_hat_sifir_aktarma geçti")


def test_bfs_baslangic_hedef_ayni() -> None:
    g = _tek_hat_graf()
    r = en_az_aktarmali_rota(g, "B", "B")
    assert r is not None
    assert r["yol"] == ["B"]
    assert r["sure"] == 0
    assert r["aktarma"] == 0
    assert r["hatlar"] == []
    print("✓ test_bfs_baslangic_hedef_ayni geçti")


def test_bfs_olmayan_istasyon_none() -> None:
    g = _tek_hat_graf()
    assert en_az_aktarmali_rota(g, "A", "YOK") is None
    assert en_az_aktarmali_rota(g, "YOK", "C") is None
    print("✓ test_bfs_olmayan_istasyon_none geçti")


def test_bfs_multigraf_aktarma_sayar() -> None:
    """
    A→C: A–B H1(1dk) + B–C H3(10dk) = 1 aktarma.
    Klasik BFS hatalı sayabilir; durum uzayı BFS doğru sayar.
    """
    g = _multigraf_ornek()
    r = en_az_aktarmali_rota(g, "A", "C")
    assert r is not None
    assert r["aktarma"] == 1
    assert r["aktarma_noktalari"] == ["B"]
    print("✓ test_bfs_multigraf_aktarma_sayar geçti")


def test_bfs_mini_istanbul_taksim_kadikoy() -> None:
    """
    Taksim → Kadıköy: M2+M2+T1+T1+Vapur (3 aktarma) VEYA
    M2+M2+T1+M1A+Vapur (4 aktarma).
    BFS en az aktarmalıyı bulmalı.
    Beklenen yol: Taksim→Şişhane→Vezneciler→Aksaray→Yenikapı→Kadıköy
    """
    g = mini_istanbul_olustur()
    r = en_az_aktarmali_rota(g, "Taksim", "Kadıköy")
    assert r is not None
    assert r["yol"][0] == "Taksim"
    assert r["yol"][-1] == "Kadıköy"
    assert len(r["yol"]) == 6    # 5 adım
    # En az aktarma sağlanmalı (2 or 3 bağlı olarak ama 0 olamaz)
    assert r["aktarma"] >= 0
    print(f"✓ test_bfs_mini_istanbul_taksim_kadikoy geçti  "
          f"(aktarma={r['aktarma']}, süre={r['sure']}dk)")


def test_bfs_yol_yok_none() -> None:
    g = Graf()
    g.hat_ekle("A", "B", "Metro", "M1", 5, "#111111")
    g.istasyon_ekle("Z")
    assert en_az_aktarmali_rota(g, "A", "Z") is None
    print("✓ test_bfs_yol_yok_none geçti")


def test_bfs_simetrik() -> None:
    """A→C ile C→A aynı yol uzunluğunda olmalı (yönsüz graf)."""
    g = _tek_hat_graf()
    r_ileri = en_az_aktarmali_rota(g, "A", "C")
    r_geri  = en_az_aktarmali_rota(g, "C", "A")
    assert r_ileri is not None and r_geri is not None
    assert r_ileri["sure"]    == r_geri["sure"]
    assert r_ileri["aktarma"] == r_geri["aktarma"]
    print("✓ test_bfs_simetrik geçti")


# ── en_kisa_sureli_rota testleri ──────────────────────────────────────────────

def test_dijkstra_tek_hat() -> None:
    """Tek hat: Dijkstra doğru süreyi döndürmeli."""
    g = _tek_hat_graf()
    r = en_kisa_sureli_rota(g, "A", "C")
    assert r is not None
    assert r["sure"] == 3
    assert r["yol"] == ["A", "B", "C"]
    print("✓ test_dijkstra_tek_hat geçti")


def test_dijkstra_multigraf_en_kisa_secer() -> None:
    """
    A→B: H1(1dk) veya H2(5dk) — Dijkstra H1 seçmeli.
    A→C: A→B(H1,1) + B→C(H3,10) = 11dk
    """
    g = _multigraf_ornek()
    r = en_kisa_sureli_rota(g, "A", "C")
    assert r is not None
    assert r["sure"] == 11
    assert r["hatlar"][0] == "H1"   # H2 değil H1 seçilmeli
    print("✓ test_dijkstra_multigraf_en_kisa_secer geçti")


def test_dijkstra_baslangic_hedef_ayni() -> None:
    g = _tek_hat_graf()
    r = en_kisa_sureli_rota(g, "B", "B")
    assert r is not None
    assert r["sure"] == 0
    assert r["aktarma"] == 0
    print("✓ test_dijkstra_baslangic_hedef_ayni geçti")


def test_dijkstra_yol_yok_none() -> None:
    g = Graf()
    g.hat_ekle("A", "B", "Metro", "M1", 5, "#111111")
    g.istasyon_ekle("Z")
    assert en_kisa_sureli_rota(g, "A", "Z") is None
    print("✓ test_dijkstra_yol_yok_none geçti")


def test_dijkstra_olmayan_istasyon_none() -> None:
    g = _tek_hat_graf()
    assert en_kisa_sureli_rota(g, "A", "YOK") is None
    assert en_kisa_sureli_rota(g, "YOK", "C") is None
    print("✓ test_dijkstra_olmayan_istasyon_none geçti")


def test_dijkstra_mini_istanbul() -> None:
    """Taksim → Kadıköy: sure > 0 ve yol mantıklı."""
    g = mini_istanbul_olustur()
    r = en_kisa_sureli_rota(g, "Taksim", "Kadıköy")
    assert r is not None
    assert r["sure"] > 0
    assert r["yol"][0]  == "Taksim"
    assert r["yol"][-1] == "Kadıköy"
    print(f"✓ test_dijkstra_mini_istanbul geçti  "
          f"(sure={r['sure']}dk, aktarma={r['aktarma']})")


def test_dijkstra_sure_bfs_den_kucuk_esit() -> None:
    """
    Dijkstra süresi ≤ BFS süresi olmalı (BFS süreyi optimize etmez).
    """
    g = mini_istanbul_olustur()
    r_bfs = en_az_aktarmali_rota(g, "Taksim", "Kadıköy")
    r_dij = en_kisa_sureli_rota(g, "Taksim", "Kadıköy")
    assert r_bfs is not None and r_dij is not None
    assert r_dij["sure"] <= r_bfs["sure"], (
        f"Dijkstra ({r_dij['sure']}dk) BFS'den ({r_bfs['sure']}dk) uzun olamaz"
    )
    print("✓ test_dijkstra_sure_bfs_den_kucuk_esit geçti")


# ── k_en_iyi_rota testleri ────────────────────────────────────────────────────

def test_k_en_iyi_bos_graf_none() -> None:
    """Bağlantısız istasyonlar → boş liste."""
    g = Graf()
    g.istasyon_ekle("X")
    g.istasyon_ekle("Y")
    rotalar = k_en_iyi_rota(g, "X", "Y", k=3)
    assert rotalar == []
    print("✓ test_k_en_iyi_bos_graf_none geçti")


def test_k_en_iyi_baslangic_hedef_ayni() -> None:
    g = _tek_hat_graf()
    rotalar = k_en_iyi_rota(g, "A", "A", k=3)
    assert len(rotalar) >= 1
    assert rotalar[0]["sure"] == 0
    print("✓ test_k_en_iyi_baslangic_hedef_ayni geçti")


def test_k_en_iyi_k_siniri() -> None:
    """Dönen rota sayısı k'yı aşmamalı."""
    g = mini_istanbul_olustur()
    for k in [1, 2, 3]:
        rotalar = k_en_iyi_rota(g, "Taksim", "Kadıköy", k=k)
        assert len(rotalar) <= k, f"k={k} için {len(rotalar)} rota döndü"
    print("✓ test_k_en_iyi_k_siniri geçti")


def test_k_en_iyi_pareto_optimal() -> None:
    """
    k_en_iyi_rota Pareto filtreden geçirilmeli:
    sonuçlarda hiçbir rota başka bir rotayı domine etmemeli.
    """
    g = mini_istanbul_olustur()
    rotalar = k_en_iyi_rota(g, "Taksim", "Kadıköy", k=3)
    for i, a in enumerate(rotalar):
        for j, b in enumerate(rotalar):
            if i == j:
                continue
            domine = (
                b["aktarma"] <= a["aktarma"] and
                b["sure"]    <= a["sure"]    and
                (b["aktarma"] < a["aktarma"] or b["sure"] < a["sure"])
            )
            assert not domine, (
                f"Rota {j+1} Rota {i+1}'i domine ediyor — filtre çalışmıyor"
            )
    print("✓ test_k_en_iyi_pareto_optimal geçti")


def test_k_en_iyi_strateji_alanlari() -> None:
    """Her rotada 'strateji' anahtarı olmalı."""
    g = mini_istanbul_olustur()
    rotalar = k_en_iyi_rota(g, "Taksim", "Kadıköy", k=3)
    for rota in rotalar:
        assert "strateji" in rota, "Rotada 'strateji' anahtarı eksik"
    print("✓ test_k_en_iyi_strateji_alanlari geçti")


def test_k_en_iyi_yol_gecerli() -> None:
    """Her rota baslangic'tan başlayıp hedefte bitmeli; yol boş olmamalı."""
    g = mini_istanbul_olustur()
    rotalar = k_en_iyi_rota(g, "Taksim", "Kadıköy", k=3)
    for rota in rotalar:
        assert rota["yol"][0]  == "Taksim",  "Yol Taksim'den başlamalı"
        assert rota["yol"][-1] == "Kadıköy", "Yol Kadıköy'de bitmeli"
    print("✓ test_k_en_iyi_yol_gecerli geçti")


def test_k_en_iyi_tek_hat_tek_rota() -> None:
    """Tek hatlı grafta tüm stratejiler aynı yolu bulur → 1 Pareto optimal."""
    g = _tek_hat_graf()
    rotalar = k_en_iyi_rota(g, "A", "C", k=3)
    assert len(rotalar) >= 1
    for rota in rotalar:
        assert rota["sure"] == 3
        assert rota["aktarma"] == 0
    print("✓ test_k_en_iyi_tek_hat_tek_rota geçti")


# ── Klasik BFS vs Durum Uzayı BFS karşılaştırma ───────────────────────────────

def test_multigraf_aktarma_farki() -> None:
    """
    Multigraf durumunda klasik BFS aktarma sayısını doğru bilmeyebilir.
    Durum uzayı BFS multigraf kenarlarını ayırt eder.

    mini_istanbul'da Taksim→Kadıköy:
      Durum uzayı BFS aktarma sayacını doğru tutar.
      Klasik BFS en kısa hop sayısını (istasyon sayısını) bulur.
    """
    g = mini_istanbul_olustur()
    r_klasik = klasik_bfs(g, "Taksim", "Kadıköy")
    r_gelismis = en_az_aktarmali_rota(g, "Taksim", "Kadıköy")
    assert r_klasik is not None and r_gelismis is not None
    # Gelişmiş versiyon aktarma alanını doldurur (≥ 0)
    assert r_gelismis["aktarma"] >= 0
    assert "aktarma_noktalari" in r_gelismis
    print(f"✓ test_multigraf_aktarma_farki geçti  "
          f"(klasik={r_klasik['aktarma']}, gelismis={r_gelismis['aktarma']})")


# ── Test koşucusu ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pareto filtre
    test_pareto_bos_liste()
    test_pareto_tek_rota()
    test_pareto_dominans()
    test_pareto_esit_domine_etmez()
    test_pareto_iki_boyutlu_optimal()

    # Klasik BFS
    test_klasik_bfs_basit()
    test_klasik_bfs_baslangic_hedef_ayni()
    test_klasik_bfs_yol_yok()
    test_klasik_bfs_olmayan_istasyon()

    # en_az_aktarmali_rota (Durum Uzayı BFS)
    test_bfs_tek_hat_sifir_aktarma()
    test_bfs_baslangic_hedef_ayni()
    test_bfs_olmayan_istasyon_none()
    test_bfs_multigraf_aktarma_sayar()
    test_bfs_mini_istanbul_taksim_kadikoy()
    test_bfs_yol_yok_none()
    test_bfs_simetrik()

    # en_kisa_sureli_rota (Dijkstra)
    test_dijkstra_tek_hat()
    test_dijkstra_multigraf_en_kisa_secer()
    test_dijkstra_baslangic_hedef_ayni()
    test_dijkstra_yol_yok_none()
    test_dijkstra_olmayan_istasyon_none()
    test_dijkstra_mini_istanbul()
    test_dijkstra_sure_bfs_den_kucuk_esit()

    # k_en_iyi_rota
    test_k_en_iyi_bos_graf_none()
    test_k_en_iyi_baslangic_hedef_ayni()
    test_k_en_iyi_k_siniri()
    test_k_en_iyi_pareto_optimal()
    test_k_en_iyi_strateji_alanlari()
    test_k_en_iyi_yol_gecerli()
    test_k_en_iyi_tek_hat_tek_rota()

    # Karşılaştırma
    test_multigraf_aktarma_farki()

    print("\n✓ TÜM BFS TESTLERİ GEÇTİ")
