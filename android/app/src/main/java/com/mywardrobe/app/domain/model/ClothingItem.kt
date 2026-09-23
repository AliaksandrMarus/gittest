package com.mywardrobe.app.domain.model

data class ClothingItem(
    val id: String,
    val imageUri: String,
    val cutoutImageUri: String?,
    val category: Category,
    val dominantColorArgb: Int,
    val seasons: Set<Season>,
    val occasions: Set<Occasion>,
    val createdAt: Long,
) {
    /** Фото для отображения: вырезанное на прозрачном фоне, пока оно не готово — исходное. */
    val displayImageUri: String get() = cutoutImageUri ?: imageUri
}
