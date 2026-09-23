package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mywardrobe.app.WardrobeApplication
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
            OutfitBuilderViewModel(
                container.outfitRepository,
                container.wardrobeRepository,
                container.profileRepository,
                outfitId,
            )
        },
    )
    val profilePhotoUri by viewModel.profilePhotoUri.collectAsStateWithLifecycle()
    val wardrobeItems by viewModel.wardrobeItems.collectAsStateWithLifecycle()
    var selectedPlacementId by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    OutlinedTextField(
                        value = viewModel.outfitName,
                        onValueChange = viewModel::setOutfitName,
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
                .fillMaxSize(),
        ) {
            DraggableCanvas(
                backgroundImageUri = profilePhotoUri,
                placements = viewModel.placements,
                selectedPlacementId = selectedPlacementId,
                onPlacementSelected = { selectedPlacementId = it },
                onPlacementTransform = viewModel::updatePlacement,
                onPlacementRemoved = { id ->
                    viewModel.removePlacement(id)
                    if (selectedPlacementId == id) selectedPlacementId = null
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.75f),
            )

            Text(
                text = "Нажмите на вещь внизу, чтобы добавить на холст. Долгое нажатие на холсте — удалить.",
                style = MaterialTheme.typography.labelMedium,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )

            LazyRow(
                contentPadding = PaddingValues(12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(wardrobeItems, key = { it.id }) { item ->
                    PhotoThumbnail(
                        imageUri = item.displayImageUri,
                        label = item.category.label,
                        modifier = Modifier.size(88.dp),
                        onClick = { viewModel.addItem(item) },
                    )
                }
            }
        }
    }
}
