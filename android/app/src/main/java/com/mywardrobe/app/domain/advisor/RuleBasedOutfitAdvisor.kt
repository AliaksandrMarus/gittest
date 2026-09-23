package com.mywardrobe.app.domain.advisor

import android.graphics.Color
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season
import kotlin.math.abs

class RuleBasedOutfitAdvisor : OutfitAdvisor {

    override suspend fun recommend(
        wardrobe: List<ClothingItem>,
        occasion: Occasion?,
        season: Season?,
        maxResults: Int,
    ): List<OutfitSuggestion> {
        val byCategory = wardrobe.groupBy { it.category }
        val tops = byCategory[Category.TOP].orEmpty().take(MAX_PER_CATEGORY)
        val bottoms = byCategory[Category.BOTTOM].orEmpty().take(MAX_PER_CATEGORY)
        val dresses = byCategory[Category.DRESS].orEmpty().take(MAX_PER_CATEGORY)
        val shoes = byCategory[Category.SHOES].orEmpty().take(MAX_PER_CATEGORY)
        val outerwear = byCategory[Category.OUTERWEAR].orEmpty().firstOrNull()
        val accessory = byCategory[Category.ACCESSORY].orEmpty().firstOrNull()

        if (shoes.isEmpty()) return emptyList()

        // Валидная база образа — (верх + низ) или платье.
        val baseCombos = mutableListOf<List<ClothingItem>>()
        for (top in tops) {
            for (bottom in bottoms) {
                baseCombos += listOf(top, bottom)
            }
        }
        for (dress in dresses) {
            baseCombos += listOf(dress)
        }
        if (baseCombos.isEmpty()) return emptyList()

        val suggestions = mutableListOf<OutfitSuggestion>()
        for (base in baseCombos) {
            for (shoe in shoes) {
                var items = base + shoe
                outerwear?.let { items = items + it }
                accessory?.let { items = items + it }

                suggestions += OutfitSuggestion(
                    items = items,
                    score = score(items, occasion, season),
                    reason = reason(items, occasion, season),
                )
            }
        }

        return suggestions.sortedByDescending { it.score }.take(maxResults)
    }

    private fun score(items: List<ClothingItem>, occasion: Occasion?, season: Season?): Float {
        var score = 0f
        if (occasion != null) {
            score += items.count { occasion in it.occasions } * 2f
        }
        if (season != null) {
            score += items.count { matchesSeason(it, season) } * 1f
        }
        score += colorCompatibilityScore(items)
        return score
    }

    private fun matchesSeason(item: ClothingItem, season: Season): Boolean =
        season in item.seasons || Season.ALL_SEASON in item.seasons

    private fun reason(items: List<ClothingItem>, occasion: Occasion?, season: Season?): String {
        val parts = mutableListOf<String>()
        if (occasion != null && items.any { occasion in it.occasions }) {
            parts += "подходит для повода «${occasion.label.lowercase()}»"
        }
        if (season != null && items.any { matchesSeason(it, season) }) {
            parts += "по сезону «${season.label.lowercase()}»"
        }
        parts += "цвета хорошо сочетаются"
        return parts.joinToString(", ").replaceFirstChar { it.uppercase() }
    }

    /** Нейтральные цвета сочетаются с чем угодно; иначе — по расстоянию оттенков в HSV. */
    private fun colorCompatibilityScore(items: List<ClothingItem>): Float {
        var score = 0f
        for (i in items.indices) {
            for (j in i + 1 until items.size) {
                score += pairColorScore(items[i].dominantColorArgb, items[j].dominantColorArgb)
            }
        }
        return score
    }

    private fun pairColorScore(colorA: Int, colorB: Int): Float {
        if (isNeutral(colorA) || isNeutral(colorB)) return 1f
        val diff = hueDistance(hueOf(colorA), hueOf(colorB))
        return when {
            diff < 30f -> 0.8f
            diff in 150f..210f -> 1f
            else -> 0.2f
        }
    }

    private fun isNeutral(colorArgb: Int): Boolean {
        val hsv = FloatArray(3)
        Color.colorToHSV(colorArgb, hsv)
        return hsv[1] < 0.15f
    }

    private fun hueOf(colorArgb: Int): Float {
        val hsv = FloatArray(3)
        Color.colorToHSV(colorArgb, hsv)
        return hsv[0]
    }

    private fun hueDistance(a: Float, b: Float): Float {
        val diff = abs(a - b) % 360f
        return if (diff > 180f) 360f - diff else diff
    }

    private companion object {
        const val MAX_PER_CATEGORY = 5
    }
}
