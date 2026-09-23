package com.mywardrobe.app.data.repository

import com.mywardrobe.app.domain.model.ClothingItem
import kotlinx.coroutines.flow.Flow

interface WardrobeRepository {
    fun observeItems(): Flow<List<ClothingItem>>
    suspend fun getItem(id: String): ClothingItem?
    suspend fun getItems(ids: List<String>): List<ClothingItem>
    suspend fun saveItem(item: ClothingItem)
    suspend fun deleteItem(item: ClothingItem)
}
