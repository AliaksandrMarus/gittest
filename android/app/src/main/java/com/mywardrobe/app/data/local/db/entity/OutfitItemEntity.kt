package com.mywardrobe.app.data.local.db.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "outfit_items",
    foreignKeys = [
        ForeignKey(
            entity = OutfitEntity::class,
            parentColumns = ["id"],
            childColumns = ["outfitId"],
            onDelete = ForeignKey.CASCADE,
        ),
        ForeignKey(
            entity = ClothingItemEntity::class,
            parentColumns = ["id"],
            childColumns = ["itemId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("outfitId"), Index("itemId")],
)
data class OutfitItemEntity(
    @PrimaryKey val id: String,
    val outfitId: String,
    val itemId: String,
    val x: Float,
    val y: Float,
    val scale: Float,
    val rotationDegrees: Float,
    val zIndex: Int,
)
