package com.mywardrobe.app.ui.camera

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import android.net.Uri
import com.mywardrobe.app.data.imaging.ImageStorage

/**
 * Один переиспользуемый экран съёмки — используется и для вещей гардероба,
 * и для фото в полный рост. [guideOverlay] задаёт разную подсказку поверх
 * превью камеры в зависимости от того, что снимается.
 */
@Composable
fun CaptureScreen(
    filePrefix: String,
    onImageCaptured: (Uri) -> Unit,
    onCancel: () -> Unit,
    guideOverlay: (@Composable BoxScope.() -> Unit)? = null,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val imageStorage = remember { ImageStorage(context) }
    val cameraController = remember { CameraController(context) }

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    var permissionDenied by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasCameraPermission = granted
        permissionDenied = !granted
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    Box(modifier = Modifier.fillMaxSize()) {
        when {
            hasCameraPermission -> {
                AndroidView(
                    factory = { ctx ->
                        PreviewView(ctx).also { previewView ->
                            cameraController.startCamera(previewView, lifecycleOwner) { }
                        }
                    },
                    modifier = Modifier.fillMaxSize(),
                )

                guideOverlay?.invoke(this)

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .align(Alignment.BottomCenter)
                        .padding(24.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    TextButton(onClick = onCancel) { Text("Отмена") }
                    FloatingActionButton(
                        onClick = {
                            val file = imageStorage.newCaptureFile(filePrefix)
                            cameraController.takePicture(
                                outputFile = file,
                                onSaved = { uri -> onImageCaptured(uri) },
                                onError = { },
                            )
                        },
                    ) {
                        Icon(Icons.Filled.PhotoCamera, contentDescription = "Сделать снимок")
                    }
                }
            }

            permissionDenied -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text("Нужен доступ к камере, чтобы сделать фото.")
                    TextButton(onClick = onCancel) { Text("Назад") }
                }
            }
        }
    }
}
