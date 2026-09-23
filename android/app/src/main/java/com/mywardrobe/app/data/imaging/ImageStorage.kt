package com.mywardrobe.app.data.imaging

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import java.io.File
import java.io.FileOutputStream

/** Все фото живут во внутреннем хранилище приложения — без запроса разрешений на память. */
class ImageStorage(context: Context) {
    private val photosDir: File = File(context.filesDir, "photos").apply { mkdirs() }

    fun newCaptureFile(prefix: String): File {
        val timestamp = System.currentTimeMillis()
        return File(photosDir, "${prefix}_$timestamp.jpg")
    }

    fun cutoutFileFor(sourceFile: File): File =
        File(photosDir, "${sourceFile.nameWithoutExtension}_cutout.png")

    fun saveBitmapAsPng(bitmap: Bitmap, file: File) {
        FileOutputStream(file).use { output ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
        }
    }

    fun fileForUri(uri: Uri): File? = uri.path?.let { File(it) }
}
