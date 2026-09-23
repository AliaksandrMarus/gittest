package com.mywardrobe.app.ui.outfits

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.OutfitRepository
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.domain.advisor.OutfitAdvisor
import com.mywardrobe.app.domain.advisor.OutfitSuggestion
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Outfit
import com.mywardrobe.app.domain.model.OutfitItemPlacement
import com.mywardrobe.app.domain.model.OutfitSummary
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class OutfitsViewModel(
    private val outfitRepository: OutfitRepository,
    private val wardrobeRepository: WardrobeRepository,
    private val outfitAdvisor: OutfitAdvisor,
) : ViewModel() {

    val outfits: StateFlow<List<OutfitSummary>> = outfitRepository.observeOutfitSummaries()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _suggestions = MutableStateFlow<List<OutfitSuggestion>>(emptyList())
    val suggestions: StateFlow<List<OutfitSuggestion>> = _suggestions.asStateFlow()

    private val _isAdvising = MutableStateFlow(false)
    val isAdvising: StateFlow<Boolean> = _isAdvising.asStateFlow()

    fun requestSuggestions() {
        viewModelScope.launch {
            _isAdvising.value = true
            val wardrobe = wardrobeRepository.observeItems().first()
            _suggestions.value = outfitAdvisor.recommend(wardrobe, occasion = null, season = null)
            _isAdvising.value = false
        }
    }

    fun clearSuggestions() {
        _suggestions.value = emptyList()
    }

    /** Превращает подборку в новый образ с простой раскладкой по холсту, готовый к правке в конструкторе. */
    fun openSuggestionInBuilder(suggestion: OutfitSuggestion, onCreated: (String) -> Unit) {
        viewModelScope.launch {
            val id = UUID.randomUUID().toString()
            outfitRepository.saveOutfit(
                Outfit(
                    id = id,
                    name = "Подборка помощника",
                    occasion = null,
                    createdAt = System.currentTimeMillis(),
                    placements = autoArrange(suggestion.items),
                ),
            )
            clearSuggestions()
            onCreated(id)
        }
    }

    private fun autoArrange(items: List<ClothingItem>): List<OutfitItemPlacement> {
        val order = listOf(
            Category.OUTERWEAR,
            Category.TOP,
            Category.DRESS,
            Category.BOTTOM,
            Category.SHOES,
            Category.ACCESSORY,
        )
        val sorted = items.sortedBy { item -> order.indexOf(item.category).takeIf { it >= 0 } ?: order.size }
        val step = 1f / (sorted.size + 1)
        return sorted.mapIndexed { index, item ->
            OutfitItemPlacement(
                id = UUID.randomUUID().toString(),
                item = item,
                x = 0.5f,
                y = step * (index + 1),
                scale = 1f,
                rotationDegrees = 0f,
                zIndex = index,
            )
        }
    }
}
