package com.mywardrobe.app.ui.outfits

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun OutfitsScreen(
    onOutfitClick: (String) -> Unit,
    onCreateOutfitClick: () -> Unit,
) {
    Scaffold { padding ->
        Text(
            text = "Сохранённых образов пока нет.",
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        )
    }
}
