package com.mywardrobe.app.ui.additem

import android.net.Uri

sealed interface AddItemStep {
    data object Capture : AddItemStep

    data class Processing(val originalUri: Uri) : AddItemStep

    data class TagPicker(
        val originalUri: Uri,
        val cutoutUri: Uri?,
        val dominantColorArgb: Int,
    ) : AddItemStep

    data object Saving : AddItemStep

    data object Done : AddItemStep
}
