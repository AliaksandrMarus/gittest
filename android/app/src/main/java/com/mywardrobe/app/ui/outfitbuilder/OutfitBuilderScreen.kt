package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.components.PhotoThumbnail

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OutfitBuilderScreen(
    outfitId: String?,
    onSaved: (String) -> Unit,
    onCancel: () -> Unit,
) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: OutfitBuilderViewModel = viewModel(
        factory = ViewModelFactory {
            OutfitBuilderViewModel(container.outfitRepository, container.wardrobeRepository, outfitId)
        },
    )
    val wardrobeItems by viewModel.wardrobeItems.collectAsStateWithLifecycle()
    val itemsByCategory = remember(wardrobeItems) { wardrobeItems.groupBy { it.category } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    OutlinedTextField(
                        value = viewModel.outfitName,
                        onValueChange = viewModel::updateOutfitName,
                        placeholder = { Text("Название образа") },
                        singleLine = true,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onCancel) {
                        Icon(Icons.Filled.Close, contentDescription = "Отмена")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.save(onSaved) }) {
                        Icon(Icons.Filled.Check, contentDescription = "Сохранить")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
        ) {
            FlatLayCollage(
                items = viewModel.previewItems,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(280.dp),
            )

            Column(modifier = Modifier.padding(vertical = 8.dp)) {
                CategoryPickerRow("Верхняя одежда", itemsByCategory[Category.OUTERWEAR], viewModel.outerwear?.id, viewModel::selectItem)
                CategoryPickerRow("Платье", itemsByCategory[Category.DRESS], viewModel.dress?.id, viewModel::selectItem)
                CategoryPickerRow("Верх", itemsByCategory[Category.TOP], viewModel.top?.id, viewModel::selectItem)
                CategoryPickerRow("Низ", itemsByCategory[Category.BOTTOM], viewModel.bottom?.id, viewModel::selectItem)
                CategoryPickerRow("Обувь", itemsByCategory[Category.SHOES], viewModel.shoes?.id, viewModel::selectItem)
                CategoryPickerRow("Аксессуары", itemsByCategory[Category.ACCESSORY], viewModel.accessory?.id, viewModel::selectItem)
            }
        }
    }
}

@Composable
private fun CategoryPickerRow(
    title: String,
    items: List<ClothingItem>?,
    selectedId: String?,
    onSelect: (ClothingItem) -> Unit,
) {
    if (items.isNullOrEmpty()) return

    Text(
        text = title,
        style = MaterialTheme.typography.labelLarge,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
    )
    LazyRow(
        contentPadding = PaddingValues(horizontal = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(items, key = { it.id }) { item ->
            PhotoThumbnail(
                imageUri = item.displayImageUri,
                label = item.category.label,
                selected = item.id == selectedId,
                modifier = Modifier.size(84.dp),
                onClick = { onSelect(item) },
            )
        }
    }
}
