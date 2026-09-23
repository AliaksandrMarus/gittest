package com.mywardrobe.app.ui.outfits

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.domain.model.OutfitSummary
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.components.EmptyState

@Composable
fun OutfitsScreen(
    onOutfitClick: (String) -> Unit,
    onCreateOutfitClick: () -> Unit,
) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: OutfitsViewModel = viewModel(
        factory = ViewModelFactory { OutfitsViewModel(container.outfitRepository) },
    )
    val outfits by viewModel.outfits.collectAsStateWithLifecycle()

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateOutfitClick) {
                Icon(Icons.Filled.Add, contentDescription = "Новый образ")
            }
        },
    ) { padding ->
        if (outfits.isEmpty()) {
            EmptyState(
                message = "Сохранённых образов пока нет. Соберите первый в конструкторе.",
                modifier = Modifier.padding(padding),
            )
        } else {
            LazyColumn(
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier
                    .padding(padding)
                    .fillMaxSize(),
            ) {
                items(outfits, key = { it.id }) { outfit ->
                    OutfitSummaryCard(outfit = outfit, onClick = { onOutfitClick(outfit.id) })
                }
            }
        }
    }
}

@Composable
private fun OutfitSummaryCard(outfit: OutfitSummary, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = outfit.name, style = MaterialTheme.typography.titleMedium)
            outfit.occasion?.let { occasion ->
                Text(text = occasion.label, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
