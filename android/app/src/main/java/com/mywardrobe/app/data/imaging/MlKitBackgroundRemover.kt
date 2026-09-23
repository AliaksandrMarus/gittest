package com.mywardrobe.app.data.imaging

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.segmentation.subject.SubjectSegmentation
import com.google.mlkit.vision.segmentation.subject.SubjectSegmenterOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.resume
import kotlinx.coroutines.resumeWithException

class MlKitBackgroundRemover : BackgroundRemover {
    private val segmenter by lazy {
        SubjectSegmentation.getClient(
            SubjectSegmenterOptions.Builder()
                .enableForegroundBitmap()
                .build(),
        )
    }

    override suspend fun removeBackground(source: Bitmap): Bitmap =
        try {
            suspendCancellableCoroutine { continuation ->
                val inputImage = InputImage.fromBitmap(source, 0)
                segmenter.process(inputImage)
                    .addOnSuccessListener { result ->
                        continuation.resume(result.foregroundBitmap ?: source)
                    }
                    .addOnFailureListener { exception ->
                        continuation.resumeWithException(exception)
                    }
            }
        } catch (e: Exception) {
            // Модель Play Services могла не успеть загрузиться (нет сети при первом
            // запуске) или сегментация не удалась — отдаём исходное фото без
            // прозрачности вместо падения экрана добавления вещи.
            source
        }
}
