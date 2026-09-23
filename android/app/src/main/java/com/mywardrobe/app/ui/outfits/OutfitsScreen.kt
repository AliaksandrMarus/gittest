package com.mywardrobe.app.ui.outfits

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.shape.RoundedCornerShape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.mywardrobe.app.WardrobeApplication
import com.mywardrobe.app.domain.advisor.OutfitSuggestion
import com.mywardrobe.app.domain.model.OutfitSummary
import com.mywardrobe.app.ui.common.ViewModelFactory
import com.mywardrobe.app.ui.components.EmptyState

@Composable
fun OutfitsScreen(
    onOutfitClick: (String) -> Unit,
    onCreateOutfitClick: () -> Unit,
    onOpenBuilderWithId: (String) -> Unit,
) {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: OutfitsViewModel = viewModel(
        factory = ViewModelFactory {
            OutfitsViewModel(container.outfitRepository, container.wardrobeRepository, container.outfitAdvisor)
        },
    )
    val outfits by viewModel.outfits.collectAsStateWithLifecycle()
    val suggestions by viewModel.suggestions.collectAsStateWithLifecycle()
    val isAdvising by viewModel.isAdvising.collectAsStateWithLifecycle()

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateOutfitClick) {
                Icon(Icons.Filled.Add, contentDescription = "Новый образ")
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            Button(
                onClick = viewModel::requestSuggestions,
                enabled = !isAdvising,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
            ) {
                Text(if (isAdvising) "Подбираем…" else "Подобрать образ")
            }

            if (outfits.isEmpty()) {
                EmptyState(message = "Сохранённых образов пока нет. Соберите первый в конструкторе.")
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(outfits, key = { it.id }) { outfit ->
                        OutfitSummaryCard(outfit = outfit, onClick = { onOutfitClick(outfit.id) })
                    }
                }
            }
        }
    }

    if (suggestions.isNotEmpty()) {
        SuggestionsDialog(
            suggestions = suggestions,
            onDismiss = viewModel::clearSuggestions,
            onSelect = { suggestion -> viewModel.openSuggestionInBuilder(suggestion, onOpenBuilderWithId) },
        )
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

@Composable
private fun SuggestionsDialog(
    suggestions: List<OutfitSuggestion>,
    onDismiss: () -> Unit,
    onSelect: (OutfitSuggestion) -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Варианты образа", style = MaterialTheme.typography.titleLarge)
                Text(
                    "Выберите вариант, чтобы открыть его в конструкторе и подправить",
                    style = MaterialTheme.typography.bodySmall,
                )
                LazyColumn(
                    modifier = Modifier
                        .padding(top = 12.dp)
                        .heightIn(max = 400.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(suggestions) { suggestion ->
                        SuggestionCard(suggestion = suggestion, onClick = { onSelect(suggestion) })
                    }
                }
            }
        }
    }
}

@Composable
private fun SuggestionCard(suggestion: OutfitSuggestion, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                items(suggestion.items, key = { it.id }) { item ->
                    AsyncImage(
                        model = item.displayImageUri,
                        contentDescription = item.category.label,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .size(56.dp)
                            .clip(RoundedCornerShape(6.dp)),
                    )
                }
            }
            Text(
                text = suggestion.reason,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}
