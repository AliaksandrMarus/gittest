package com.mywardrobe.app.ui.wardrobe

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun WardrobeScreen(onAddItemClick: () -> Unit) {
    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = onAddItemClick) {
                Icon(Icons.Filled.Add, contentDescription = "Добавить вещь")
            }
        },
    ) { padding ->
        Text(
            text = "Гардероб пуст. Добавьте первую вещь.",
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        )
    }
}
