package com.mywardrobe.app.data.local.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season

@Entity(tableName = "clothing_items")
data class ClothingItemEntity(
    @PrimaryKey val id: String,
    val imageUri: String,
    val cutoutImageUri: String?,
    val category: Category,
    val dominantColorArgb: Int,
    val seasons: Set<Season>,
    val occasions: Set<Occasion>,
    val createdAt: Long,
)
