package com.mywardrobe.app.data.repository

import com.mywardrobe.app.data.local.db.dao.ClothingItemDao
import com.mywardrobe.app.data.local.db.dao.OutfitDao
import com.mywardrobe.app.data.local.db.dao.OutfitItemDao
import com.mywardrobe.app.data.local.db.entity.OutfitEntity
import com.mywardrobe.app.data.local.db.entity.OutfitItemEntity
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Outfit
import com.mywardrobe.app.domain.model.OutfitItemPlacement
import com.mywardrobe.app.domain.model.OutfitSummary
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
        val placementEntities = outfitItemDao.getForOutfit(id)
        val items = clothingItemDao.getByIds(placementEntities.map { it.itemId })
            .associateBy { it.id }

        val placements = placementEntities.mapNotNull { placement ->
            val itemEntity = items[placement.itemId] ?: return@mapNotNull null
            OutfitItemPlacement(
                id = placement.id,
                item = ClothingItem(
                    id = itemEntity.id,
                    imageUri = itemEntity.imageUri,
                    cutoutImageUri = itemEntity.cutoutImageUri,
                    category = itemEntity.category,
                    dominantColorArgb = itemEntity.dominantColorArgb,
                    seasons = itemEntity.seasons,
                    occasions = itemEntity.occasions,
                    createdAt = itemEntity.createdAt,
                ),
                x = placement.x,
                y = placement.y,
                scale = placement.scale,
                rotationDegrees = placement.rotationDegrees,
                zIndex = placement.zIndex,
            )
        }

        return Outfit(
            id = outfitEntity.id,
            name = outfitEntity.name,
            occasion = outfitEntity.occasion,
            createdAt = outfitEntity.createdAt,
            placements = placements,
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
            outfit.placements.map { placement ->
                OutfitItemEntity(
                    id = placement.id,
                    outfitId = outfit.id,
                    itemId = placement.item.id,
                    x = placement.x,
                    y = placement.y,
                    scale = placement.scale,
                    rotationDegrees = placement.rotationDegrees,
                    zIndex = placement.zIndex,
                )
            },
        )
    }

    override suspend fun deleteOutfit(id: String) {
        outfitDao.getById(id)?.let { outfitDao.delete(it) }
    }
}
