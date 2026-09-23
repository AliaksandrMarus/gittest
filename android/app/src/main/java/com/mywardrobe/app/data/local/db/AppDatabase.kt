package com.mywardrobe.app.data.local.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import com.mywardrobe.app.data.local.db.dao.ClothingItemDao
import com.mywardrobe.app.data.local.db.dao.OutfitDao
import com.mywardrobe.app.data.local.db.dao.OutfitItemDao
import com.mywardrobe.app.data.local.db.entity.ClothingItemEntity
import com.mywardrobe.app.data.local.db.entity.OutfitEntity
import com.mywardrobe.app.data.local.db.entity.OutfitItemEntity

@Database(
    entities = [ClothingItemEntity::class, OutfitEntity::class, OutfitItemEntity::class],
    version = 1,
    exportSchema = false,
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun clothingItemDao(): ClothingItemDao
    abstract fun outfitDao(): OutfitDao
    abstract fun outfitItemDao(): OutfitItemDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "mywardrobe.db",
                ).build().also { INSTANCE = it }
            }
    }
}
