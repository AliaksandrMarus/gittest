package com.mywardrobe.app.domain.advisor

import com.mywardrobe.app.domain.model.ClothingItem

data class OutfitSuggestion(
    val items: List<ClothingItem>,
    val score: Float,
    val reason: String,
)
