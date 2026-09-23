package com.mywardrobe.app.ui.additem

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.Occasion
import com.mywardrobe.app.domain.model.Season
import com.mywardrobe.app.ui.camera.CaptureScreen
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.components.ChipGroup

@Composable
fun AddItemScreen(onDone: () -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: AddItemViewModel = viewModel(
        factory = ViewModelFactory {
            AddItemViewModel(container.wardrobeRepository, container.backgroundRemover, container.imageStorage)
        },
    )
    val step by viewModel.step.collectAsStateWithLifecycle()

    when (val current = step) {
        is AddItemStep.Capture -> {
            CaptureScreen(
                filePrefix = "item",
                onImageCaptured = viewModel::onImageCaptured,
                onCancel = onCancel,
                guideOverlay = {
                    Text(
                        text = "Разложите вещь на светлом фоне и сфотографируйте",
                        color = Color.White,
                        modifier = Modifier
                            .align(Alignment.TopCenter)
                            .padding(24.dp),
                    )
                },
            )
        }

        is AddItemStep.Processing -> {
            LoadingContent("Убираем фон и определяем цвет…")
        }

        is AddItemStep.TagPicker -> {
            TagPickerContent(
                imageUri = current.cutoutUri ?: current.originalUri,
                dominantColorArgb = current.dominantColorArgb,
                selectedCategory = viewModel.selectedCategory,
                selectedSeasons = viewModel.selectedSeasons,
                selectedOccasions = viewModel.selectedOccasions,
                onCategorySelected = viewModel::selectCategory,
                onSeasonToggle = viewModel::toggleSeason,
                onOccasionToggle = viewModel::toggleOccasion,
                onSave = { viewModel.save(onDone) },
                onCancel = onCancel,
            )
        }

        is AddItemStep.Saving -> {
            LoadingContent("Сохраняем вещь…")
        }

        is AddItemStep.Done -> {
            // Переход на предыдущий экран уже выполнен колбэком onDone из save().
        }
    }
}

@Composable
private fun LoadingContent(message: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(modifier = Modifier.height(16.dp))
            Text(message)
        }
    }
}

@Composable
private fun TagPickerContent(
    imageUri: Uri,
    dominantColorArgb: Int,
    selectedCategory: Category,
    selectedSeasons: Set<Season>,
    selectedOccasions: Set<Occasion>,
    onCategorySelected: (Category) -> Unit,
    onSeasonToggle: (Season) -> Unit,
    onOccasionToggle: (Occasion) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            AsyncImage(
                model = imageUri,
                contentDescription = null,
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(240.dp),
            )

            Spacer(modifier = Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(Color(dominantColorArgb), CircleShape),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Определённый цвет вещи")
            }

            Spacer(modifier = Modifier.height(20.dp))
            Text("Категория", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
            ChipGroup(
                items = Category.entries,
                isSelected = { it == selectedCategory },
                label = { it.label },
                onToggle = onCategorySelected,
            )

            Spacer(modifier = Modifier.height(20.dp))
            Text("Сезон", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
            ChipGroup(
                items = Season.entries,
                isSelected = { it in selectedSeasons },
                label = { it.label },
                onToggle = onSeasonToggle,
            )

            Spacer(modifier = Modifier.height(20.dp))
            Text("Повод", style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(8.dp))
            ChipGroup(
                items = Occasion.entries,
                isSelected = { it in selectedOccasions },
                label = { it.label },
                onToggle = onOccasionToggle,
            )

            Spacer(modifier = Modifier.height(24.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onCancel) { Text("Отмена") }
                Spacer(modifier = Modifier.width(8.dp))
                Button(onClick = onSave) { Text("Сохранить в гардероб") }
            }
        }
    }
}
