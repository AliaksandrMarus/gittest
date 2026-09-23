package com.mywardrobe.app.ui.profile

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun ProfileScreen() {
    Scaffold { padding ->
        Text(
            text = "Фото в полный рост ещё не добавлено.",
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        )
    }
}
