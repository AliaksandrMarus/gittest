package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.OutfitRepository
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Outfit
import java.util.UUID
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class OutfitBuilderViewModel(
    private val outfitRepository: OutfitRepository,
    wardrobeRepository: WardrobeRepository,
    private val outfitId: String?,
) : ViewModel() {

    val wardrobeItems: StateFlow<List<ClothingItem>> = wardrobeRepository.observeItems()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    var outfitName by mutableStateOf("")
        private set
    var occasion by mutableStateOf<Occasion?>(null)
        private set

    var outerwear by mutableStateOf<ClothingItem?>(null)
        private set
    var top by mutableStateOf<ClothingItem?>(null)
        private set
    var bottom by mutableStateOf<ClothingItem?>(null)
        private set
    var dress by mutableStateOf<ClothingItem?>(null)
        private set
    var shoes by mutableStateOf<ClothingItem?>(null)
        private set
    var accessory by mutableStateOf<ClothingItem?>(null)
        private set

    /** Живое превью коллажа из уже выбранных слотов. */
    val previewItems: List<ClothingItem>
        get() = listOfNotNull(outerwear, dress, top, bottom, shoes, accessory)

    private var createdAt = System.currentTimeMillis()

    init {
        val id = outfitId
        if (id != null) {
            viewModelScope.launch {
                outfitRepository.getOutfit(id)?.let { outfit ->
                    outfitName = outfit.name
                    occasion = outfit.occasion
                    createdAt = outfit.createdAt
                    outfit.items.forEach { assignToSlot(it, it.category) }
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

    /** Тап по вещи в её категории — выбрать или снять; платье и верх/низ взаимоисключающие. */
    fun selectItem(item: ClothingItem) {
        val alreadySelected = when (item.category) {
            Category.OUTERWEAR -> outerwear?.id == item.id
            Category.TOP -> top?.id == item.id
            Category.BOTTOM -> bottom?.id == item.id
            Category.DRESS -> dress?.id == item.id
            Category.SHOES -> shoes?.id == item.id
            Category.ACCESSORY -> accessory?.id == item.id
        }
        assignToSlot(if (alreadySelected) null else item, item.category)
    }

    private fun assignToSlot(item: ClothingItem?, category: Category) {
        when (category) {
            Category.OUTERWEAR -> outerwear = item
            Category.TOP -> {
                top = item
                if (item != null) dress = null
            }
            Category.BOTTOM -> {
                bottom = item
                if (item != null) dress = null
            }
            Category.DRESS -> {
                dress = item
                if (item != null) {
                    top = null
                    bottom = null
                }
            }
            Category.SHOES -> shoes = item
            Category.ACCESSORY -> accessory = item
        }
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
                    items = previewItems,
                ),
            )
            onSaved(id)
        }
    }
}
