package com.mywardrobe.app.ui.outfitdetail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.OutfitRepository
import com.mywardrobe.app.domain.model.Outfit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class OutfitDetailViewModel(
    private val outfitRepository: OutfitRepository,
    private val outfitId: String,
) : ViewModel() {

    private val _outfit = MutableStateFlow<Outfit?>(null)
    val outfit: StateFlow<Outfit?> = _outfit.asStateFlow()

    init {
        viewModelScope.launch { _outfit.value = outfitRepository.getOutfit(outfitId) }
    }

    fun delete(onDeleted: () -> Unit) {
        viewModelScope.launch {
            outfitRepository.deleteOutfit(outfitId)
            onDeleted()
        }
    }
}
