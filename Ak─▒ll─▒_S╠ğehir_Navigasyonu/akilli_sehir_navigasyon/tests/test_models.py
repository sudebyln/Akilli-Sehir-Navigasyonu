# -*- coding: utf-8 -*-
"""
tests/test_models.py — Hat ve Graf sınıfları için assert-tabanlı testler.

Bağımlılık yok (pytest/unittest kullanılmıyor); standart kütüphane yeterli.
Her test fonksiyonu izoledir; başarısız test ValueError/AssertionError fırlatır.

Çalıştırma:
    python tests/test_models.py          (akilli_sehir_navigasyon/ dizininden)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.hat import Hat
from models.graf import Graf
from data.ornek_sehir import mini_istanbul_olustur


# ── Hat testleri ─────────────────────────────────────────────────────────────

def test_hat_olusturma_pozitif() -> None:
    """Geçerli parametrelerle Hat oluşur; id atanır; to_dict çalışır."""
    h = Hat("Taksim", "Şişhane", "Metro", "M2", 3, "#00A651")

    assert h.id > 0,                      "id pozitif tam sayı olmalı"
    assert h.baslangic == "Taksim",        "baslangic yanlış"
    assert h.hedef_istasyon == "Şişhane",  "hedef_istasyon yanlış"
    assert h.hat_tipi == "Metro",          "hat_tipi yanlış"
    assert h.hat_adi == "M2",              "hat_adi yanlış"
    assert h.sure == 3,                    "sure yanlış"
    assert h.renk == "#00A651",            "renk yanlış"

    d = h.to_dict()
    assert d["id"] == h.id,               "to_dict id eşleşmiyor"
    assert d["baslangic"] == "Taksim",    "to_dict baslangic yanlış"
    assert d["bitis"] == "Şişhane",       "to_dict bitis yanlış"
    assert d["hat_adi"] == "M2",          "to_dict hat_adi yanlış"
    assert d["sure"] == 3,                "to_dict sure yanlış"
    print("✓ test_hat_olusturma_pozitif geçti")


def test_hat_negatif_sure_hata_verir() -> None:
    """sure=-1 → ValueError fırlatılmalı."""
    try:
        Hat("Taksim", "Şişhane", "Metro", "M2", -1, "#00A651")
        assert False, "ValueError fırlamadı!"
    except ValueError:
        pass
    print("✓ test_hat_negatif_sure_hata_verir geçti")


def test_hat_sifir_sure_hata_verir() -> None:
    """sure=0 → ValueError fırlatılmalı (w(e) ∈ ℝ⁺, 0 dahil değil)."""
    try:
        Hat("Taksim", "Şişhane", "Metro", "M2", 0, "#00A651")
        assert False, "ValueError fırlamadı!"
    except ValueError:
        pass
    print("✓ test_hat_sifir_sure_hata_verir geçti")


def test_hat_gecersiz_renk_hata_verir() -> None:
    """Geçersiz hex kodu → ValueError fırlatılmalı."""
    for gecersiz in ("mavi", "#GGG", "#12345", "00A651", "#00A65X"):
        try:
            Hat("Taksim", "Şişhane", "Metro", "M2", 3, gecersiz)
            assert False, f"ValueError fırlamadı: '{gecersiz}'"
        except ValueError:
            pass
    print("✓ test_hat_gecersiz_renk_hata_verir geçti")


def test_hat_bos_alanlar_hata_verir() -> None:
    """Boş string alanlar ValueError fırlatmalı."""
    baz = ("Taksim", "Şişhane", "Metro", "M2", 3, "#00A651")
    boşluk_girdileri = [
        ("",       baz[1], baz[2], baz[3], baz[4], baz[5]),  # baslangic
        (baz[0],   "",     baz[2], baz[3], baz[4], baz[5]),  # hedef
        (baz[0], baz[1],   "",     baz[3], baz[4], baz[5]),  # hat_tipi
        (baz[0], baz[1],  baz[2],  "",     baz[4], baz[5]),  # hat_adi
    ]
    for girdi in boşluk_girdileri:
        try:
            Hat(*girdi)
            assert False, f"ValueError fırlamadı: {girdi}"
        except ValueError:
            pass
    print("✓ test_hat_bos_alanlar_hata_verir geçti")


def test_hat_id_artiyor() -> None:
    """Ardışık iki Hat, art arda id alır (monoton artış)."""
    h1 = Hat("A", "B", "Metro", "X1", 5, "#AABBCC")
    h2 = Hat("B", "C", "Otobüs", "X2", 10, "#112233")
    assert h2.id == h1.id + 1, f"Beklenen {h1.id + 1}, alınan {h2.id}"
    print("✓ test_hat_id_artiyor geçti")


def test_hat_esitlik_ve_hash() -> None:
    """id farklıysa eşit değil; aynı obje kendisiyle eşit; set desteği çalışır."""
    h1 = Hat("X", "Y", "Tramvay", "T1", 4, "#C8102E")
    h2 = Hat("X", "Y", "Tramvay", "T1", 4, "#C8102E")
    assert h1 != h2,              "Farklı id'ler eşit görünüyor"
    assert h1 == h1,              "Nesne kendisiyle eşit olmalı"
    assert hash(h1) == hash(h1),  "hash tutarlı olmalı"

    hat_seti = {h1, h2}
    assert len(hat_seti) == 2,    "set iki farklı hat içermeli"
    print("✓ test_hat_esitlik_ve_hash geçti")


def test_hat_diger_uc() -> None:
    """diger_uc(kaynak) doğru ucu döndürür."""
    h = Hat("Taksim", "Şişhane", "Metro", "M2", 3, "#00A651")
    assert h.diger_uc("Taksim")  == "Şişhane", "Taksim'den diğer uç Şişhane olmalı"
    assert h.diger_uc("Şişhane") == "Taksim",  "Şişhane'den diğer uç Taksim olmalı"
    print("✓ test_hat_diger_uc geçti")


# ── Graf testleri ─────────────────────────────────────────────────────────────

def test_graf_istasyon_ekleme() -> None:
    """|V| doğru artıyor; duplicate ekleme sessizce görmezden geliniyor."""
    g = Graf()
    g.istasyon_ekle("Taksim")
    g.istasyon_ekle("Şişhane")
    assert g.istasyon_sayisi() == 2, "İki farklı istasyon eklenmeli"

    g.istasyon_ekle("Taksim")        # Duplicate — idempotent
    assert g.istasyon_sayisi() == 2, "Duplicate istasyon sayıyı artırmamalı"
    print("✓ test_graf_istasyon_ekleme geçti")


def test_graf_bos_istasyon_hata_verir() -> None:
    """Boş string istasyon → ValueError."""
    g = Graf()
    try:
        g.istasyon_ekle("")
        assert False, "ValueError fırlamadı!"
    except ValueError:
        pass
    print("✓ test_graf_bos_istasyon_hata_verir geçti")


def test_graf_self_loop_yasak() -> None:
    """baslangic == bitis → ValueError."""
    g = Graf()
    try:
        g.hat_ekle("Taksim", "Taksim", "Metro", "M2", 3, "#00A651")
        assert False, "ValueError fırlamadı!"
    except ValueError:
        pass
    print("✓ test_graf_self_loop_yasak geçti")


def test_graf_duplicate_hat_yasak() -> None:
    """Aynı (baslangic, bitis, hat_adi) ikinci kez → ValueError."""
    g = Graf()
    g.hat_ekle("Taksim", "Şişhane", "Metro", "M2", 3, "#00A651")
    try:
        g.hat_ekle("Taksim", "Şişhane", "Metro", "M2", 5, "#00A651")
        assert False, "ValueError fırlamadı!"
    except ValueError:
        pass
    print("✓ test_graf_duplicate_hat_yasak geçti")


def test_graf_multigraf_kabul_eder() -> None:
    """Aynı (baslangic, bitis) — FARKLI hat_adi → kabul edilmeli (multigraf özü)."""
    g = Graf()
    h1 = g.hat_ekle("Taksim", "Şişhane", "Metro",  "M2",  3, "#00A651")
    h2 = g.hat_ekle("Taksim", "Şişhane", "Otobüs", "55T", 6, "#1976D2")

    assert h1.id != h2.id,          "Farklı kenarlar farklı id almalı"
    assert g.hat_sayisi() == 2,     "|E| = 2 olmalı"
    assert g.istasyon_sayisi() == 2, "|V| = 2 olmalı"
    print("✓ test_graf_multigraf_kabul_eder geçti")


def test_graf_komsuluk_simetrik() -> None:
    """Taksim→Şişhane eklendiğinde Şişhane'nin komşularında Taksim görünmeli."""
    g = Graf()
    g.hat_ekle("Taksim", "Şişhane", "Metro", "M2", 3, "#00A651")

    taksim_komsulari  = [h.diger_uc("Taksim")  for h in g.komsulari_getir("Taksim")]
    sisane_komsulari  = [h.diger_uc("Şişhane") for h in g.komsulari_getir("Şişhane")]

    assert "Şişhane" in taksim_komsulari, "Taksim'den Şişhane'ye yol yok"
    assert "Taksim"  in sisane_komsulari, "Şişhane'den Taksim'e yol yok (simetri bozuk)"
    print("✓ test_graf_komsuluk_simetrik geçti")


def test_graf_olmayan_istasyon_komsulari() -> None:
    """V'de bulunmayan istasyon → KeyError."""
    g = Graf()
    try:
        g.komsulari_getir("Mars")
        assert False, "KeyError fırlamadı!"
    except KeyError:
        pass
    print("✓ test_graf_olmayan_istasyon_komsulari geçti")


def test_to_dict_kenar_dedupe() -> None:
    """7 kenar varsa to_dict['hatlar'] tam 7 öğe içermeli (14 değil)."""
    g = mini_istanbul_olustur()
    d = g.to_dict()

    assert len(d["hatlar"]) == 7, (
        f"Beklenen 7 kenar, alınan {len(d['hatlar'])}"
    )
    idler = [h["id"] for h in d["hatlar"]]
    assert len(idler) == len(set(idler)), "Çıktıda duplicate kenar id'si var"
    print("✓ test_to_dict_kenar_dedupe geçti")


def test_mini_istanbul_butunlugu() -> None:
    """|V|=6 ve |E|=7 tam olarak doğrulanmalı."""
    g = mini_istanbul_olustur()
    assert g.istasyon_sayisi() == 6, (
        f"Beklenen |V|=6, alınan {g.istasyon_sayisi()}"
    )
    assert g.hat_sayisi() == 7, (
        f"Beklenen |E|=7, alınan {g.hat_sayisi()}"
    )
    print("✓ test_mini_istanbul_butunlugu geçti")


def test_to_dict_istasyonlar_sirali() -> None:
    """to_dict['istasyonlar'] alfabetik sıralı olmalı."""
    g = Graf()
    for ad in ["Zühtüpaşa", "Aksaray", "Bağcılar"]:
        g.istasyon_ekle(ad)
    istasyonlar = g.to_dict()["istasyonlar"]
    assert istasyonlar == sorted(istasyonlar), "İstasyon listesi sıralı değil"
    print("✓ test_to_dict_istasyonlar_sirali geçti")


# ── Test koşucusu ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_hat_olusturma_pozitif()
    test_hat_negatif_sure_hata_verir()
    test_hat_sifir_sure_hata_verir()
    test_hat_gecersiz_renk_hata_verir()
    test_hat_bos_alanlar_hata_verir()
    test_hat_id_artiyor()
    test_hat_esitlik_ve_hash()
    test_hat_diger_uc()
    test_graf_istasyon_ekleme()
    test_graf_bos_istasyon_hata_verir()
    test_graf_self_loop_yasak()
    test_graf_duplicate_hat_yasak()
    test_graf_multigraf_kabul_eder()
    test_graf_komsuluk_simetrik()
    test_graf_olmayan_istasyon_komsulari()
    test_to_dict_kenar_dedupe()
    test_mini_istanbul_butunlugu()
    test_to_dict_istasyonlar_sirali()

    print("\n✓ TÜM TESTLER GEÇTİ")
