package com.mywardrobe.app.data.local.db.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.mywardrobe.app.data.local.db.entity.OutfitEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface OutfitDao {
    @Query("SELECT * FROM outfits ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<OutfitEntity>>

    @Query("SELECT * FROM outfits WHERE id = :id")
    suspend fun getById(id: String): OutfitEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(outfit: OutfitEntity)

    @Delete
    suspend fun delete(outfit: OutfitEntity)
}
