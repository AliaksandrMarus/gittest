package com.mywardrobe.app.ui.wardrobe

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.components.CategoryFilterRow
import com.mywardrobe.app.ui.components.EmptyState
import com.mywardrobe.app.ui.components.PhotoThumbnail

@Composable
fun WardrobeScreen(onAddItemClick: () -> Unit) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: WardrobeViewModel = viewModel(
        factory = ViewModelFactory { WardrobeViewModel(container.wardrobeRepository) },
    )
    val items by viewModel.items.collectAsStateWithLifecycle()
    val selectedCategory = viewModel.selectedCategory

    val filteredItems = remember(items, selectedCategory) {
        if (selectedCategory == null) items else items.filter { it.category == selectedCategory }
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = onAddItemClick) {
                Icon(Icons.Filled.Add, contentDescription = "Добавить вещь")
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            CategoryFilterRow(selected = selectedCategory, onSelect = viewModel::selectCategory)

            if (filteredItems.isEmpty()) {
                EmptyState(
                    message = if (items.isEmpty()) {
                        "Гардероб пуст. Нажмите «+», чтобы сфотографировать первую вещь."
                    } else {
                        "В этой категории пока нет вещей."
                    },
                )
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    contentPadding = PaddingValues(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(items = filteredItems, key = { it.id }) { item ->
                        PhotoThumbnail(imageUri = item.displayImageUri, label = item.category.label)
                    }
                }
            }
        }
    }
}
