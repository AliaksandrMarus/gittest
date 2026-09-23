package com.mywardrobe.app.domain.advisor

import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season

/**
 * Интерфейс намеренно не привязан к правило-based логике — реализация на
 * основе LLM сможет подставиться сюда же без изменений в вызывающем коде.
 */
interface OutfitAdvisor {
    suspend fun recommend(
        wardrobe: List<ClothingItem>,
        occasion: Occasion?,
        season: Season?,
        maxResults: Int = 5,
    ): List<OutfitSuggestion>
}
