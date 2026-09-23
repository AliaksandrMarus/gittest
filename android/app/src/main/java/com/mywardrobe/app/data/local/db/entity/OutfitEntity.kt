package com.mywardrobe.app.data.local.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.mywardrobe.app.domain.model.Occasion

@Entity(tableName = "outfits")
data class OutfitEntity(
    @PrimaryKey val id: String,
    val name: String,
    val occasion: Occasion?,
    val createdAt: Long,
)
