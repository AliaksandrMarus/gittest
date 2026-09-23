package com.mywardrobe.app.data.imaging

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
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

    /**
     * BitmapFactory.decodeFile сам по себе игнорирует EXIF-ориентацию JPEG.
     * CameraX часто сохраняет кадр с тегом поворота, а не поворачивает пиксели
     * физически — без этой поправки вырезание фона (ML Kit) получает картинку
     * «лёжа на боку» и не находит объект, хотя в превью (через Coil) всё
     * выглядит нормально, поскольку Coil EXIF учитывает сам.
     */
    fun loadOrientedBitmap(file: File): Bitmap? {
        val bitmap = BitmapFactory.decodeFile(file.path) ?: return null
        val rotationDegrees = runCatching {
            when (ExifInterface(file.path).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90f
                ExifInterface.ORIENTATION_ROTATE_180 -> 180f
                ExifInterface.ORIENTATION_ROTATE_270 -> 270f
                else -> 0f
            }
        }.getOrDefault(0f)

        if (rotationDegrees == 0f) return bitmap

        val matrix = Matrix().apply { postRotate(rotationDegrees) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }
}
