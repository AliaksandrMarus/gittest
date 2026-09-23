package com.mywardrobe.app.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Checkroom
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Style
import androidx.compose.ui.graphics.vector.ImageVector

object Destinations {
    const val WARDROBE = "wardrobe"
    const val ADD_ITEM = "add_item"
    const val OUTFITS = "outfits"
    const val OUTFIT_BUILDER = "outfit_builder"
    const val OUTFIT_BUILDER_WITH_ID = "outfit_builder?outfitId={outfitId}"
    const val OUTFIT_DETAIL = "outfit_detail/{outfitId}"
    const val PROFILE = "profile"

    fun outfitBuilder(outfitId: String? = null): String =
        if (outfitId == null) OUTFIT_BUILDER else "outfit_builder?outfitId=$outfitId"

    fun outfitDetail(outfitId: String): String = "outfit_detail/$outfitId"
}

data class BottomNavItem(
    val route: String,
    val label: String,
    val icon: ImageVector,
)

val bottomNavItems = listOf(
    BottomNavItem(Destinations.WARDROBE, "Гардероб", Icons.Filled.Checkroom),
    BottomNavItem(Destinations.OUTFITS, "Образы", Icons.Filled.Style),
    BottomNavItem(Destinations.PROFILE, "Профиль", Icons.Filled.Person),
)
