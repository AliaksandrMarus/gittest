package com.mywardrobe.app.data.imaging

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import androidx.palette.graphics.Palette

object ColorExtractor {

    fun extractDominantColor(cutout: Bitmap): Int {
        val opaque = compositeOnNeutralBackground(cutout)
        val palette = Palette.from(opaque).generate()
        return palette.dominantSwatch?.rgb
            ?: palette.vibrantSwatch?.rgb
            ?: palette.mutedSwatch?.rgb
            ?: Color.GRAY
    }

    /**
     * Palette не понимает альфа-канал — на вырезанном (прозрачном) фото
     * прозрачные пиксели читаются как чёрные и портят результат. Поэтому
     * сначала накладываем вырез на непрозрачную нейтральную подложку.
     */
    private fun compositeOnNeutralBackground(source: Bitmap): Bitmap {
        val background = Bitmap.createBitmap(source.width, source.height, Bitmap.Config.ARGB_8888)
        Canvas(background).apply {
            drawColor(Color.LTGRAY)
            drawBitmap(source, 0f, 0f, null)
        }
        return background
    }
}
