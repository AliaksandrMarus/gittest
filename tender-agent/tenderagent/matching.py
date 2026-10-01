"""Сопоставление позиций тендера с прайсом. Работает полностью без интернета."""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from . import textnorm
from .config import OfferTerms
from .models import Match, Position, PriceItem


class PriceIndex:
    def __init__(self, items: list[PriceItem]):
        self.items = items
        self._keys = [textnorm.key(i.name + " " + i.code) for i in items]
        self._nums = [textnorm.numbers(i.name) for i in items]
        self._by_code = {i.code.strip().lower(): n for n, i in enumerate(items) if i.code.strip()}
        self._by_name = {i.name.strip().lower(): n for n, i in enumerate(items)}

    def __len__(self):
        return len(self.items)

    def find(self, item_ref: str) -> PriceItem | None:
        """Найти позицию прайса по коду или точному имени (для ручных сопоставлений)."""
        ref = (item_ref or "").strip().lower()
        n = self._by_code.get(ref, self._by_name.get(ref))
        return self.items[n] if n is not None else None

    def candidates(self, text: str, limit: int = 10) -> list[tuple[PriceItem, int]]:
        if not self.items:
            return []
        q = textnorm.key(text)
        if not q:
            return []
        qnums = textnorm.numbers(text)
        raw = process.extract(q, self._keys, scorer=fuzz.token_set_ratio, limit=max(limit * 4, 30),
                              processor=None)
        scored = []
        for _, base, n in raw:
            s = _combine(q, self._keys[n], base, qnums, self._nums[n])
            scored.append((self.items[n], s))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]


def _combine(q: str, k: str, base: float, qnums: set[str], inums: set[str]) -> int:
    # token_set_ratio даёт 100, если одно название целиком входит в другое —
    # смягчаем полнотой: «кабель» не должен на 100% совпасть с любым кабелем.
    sort_ratio = fuzz.token_sort_ratio(q, k)
    score = 0.65 * base + 0.35 * sort_ratio
    if qnums:
        hit = len(qnums & inums) / len(qnums)
        score *= 0.55 + 0.45 * hit
        if inums and not (qnums & inums):
            score *= 0.8
    elif inums:
        score *= 0.95
    return int(round(min(score, 100)))


@dataclass
class MatchSummary:
    total: int
    found: int
    percent: int
    our_sum: float          # без НДС, по включённым и найденным позициям
    limit_sum: float | None  # ориентировочная стоимость (с НДС) по тем же позициям
    estimate_ok: bool | None


def unit_price(item: PriceItem, terms: OfferTerms) -> float:
    price = item.price
    if terms.prices_include_vat:
        rate = item.vat_rate if item.vat_rate is not None else terms.vat_rate
        price = price / (1 + rate / 100)
    price *= 1 + terms.markup_percent / 100
    return round(price, 2)


def match_positions(positions: list[Position], index: PriceIndex, terms: OfferTerms,
                    min_score: int, manual: dict[str, str] | None = None) -> list[Match]:
    manual = manual or {}
    result = []
    for p in positions:
        ref = manual.get(textnorm.key(p.name))
        if ref == "-":
            result.append(Match(p, None, 0, manual=True, include=False))
            continue
        if ref:
            item = index.find(ref)
            if item:
                result.append(Match(p, item, 100, manual=True, price=unit_price(item, terms)))
                continue
        cands = index.candidates(p.name, limit=1)
        if cands and cands[0][1] >= min_score:
            item, s = cands[0]
            result.append(Match(p, item, s, price=unit_price(item, terms)))
        else:
            result.append(Match(p, None, cands[0][1] if cands else 0))
    return result


def summarize(matches: list[Match], estimate: float | None = None,
              vat_multiplier: float = 1.0) -> MatchSummary:
    """estimate и price_limit сравниваются с нашей суммой с НДС (vat_multiplier)."""
    total = len(matches)
    found = [m for m in matches if m.found and m.include]
    our = sum((m.price or 0) * m.qty for m in found)
    limits = [m.position.price_limit for m in found if m.position.price_limit]
    limit_sum = sum(limits) if limits and len(limits) == len(found) else None
    if limit_sum is None and estimate and total and len(found) == total:
        limit_sum = estimate
    ok = None if limit_sum is None else our * vat_multiplier <= limit_sum + 0.005
    return MatchSummary(total, len(found), int(round(100 * len(found) / total)) if total else 0,
                        round(our, 2), limit_sum, ok)
