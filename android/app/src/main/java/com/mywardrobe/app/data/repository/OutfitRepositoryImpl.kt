package com.mywardrobe.app.data.repository

import com.mywardrobe.app.data.local.db.dao.ClothingItemDao
import com.mywardrobe.app.data.local.db.dao.OutfitDao
import com.mywardrobe.app.data.local.db.dao.OutfitItemDao
import com.mywardrobe.app.data.local.db.entity.ClothingItemEntity
import com.mywardrobe.app.data.local.db.entity.OutfitEntity
import com.mywardrobe.app.data.local.db.entity.OutfitItemEntity
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Outfit
import com.mywardrobe.app.domain.model.OutfitSummary
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class OutfitRepositoryImpl(
    private val outfitDao: OutfitDao,
    private val outfitItemDao: OutfitItemDao,
    private val clothingItemDao: ClothingItemDao,
) : OutfitRepository {

    override fun observeOutfitSummaries(): Flow<List<OutfitSummary>> =
        outfitDao.observeAll().map { entities ->
            entities.map {
                OutfitSummary(id = it.id, name = it.name, occasion = it.occasion, createdAt = it.createdAt)
            }
        }

    override suspend fun getOutfit(id: String): Outfit? {
        val outfitEntity = outfitDao.getById(id) ?: return null
        val itemLinks = outfitItemDao.getForOutfit(id)
        val items = clothingItemDao.getByIds(itemLinks.map { it.itemId }).map { it.toDomain() }

        return Outfit(
            id = outfitEntity.id,
            name = outfitEntity.name,
            occasion = outfitEntity.occasion,
            createdAt = outfitEntity.createdAt,
            items = items,
        )
    }

    override suspend fun saveOutfit(outfit: Outfit) {
        outfitDao.upsert(
            OutfitEntity(
                id = outfit.id,
                name = outfit.name,
                occasion = outfit.occasion,
                createdAt = outfit.createdAt,
            ),
        )
        outfitItemDao.deleteForOutfit(outfit.id)
        outfitItemDao.upsertAll(
            outfit.items.map { item ->
                OutfitItemEntity(
                    id = UUID.randomUUID().toString(),
                    outfitId = outfit.id,
                    itemId = item.id,
                )
            },
        )
    }

    override suspend fun deleteOutfit(id: String) {
        outfitDao.getById(id)?.let { outfitDao.delete(it) }
    }
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
