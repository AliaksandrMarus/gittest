package com.mywardrobe.app.data.repository

import com.mywardrobe.app.data.local.db.dao.ClothingItemDao
import com.mywardrobe.app.data.local.db.entity.ClothingItemEntity
import com.mywardrobe.app.domain.model.ClothingItem
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class WardrobeRepositoryImpl(
    private val dao: ClothingItemDao,
) : WardrobeRepository {

    override fun observeItems(): Flow<List<ClothingItem>> =
        dao.observeAll().map { entities -> entities.map { it.toDomain() } }

    override suspend fun getItem(id: String): ClothingItem? = dao.getById(id)?.toDomain()

    override suspend fun getItems(ids: List<String>): List<ClothingItem> =
        dao.getByIds(ids).map { it.toDomain() }

    override suspend fun saveItem(item: ClothingItem) = dao.upsert(item.toEntity())

    override suspend fun deleteItem(item: ClothingItem) = dao.delete(item.toEntity())
}

private fun ClothingItemEntity.toDomain() = ClothingItem(
    id = id,
    imageUri = imageUri,
    cutoutImageUri = cutoutImageUri,
    category = category,
    dominantColorArgb = dominantColorArgb,
    seasons = seasons,
    occasions = occasions,
    createdAt = createdAt,
)

private fun ClothingItem.toEntity() = ClothingItemEntity(
    id = id,
    imageUri = imageUri,
    cutoutImageUri = cutoutImageUri,
    category = category,
    dominantColorArgb = dominantColorArgb,
    seasons = seasons,
    occasions = occasions,
    createdAt = createdAt,
)
