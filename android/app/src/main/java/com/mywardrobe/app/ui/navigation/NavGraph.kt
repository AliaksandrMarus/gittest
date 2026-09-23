package com.mywardrobe.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.mywardrobe.app.ui.outfits.OutfitsScreen
import com.mywardrobe.app.ui.profile.ProfileScreen
import com.mywardrobe.app.ui.wardrobe.WardrobeScreen

@Composable
fun rememberWardrobeNavController(): NavHostController = rememberNavController()

@Composable
fun WardrobeNavGraph(navController: NavHostController) {
    NavHost(navController = navController, startDestination = Destinations.WARDROBE) {
        composable(Destinations.WARDROBE) {
            WardrobeScreen(
                onAddItemClick = { navController.navigate(Destinations.ADD_ITEM) },
            )
        }
        composable(Destinations.OUTFITS) {
            OutfitsScreen(
                onOutfitClick = { outfitId -> navController.navigate(Destinations.outfitDetail(outfitId)) },
                onCreateOutfitClick = { navController.navigate(Destinations.outfitBuilder()) },
            )
        }
        composable(Destinations.PROFILE) {
            ProfileScreen()
        }
    }
}
