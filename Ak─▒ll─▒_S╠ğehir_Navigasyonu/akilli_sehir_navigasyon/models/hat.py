# -*- coding: utf-8 -*-
"""
models/hat.py — Toplu taşıma kenarı (edge) veri sınıfı.

Matematiksel arka plan
──────────────────────
Bu sınıf G = (V, E, ψ, w) çoklu grafının E kümesinin bir elemanını temsil eder.

Multigraf tanımı:
    ψ : E → V × V  olay fonksiyonu ÖRTEN OLMAYABİLİR.
    Yani aynı (u,v) düğüm çiftine birden fazla kenar gönderilebilir.
    Örnek: Taksim–Şişhane arasında hem M2 Metro (id=1) hem 55T Otobüs (id=2)
    ayrı kenardır — ikisi de ψ(e) = (Taksim, Şişhane) üretiyor ama e₁ ≠ e₂.

Ağırlık fonksiyonu:
    w : E → ℝ⁺  (gerçek pozitif sayılar)
    `sure` alanı bu fonksiyonun dakika cinsinden değerini taşır.

Edge ID zorunluluğu:
    Aynı (u,v) uçlarına sahip iki kenarı ayırt etmenin TEK güvenilir yolu
    benzersiz bir tam sayı id'dir. BFS'te "bu kenardan geçtim mi?" sorusu
    O(1) ile bu id üzerinden cevaplanır; rota loglama da bu id'yi kullanır.

Simetrik depolama kararı:
    Graf yönsüz olduğundan aynı Hat nesnesi hem kaynak hem hedef düğümün
    komşuluk listesinde REF olarak tutulur (kopya değil). Bu nedenle sınıfa
    hem `baslangic` hem `hedef_istasyon` alanı eklendi; `diger_uc(kaynak)`
    metodu BFS traversalının doğru yönde ilerlemesini sağlar.

Performans hedefleri:
    __init__, to_dict : O(1)
    __eq__, __hash__  : O(1)
    diger_uc          : O(1)
"""

import re
from typing import Any


class Hat:
    """E kümesi elemanı — toplu taşıma ağında tek bir hat parçası (kenar)."""

    _sayac: int = 0  # Tüm Hat örnekleri için ortak monoton-artan ID sayacı

    def __init__(
        self,
        baslangic: str,
        hedef_istasyon: str,
        hat_tipi: str,
        hat_adi: str,
        sure: int,
        renk: str,
    ) -> None:
        """
        Hat nesnesini başlatır; tüm parametreleri doğrular.

        Args:
            baslangic       : Kenarın çıkış düğümü (kanonik yön).
            hedef_istasyon  : Kenarın varış düğümü; w(e) perspektifinde bitis.
            hat_tipi        : "Metro" | "Otobüs" | "Tramvay" | "Vapur"
            hat_adi         : "M2" | "55T" | "T1" | "M1A" | "Vapur" vb.
            sure            : Seyahat süresi (dakika), w(e) ∈ ℝ⁺.
            renk            : Hex renk kodu, ör. "#00A651".

        Raises:
            ValueError: Herhangi bir parametre kısıtı ihlal edilirse.

        Complexity: O(1)
        """
        # ── Doğrulamalar (sayaç artmadan önce) ──────────────────────────────
        if not baslangic or not baslangic.strip():
            raise ValueError("Başlangıç istasyonu boş olamaz")
        if not hedef_istasyon or not hedef_istasyon.strip():
            raise ValueError("Hedef istasyon boş olamaz")
        if not hat_tipi or not hat_tipi.strip():
            raise ValueError("Hat tipi boş olamaz")
        if not hat_adi or not hat_adi.strip():
            raise ValueError("Hat adı boş olamaz")
        if sure <= 0:
            raise ValueError(f"Süre pozitif olmalı, alındı: {sure}")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", renk):
            raise ValueError(
                f"Renk geçerli bir hex kodu olmalı (#RRGGBB formatında), alındı: '{renk}'"
            )

        # ── ID atama (doğrulama geçtikten sonra) ────────────────────────────
        Hat._sayac += 1
        self.id: int = Hat._sayac

        self.baslangic: str = baslangic.strip()
        self.hedef_istasyon: str = hedef_istasyon.strip()
        self.hat_tipi: str = hat_tipi.strip()
        self.hat_adi: str = hat_adi.strip()
        self.sure: int = sure
        self.renk: str = renk

    # ── Traversal yardımcısı ─────────────────────────────────────────────────

    def diger_uc(self, kaynak: str) -> str:
        """
        Verilen `kaynak` düğümünden bakıldığında bu kenarın diğer ucunu döndürür.

        Yönsüz BFS traversalı için kullanılır; aynı Hat nesnesi her iki
        düğümün listesinde tutulduğundan doğru hedefi bu metot belirler.

        Complexity: O(1)
        """
        return self.hedef_istasyon if kaynak == self.baslangic else self.baslangic

    # ── Temel Python protokolleri ────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Hat#{self.id}: {self.hat_adi} {self.hat_tipi} "
            f"{self.baslangic} → {self.hedef_istasyon} ({self.sure}dk)"
        )

    def __eq__(self, other: object) -> bool:
        """İki Hat id eşitse aynı kenardır. Complexity: O(1)."""
        if not isinstance(other, Hat):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Set ve dict anahtarı olarak kullanılabilir. Complexity: O(1)."""
        return hash(self.id)

    # ── Serileştirme ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """
        JSON-uyumlu sözlük üretir.

        Frontend REST API yanıtlarında doğrudan kullanılır; `ensure_ascii=False`
        ile Türkçe karakter desteği korunur.

        Complexity: O(1)
        """
        return {
            "id": self.id,
            "baslangic": self.baslangic,
            "bitis": self.hedef_istasyon,
            "hat_tipi": self.hat_tipi,
            "hat_adi": self.hat_adi,
            "sure": self.sure,
            "renk": self.renk,
        }
