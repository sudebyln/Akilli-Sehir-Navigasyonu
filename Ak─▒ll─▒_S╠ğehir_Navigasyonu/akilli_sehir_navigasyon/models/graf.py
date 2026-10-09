# -*- coding: utf-8 -*-
"""
models/graf.py — Çoklu Graf (Multigraph) veri yapısı.

Matematiksel model
──────────────────
G = (V, E, ψ, w) dörtlüsü:

    V  : istasyon kümesi          → self.istasyonlar : set[str]
    E  : kenar kümesi             → Hat nesneleri
    ψ  : E → V×V  olay fonksiyonu → her Hat'ın (baslangic, hedef_istasyon) çifti
    w  : E → ℝ⁺   ağırlık fon.   → Hat.sure (dakika)

Multigraf özelliği:
    ψ örten OLMAYABILIR — aynı (u,v) çiftine birden fazla kenar gönderilebilir.
    Örnek: Taksim–Şişhane arası M2 Metro (id=1) ve 55T Otobüs (id=2) ayrı
    kenarlardır; hat_adi farklı olduğu sürece her ikisi de geçerlidir.

Komşuluk listesi vs. komşuluk matrisi
──────────────────────────────────────
    Matris  : O(|V|²) bellek — 500 istasyon = 250.000 hücre; seyrek grafta israf.
              Ayrıca (i,j) hücresi TEK değer alır → multigrafı temsil EDEMEZ.
    Liste   : O(|V|+|E|) bellek — gerçek ağlar için optimal.
              Paralel kenarlar list[Hat] içine kolayca eklenir.

Simetrik depolama ve ID-dedupe
────────────────────────────────
    hat_ekle(), tek Hat nesnesi yaratır ve AYNI REFERANSI hem baslangic hem
    bitis düğümünün listesine ekler.  to_dict() ID setini kullanarak her
    kenara yalnızca bir kez yer verir — alfabetik dedupe'dan daha güvenli
    çünkü aynı uçlar arasında farklı hat_adi'lı paralel kenarlar varsa
    yanlış birleşme olmaz.

Frontend köprüsü:
    to_dict() → JSON → REST API yanıtı → Harita bileşeni.
    Hiçbir metodda print/input yok; saf veri katmanı.
"""

from __future__ import annotations

from typing import Any

from models.hat import Hat


class Graf:
    """
    G = (V, E, ψ, w) çoklu grafı — komşuluk listesi temsili.

    Tüm metodlar Türkçe isimlendirilmiştir; docstring'ler Big-O notasyonu içerir.
    """

    def __init__(self) -> None:
        self.istasyonlar: set[str] = set()
        self.komsuluk: dict[str, list[Hat]] = {}
        self._node_meta: dict[str, dict] = {}  # YENİ

    # ── Düğüm işlemleri ──────────────────────────────────────────────────────

    def istasyon_ekle(self, ad: str, metadata: dict | None = None) -> None:  # YENİ: metadata parametresi
        """
        V ∪ {ad} — istasyonu grafa ekler.

        Idempotent: zaten var olan istasyonu tekrar eklemek sessizce geçer;
        set zaten deduplikasyon sağlar.

        Raises:
            ValueError: ad boş string veya yalnızca boşluktan oluşuyorsa.

        Complexity: O(1) amortized
        """
        if not ad or not ad.strip():
            raise ValueError("İstasyon adı boş olamaz")
        ad = ad.strip()
        if ad not in self.istasyonlar:
            self.istasyonlar.add(ad)
            self.komsuluk[ad] = []
        if metadata is not None:  # YENİ
            self._node_meta[ad] = metadata  # YENİ

    # ── Kenar işlemleri ──────────────────────────────────────────────────────

    def hat_ekle(
        self,
        baslangic: str,
        bitis: str,
        hat_tipi: str,
        hat_adi: str,
        sure: int,
        renk: str,
    ) -> Hat:
        """
        E ∪ {e} — yeni kenarı grafa ekler; simetrik olarak iki düğüme kaydeder.

        Multigraf desteği:
            Aynı (baslangic, bitis) çiftine FARKLI hat_adi ile birden fazla
            kenar eklenebilir — bu projenin temel özelliğidir.
            Aynı (baslangic, bitis, hat_adi) üçlüsü ikinci kez eklenemez.

        Otomatik düğüm ekleme:
            baslangic veya bitis henüz V'de yoksa istasyon_ekle() ile eklenir;
            API çağrısını basitleştirir.

        Returns:
            Oluşturulan Hat nesnesi — loglama ve test kolaylığı için.

        Raises:
            ValueError: self-loop, negatif/sıfır süre, veya duplicate hat.

        Complexity: O(degree(baslangic)) — duplicate tarama
        """
        if baslangic == bitis:
            raise ValueError(
                f"Self-loop'a izin verilmiyor: '{baslangic}' → '{bitis}'"
            )
        if sure <= 0:
            raise ValueError(f"Süre pozitif olmalı, alındı: {sure}")

        self.istasyon_ekle(baslangic)
        self.istasyon_ekle(bitis)

        # Duplicate kontrol: aynı (baslangic, bitis, hat_adi) yasak
        # Farklı hat_adi → multigraf kenarı → geçerli
        for mevcut in self.komsuluk[baslangic]:
            if mevcut.diger_uc(baslangic) == bitis and mevcut.hat_adi == hat_adi:
                raise ValueError(
                    f"'{hat_adi}' hattı '{baslangic}'–'{bitis}' arasında zaten tanımlı"
                )

        hat = Hat(baslangic, bitis, hat_tipi, hat_adi, sure, renk)
        # Aynı nesne referansı her iki listede — bellek tasarrufu + ID-dedupe
        self.komsuluk[baslangic].append(hat)
        self.komsuluk[bitis].append(hat)
        return hat

    # ── Sorgu metodları ──────────────────────────────────────────────────────

    def komsulari_getir(self, istasyon: str) -> list[Hat]:
        """
        N(v) — v düğümünün komşuluk listesini (Hat nesneleri) döndürür.

        Dönen liste bir kopyadır; dışarıdan değiştirilmesi iç yapıyı etkilemez.
        Her Hat için `hat.diger_uc(istasyon)` çağrısı gerçek komşuyu verir.

        Raises:
            KeyError: istasyon V kümesinde yoksa.

        Complexity: O(1) lookup + O(degree(v)) kopya
        """
        if istasyon not in self.istasyonlar:
            raise KeyError(f"İstasyon bulunamadı: '{istasyon}'")
        return list(self.komsuluk[istasyon])

    def istasyon_sayisi(self) -> int:
        """
        |V| — Grafın düğüm sayısı.

        Complexity: O(1)
        """
        return len(self.istasyonlar)

    def hat_sayisi(self) -> int:
        """
        |E| — Benzersiz kenar sayısı.

        Her Hat iki komşuluk listesinde bulunduğundan ID-dedupe uygulanır.

        Complexity: O(|V| + |E|)
        """
        gorulmus: set[int] = set()
        for hatlar in self.komsuluk.values():
            for hat in hatlar:
                gorulmus.add(hat.id)
        return len(gorulmus)

    def node_koord(self, node_id: str) -> tuple[float, float] | None:  # YENİ
        """node_id için (lat, lon) döndürür; metadata yoksa None."""  # YENİ
        meta = self._node_meta.get(node_id)  # YENİ
        if meta:  # YENİ
            lat = meta.get("lat") or meta.get("stop_lat")  # YENİ
            lon = meta.get("lon") or meta.get("stop_lon")  # YENİ
            if lat is not None and lon is not None:  # YENİ
                return (lat, lon)  # YENİ
        return None  # YENİ

    def node_meta(self, node_id: str) -> dict | None:  # YENİ
        """node_id için metadata dict döndürür; yoksa None."""  # YENİ
        return self._node_meta.get(node_id)  # YENİ

    # ── Serileştirme ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """
        JSON-uyumlu sözlük üretir — frontend REST köprüsü.

        Kenar dedupe:
            Her Hat nesnesi aynı id ile iki listede yer alır. Görülmüş ID'ler
            set'te takip edilip atlanarak her kenar çıktıda yalnızca bir kez
            yer alır. Bu yaklaşım alfabetik sıralama dedupesinden daha güvenli:
            aynı uçlar arasında farklı ID'li paralel kenarlar yanlış birleşmez.

        Çıktı formatı:
            {
              "istasyonlar": ["Aksaray", "Kadıköy", ...],   # sıralı
              "hatlar": [
                {"id": 1, "baslangic": "Taksim", "bitis": "Şişhane",
                 "hat_tipi": "Metro", "hat_adi": "M2", "sure": 3,
                 "renk": "#00A651"},
                ...
              ]
            }

        Complexity: O(|V| + |E|)
        """
        gorulmus_idler: set[int] = set()
        hatlar_listesi: list[dict[str, Any]] = []

        for hatlar in self.komsuluk.values():
            for hat in hatlar:
                if hat.id not in gorulmus_idler:
                    gorulmus_idler.add(hat.id)
                    hatlar_listesi.append(hat.to_dict())

        return {
            "istasyonlar": sorted(self.istasyonlar),
            "hatlar": hatlar_listesi,
        }

    # ── İnsan-okunabilir çıktı ───────────────────────────────────────────────

    def __str__(self) -> str:
        """
        Grafın komşuluk listesini formatlanmış metin olarak döndürür.

        Complexity: O(|V| + |E|)
        """
        satirlar = [
            "╔══════════════════════════════════════════════╗",
            "║      Akıllı Şehir Navigasyon Grafı           ║",
            "╚══════════════════════════════════════════════╝",
            f"  İstasyon sayısı  |V| = {self.istasyon_sayisi()}",
            f"  Hat (kenar) say. |E| = {self.hat_sayisi()}",
            "",
            "  Komşuluk Listesi:",
            "  " + "─" * 54,
        ]

        for istasyon in sorted(self.istasyonlar):
            hatlar = self.komsuluk[istasyon]
            if hatlar:
                komsu_parcalari = [
                    f"{hat.diger_uc(istasyon)} "
                    f"[{hat.hat_adi}/{hat.hat_tipi}, {hat.sure}dk]"
                    for hat in hatlar
                ]
                komsu_str = " | ".join(komsu_parcalari)
            else:
                komsu_str = "—"
            satirlar.append(f"  {istasyon:<18} →  {komsu_str}")

        return "\n".join(satirlar)
