package com.mywardrobe.app.data.local.db

import androidx.room.TypeConverter
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season

class Converters {
    @TypeConverter
    fun fromCategory(value: Category): String = value.name

    @TypeConverter
    fun toCategory(value: String): Category = Category.valueOf(value)

    @TypeConverter
    fun fromNullableOccasion(value: Occasion?): String? = value?.name

    @TypeConverter
    fun toNullableOccasion(value: String?): Occasion? = value?.let { Occasion.valueOf(it) }

    @TypeConverter
    fun fromSeasonSet(value: Set<Season>): String = value.joinToString(",") { it.name }

    @TypeConverter
    fun toSeasonSet(value: String): Set<Season> =
        if (value.isBlank()) emptySet() else value.split(",").map { Season.valueOf(it) }.toSet()

    @TypeConverter
    fun fromOccasionSet(value: Set<Occasion>): String = value.joinToString(",") { it.name }

    @TypeConverter
    fun toOccasionSet(value: String): Set<Occasion> =
        if (value.isBlank()) emptySet() else value.split(",").map { Occasion.valueOf(it) }.toSet()
}
