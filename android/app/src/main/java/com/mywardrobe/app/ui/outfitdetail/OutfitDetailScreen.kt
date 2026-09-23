package com.mywardrobe.app.ui.outfitdetail

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.outfitbuilder.FlatLayCollage

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OutfitDetailScreen(
    outfitId: String,
    onEditClick: (String) -> Unit,
    onDeleted: () -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: OutfitDetailViewModel = viewModel(
        factory = ViewModelFactory { OutfitDetailViewModel(container.outfitRepository, outfitId) },
    )
    val outfit by viewModel.outfit.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(outfit?.name ?: "Образ") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Назад")
                    }
                },
                actions = {
                    IconButton(onClick = { onEditClick(outfitId) }) {
                        Icon(Icons.Filled.Edit, contentDescription = "Редактировать")
                    }
                    IconButton(onClick = { viewModel.delete(onDeleted) }) {
                        Icon(Icons.Filled.Delete, contentDescription = "Удалить")
                    }
                },
            )
        },
    ) { padding ->
        val currentOutfit = outfit
        if (currentOutfit == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
        } else {
            FlatLayCollage(
                items = currentOutfit.items,
                modifier = Modifier
                    .padding(padding)
                    .fillMaxSize(),
            )
        }
    }
}
