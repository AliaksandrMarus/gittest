package com.mywardrobe.app.data.repository

import com.mywardrobe.app.domain.model.Outfit
import com.mywardrobe.app.domain.model.OutfitSummary
import kotlinx.coroutines.flow.Flow

interface OutfitRepository {
    fun observeOutfitSummaries(): Flow<List<OutfitSummary>>
    suspend fun getOutfit(id: String): Outfit?
    suspend fun saveOutfit(outfit: Outfit)
    suspend fun deleteOutfit(id: String)
}
