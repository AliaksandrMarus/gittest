package com.mywardrobe.app.ui.wardrobe

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class WardrobeViewModel(repository: WardrobeRepository) : ViewModel() {

    val items: StateFlow<List<ClothingItem>> = repository.observeItems()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    var selectedCategory by mutableStateOf<Category?>(null)
        private set

    fun selectCategory(category: Category?) {
        selectedCategory = category
    }
}
