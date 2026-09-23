package com.mywardrobe.app.ui.additem

import android.graphics.Color
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.imaging.BackgroundRemover
import com.mywardrobe.app.data.imaging.ColorExtractor
import com.mywardrobe.app.data.imaging.ImageStorage
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AddItemViewModel(
    private val wardrobeRepository: WardrobeRepository,
    private val backgroundRemover: BackgroundRemover,
    private val imageStorage: ImageStorage,
) : ViewModel() {

    private val _step = MutableStateFlow<AddItemStep>(AddItemStep.Capture)
    val step: StateFlow<AddItemStep> = _step.asStateFlow()

    var selectedCategory by mutableStateOf(Category.TOP)
        private set
    var selectedSeasons by mutableStateOf(emptySet<Season>())
        private set
    var selectedOccasions by mutableStateOf(emptySet<Occasion>())
        private set

    fun onImageCaptured(uri: Uri) {
        _step.value = AddItemStep.Processing(uri)
        viewModelScope.launch {
            val file = imageStorage.fileForUri(uri)
            val bitmap = file?.let { imageStorage.loadOrientedBitmap(it) }
            if (file == null || bitmap == null) {
                _step.value = AddItemStep.TagPicker(uri, null, Color.GRAY)
                return@launch
            }

            val cutout = backgroundRemover.removeBackground(bitmap)
            val cutoutFile = imageStorage.cutoutFileFor(file)
            imageStorage.saveBitmapAsPng(cutout, cutoutFile)
            val dominantColor = ColorExtractor.extractDominantColor(cutout)

            _step.value = AddItemStep.TagPicker(
                originalUri = uri,
                cutoutUri = Uri.fromFile(cutoutFile),
                dominantColorArgb = dominantColor,
            )
        }
    }

    fun selectCategory(category: Category) {
        selectedCategory = category
    }

    fun toggleSeason(season: Season) {
        selectedSeasons = if (season in selectedSeasons) selectedSeasons - season else selectedSeasons + season
    }

    fun toggleOccasion(occasion: Occasion) {
        selectedOccasions =
            if (occasion in selectedOccasions) selectedOccasions - occasion else selectedOccasions + occasion
    }

    fun save(onSaved: () -> Unit) {
        val current = _step.value as? AddItemStep.TagPicker ?: return
        _step.value = AddItemStep.Saving
        viewModelScope.launch {
            wardrobeRepository.saveItem(
                ClothingItem(
                    id = UUID.randomUUID().toString(),
                    imageUri = current.originalUri.toString(),
                    cutoutImageUri = current.cutoutUri?.toString(),
                    category = selectedCategory,
                    dominantColorArgb = current.dominantColorArgb,
                    seasons = selectedSeasons,
                    occasions = selectedOccasions,
                    createdAt = System.currentTimeMillis(),
                ),
            )
            _step.value = AddItemStep.Done
            onSaved()
        }
    }
}
