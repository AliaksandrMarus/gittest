package com.mywardrobe.app.domain.model

data class Outfit(
    val id: String,
    val name: String,
    val occasion: Occasion?,
    val createdAt: Long,
    val placements: List<OutfitItemPlacement>,
)

/** Облегчённая карточка образа для списков — без загрузки всех размещённых вещей. */
data class OutfitSummary(
    val id: String,
    val name: String,
    val occasion: Occasion?,
    val createdAt: Long,
)

data class OutfitItemPlacement(
    val id: String,
    val item: ClothingItem,
    val x: Float,
    val y: Float,
    val scale: Float,
    val rotationDegrees: Float,
    val zIndex: Int,
)
