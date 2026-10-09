# -*- coding: utf-8 -*-
"""
data/ornek_sehir.py — Örnek İstanbul toplu taşıma multigrafı.

Renk paleti İBB (İstanbul Büyükşehir Belediyesi) kurumsal kimliğine uyumludur.
Web sitesi aşamasında bu sözlükler doğrudan CSS değişkenlerine veya
Tailwind konfigürasyonuna aktarılacak.
"""

import json
import os
import sys

# Paket kök dizinini sys.path'e ekle — hem doğrudan hem de modül olarak çalışır
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.graf import Graf  # noqa: E402

# ── İBB Renk Paleti ──────────────────────────────────────────────────────────

HAT_RENKLERI: dict[str, str] = {
    "M2":    "#00A651",   # M2 Metro — yeşil
    "55T":   "#1976D2",   # İBB otobüs mavisi
    "T1":    "#C8102E",   # T1 Tramvay — kırmızı
    "M1A":   "#9C27B0",   # M1A Metro — mor
    "Vapur": "#00ACC1",   # Deniz hattı — turkuaz
}

IBB_KIMLIK: dict[str, str] = {
    "kirmizi":      "#E30613",   # İBB ana kırmızısı — CTA butonları
    "lacivert":     "#1A4F8A",   # Header / banner arka planı
    "bogaz_mavisi": "#0079C2",   # İkincil aksesuar rengi
    "beyaz":        "#FFFFFF",
    "acik_gri":     "#F5F7FA",   # Sayfa arka planı
    "koyu_yazi":    "#1F2937",   # Ana metin
    "soluk_yazi":   "#6B7280",   # İkincil metin / placeholder
}

# ── Örnek Graf Fabrikası ─────────────────────────────────────────────────────


def mini_istanbul_olustur() -> Graf:
    """
    6 istasyonlu örnek toplu taşıma multigrafını kurar.

    V = {Taksim, Şişhane, Vezneciler, Aksaray, Yenikapı, Kadıköy}
    |E| = 7  (2 multigraf çifti dahil)

    Multigraf örnekleri:
        Taksim–Şişhane   : M2 Metro (3dk) VE 55T Otobüs (6dk)  → ψ#1
        Aksaray–Yenikapı : T1 Tramvay (3dk) VE M1A Metro (2dk) → ψ#2

    Returns:
        Tam olarak yapılandırılmış Graf nesnesi.
    """
    graf = Graf()

    # ── İstasyonlar (V kümesi) ───────────────────────────────────────────────
    for istasyon in [
        "Taksim", "Şişhane", "Vezneciler", "Aksaray", "Yenikapı", "Kadıköy",
        "Üsküdar", "Sirkeci",
    ]:
        graf.istasyon_ekle(istasyon)

    # ── Hatlar (E kümesi) ────────────────────────────────────────────────────

    # Avrupa yakası metro & tramvay
    graf.hat_ekle("Taksim",     "Şişhane",    "Metro",   "M2",    3,  HAT_RENKLERI["M2"])
    graf.hat_ekle("Taksim",     "Şişhane",    "Otobüs",  "55T",   6,  HAT_RENKLERI["55T"])
    graf.hat_ekle("Şişhane",    "Vezneciler", "Metro",   "M2",    4,  HAT_RENKLERI["M2"])
    graf.hat_ekle("Vezneciler", "Aksaray",    "Tramvay", "T1",    5,  HAT_RENKLERI["T1"])
    graf.hat_ekle("Aksaray",    "Yenikapı",   "Tramvay", "T1",    3,  HAT_RENKLERI["T1"])
    graf.hat_ekle("Aksaray",    "Yenikapı",   "Metro",   "M1A",   2,  HAT_RENKLERI["M1A"])

    # Vapur: Yenikapı → Kadıköy (20 dk, bekleme cezalı)
    graf.hat_ekle("Yenikapı",   "Kadıköy",    "Vapur",   "Vapur", 20, HAT_RENKLERI["Vapur"])

    # Marmaray: Sirkeci → Üsküdar (tünel, hızlı, aktarmasız boğaz geçişi)
    graf.hat_ekle("Yenikapı",   "Sirkeci",    "Tren",    "Marmaray", 3, "#F57C00")
    graf.hat_ekle("Sirkeci",    "Üsküdar",    "Tren",    "Marmaray", 4, "#F57C00")
    graf.hat_ekle("Üsküdar",    "Kadıköy",    "Metro",   "M5",       6, "#9C27B0")

    # Yürüme kenarları (aktarma bağlantıları)
    graf.hat_ekle("Şişhane",    "Sirkeci",    "Yürüme",  "Yürüme",   7, "#9E9E9E")

    return graf


# ── Demo çalıştırma ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    graf = mini_istanbul_olustur()

    # 1. Grafın özeti
    print(graf)
    print()

    # 2. Düğüm ve kenar sayıları
    print(f"  |V| = {graf.istasyon_sayisi()}  (istasyon sayısı)")
    print(f"  |E| = {graf.hat_sayisi()}  (hat/kenar sayısı)")
    print()

    # 3. Taksim'in komşuları — multigraf burada görünür
    print("  Taksim komşuları (iki ayrı hat — multigraf):")
    for hat in graf.komsulari_getir("Taksim"):
        komsu = hat.diger_uc("Taksim")
        print(f"    → {komsu:<18} [{hat.hat_adi} / {hat.hat_tipi}, {hat.sure}dk]  (id={hat.id})")
    print()

    # 4. Aksaray'ın komşuları — ikinci multigraf çifti + tramvay
    print("  Aksaray komşuları (iki ayrı hat + Vezneciler):")
    for hat in graf.komsulari_getir("Aksaray"):
        komsu = hat.diger_uc("Aksaray")
        print(f"    → {komsu:<18} [{hat.hat_adi} / {hat.hat_tipi}, {hat.sure}dk]  (id={hat.id})")
    print()

    # 5. to_dict() JSON çıktısı
    print("  Graf JSON çıktısı:")
    print(json.dumps(graf.to_dict(), ensure_ascii=False, indent=2))
