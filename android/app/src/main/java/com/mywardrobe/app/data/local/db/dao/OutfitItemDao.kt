package com.mywardrobe.app.data.local.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.mywardrobe.app.data.local.db.entity.OutfitItemEntity

@Dao
interface OutfitItemDao {
    @Query("SELECT * FROM outfit_items WHERE outfitId = :outfitId ORDER BY zIndex ASC")
    suspend fun getForOutfit(outfitId: String): List<OutfitItemEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<OutfitItemEntity>)

    @Query("DELETE FROM outfit_items WHERE outfitId = :outfitId")
    suspend fun deleteForOutfit(outfitId: String)
}
