package com.mywardrobe.app.data.imaging

import android.graphics.Bitmap

/**
 * Единственная точка замены реализации вырезания фона: MVP использует ML Kit
 * на устройстве, позже сюда можно подставить облачный сервис (remove.bg и т.п.)
 * без изменений где-либо ещё в коде.
 */
interface BackgroundRemover {
    suspend fun removeBackground(source: Bitmap): Bitmap
}
