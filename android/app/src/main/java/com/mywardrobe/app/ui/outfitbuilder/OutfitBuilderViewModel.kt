package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.OutfitRepository
import com.mywardrobe.app.data.repository.ProfileRepository
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Outfit
import com.mywardrobe.app.domain.model.OutfitItemPlacement
import java.util.UUID
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class OutfitBuilderViewModel(
    private val outfitRepository: OutfitRepository,
    wardrobeRepository: WardrobeRepository,
    profileRepository: ProfileRepository,
    private val outfitId: String?,
) : ViewModel() {

    val profilePhotoUri: StateFlow<String?> = profileRepository.observeProfilePhotoUri()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val wardrobeItems: StateFlow<List<ClothingItem>> = wardrobeRepository.observeItems()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    var placements by mutableStateOf<List<OutfitItemPlacement>>(emptyList())
        private set

    var outfitName by mutableStateOf("")
        private set

    var occasion by mutableStateOf<Occasion?>(null)
        private set

    private var createdAt = System.currentTimeMillis()

    init {
        val id = outfitId
        if (id != null) {
            viewModelScope.launch {
                outfitRepository.getOutfit(id)?.let { outfit ->
                    placements = outfit.placements
                    outfitName = outfit.name
                    occasion = outfit.occasion
                    createdAt = outfit.createdAt
                }
            }
        }
    }

    fun updateOutfitName(name: String) {
        outfitName = name
    }

    fun updateOccasion(value: Occasion?) {
        occasion = value
    }

    fun addItem(item: ClothingItem) {
        val nextZIndex = (placements.maxOfOrNull { it.zIndex } ?: -1) + 1
        placements = placements + OutfitItemPlacement(
            id = UUID.randomUUID().toString(),
            item = item,
            x = 0.5f,
            y = 0.5f,
            scale = 1f,
            rotationDegrees = 0f,
            zIndex = nextZIndex,
        )
    }

    fun updatePlacement(id: String, dx: Float, dy: Float, scaleDelta: Float, rotationDelta: Float) {
        placements = placements.map { placement ->
            if (placement.id != id) return@map placement
            placement.copy(
                x = (placement.x + dx).coerceIn(0f, 1f),
                y = (placement.y + dy).coerceIn(0f, 1f),
                scale = (placement.scale * scaleDelta).coerceIn(0.3f, 3f),
                rotationDegrees = placement.rotationDegrees + rotationDelta,
            )
        }
    }

    fun removePlacement(id: String) {
        placements = placements.filter { it.id != id }
    }

    fun save(onSaved: (String) -> Unit) {
        viewModelScope.launch {
            val id = outfitId ?: UUID.randomUUID().toString()
            outfitRepository.saveOutfit(
                Outfit(
                    id = id,
                    name = outfitName.ifBlank { "Образ" },
                    occasion = occasion,
                    createdAt = createdAt,
                    placements = placements,
                ),
            )
            onSaved(id)
        }
    }
}
