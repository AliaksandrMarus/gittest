package com.mywardrobe.app.domain.model

data class Outfit(
    val id: String,
    val name: String,
    val occasion: Occasion?,
    val createdAt: Long,
    val items: List<ClothingItem>,
)

/** Облегчённая карточка образа для списков — без загрузки всех вещей образа. */
data class OutfitSummary(
    val id: String,
    val name: String,
    val occasion: Occasion?,
    val createdAt: Long,
)
