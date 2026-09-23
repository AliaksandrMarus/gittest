package com.mywardrobe.app.ui.profile

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.material3.Button
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import com.mywardrobe.app.ui.camera.CaptureScreen
import com.mywardrobe.app.ui.common.ViewModelFactory

@Composable
fun ProfileScreen() {
    val context = LocalContext.current
    val container = (context.applicationContext as WardrobeApplication).container
    val viewModel: ProfileViewModel = viewModel(
        factory = ViewModelFactory { ProfileViewModel(container.profileRepository) },
    )
    val photoUri by viewModel.profilePhotoUri.collectAsStateWithLifecycle()
    var isCapturing by remember { mutableStateOf(false) }

    if (isCapturing) {
        CaptureScreen(
            filePrefix = "profile",
            onImageCaptured = { uri ->
                viewModel.setProfilePhoto(uri)
                isCapturing = false
            },
            onCancel = { isCapturing = false },
            guideOverlay = {
                Text(
                    text = "Встаньте в полный рост так, чтобы вас было видно целиком",
                    color = Color.White,
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(24.dp),
                )
            },
        )
        return
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            val currentUri = photoUri
            if (currentUri != null) {
                AsyncImage(
                    model = currentUri,
                    contentDescription = "Фото в полный рост",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                )
                Spacer(modifier = Modifier.height(16.dp))
                Button(onClick = { isCapturing = true }) { Text("Заменить фото") }
            } else {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("Фото в полный рост ещё не добавлено")
                }
                Spacer(modifier = Modifier.height(16.dp))
                Button(onClick = { isCapturing = true }) { Text("Сделать фото") }
            }
        }
    }
}
