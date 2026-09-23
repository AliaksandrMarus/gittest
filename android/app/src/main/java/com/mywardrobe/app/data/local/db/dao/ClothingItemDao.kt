package com.mywardrobe.app.data.local.db.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.mywardrobe.app.data.local.db.entity.ClothingItemEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ClothingItemDao {
    @Query("SELECT * FROM clothing_items ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<ClothingItemEntity>>

    @Query("SELECT * FROM clothing_items WHERE id = :id")
    suspend fun getById(id: String): ClothingItemEntity?

    @Query("SELECT * FROM clothing_items WHERE id IN (:ids)")
    suspend fun getByIds(ids: List<String>): List<ClothingItemEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(item: ClothingItemEntity)

    @Delete
    suspend fun delete(item: ClothingItemEntity)
}
