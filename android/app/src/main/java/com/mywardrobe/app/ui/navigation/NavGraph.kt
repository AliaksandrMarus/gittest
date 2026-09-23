package com.mywardrobe.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.mywardrobe.app.ui.additem.AddItemScreen
import com.mywardrobe.app.ui.outfitbuilder.OutfitBuilderScreen
import com.mywardrobe.app.ui.outfitdetail.OutfitDetailScreen
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
        composable(Destinations.ADD_ITEM) {
            AddItemScreen(
                onDone = { navController.popBackStack() },
                onCancel = { navController.popBackStack() },
            )
        }
        composable(Destinations.OUTFITS) {
            OutfitsScreen(
                onOutfitClick = { outfitId -> navController.navigate(Destinations.outfitDetail(outfitId)) },
                onCreateOutfitClick = { navController.navigate(Destinations.outfitBuilder()) },
                onOpenBuilderWithId = { outfitId -> navController.navigate(Destinations.outfitBuilder(outfitId)) },
            )
        }
        composable(
            route = Destinations.OUTFIT_BUILDER_WITH_ID,
            arguments = listOf(
                navArgument("outfitId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
        ) { backStackEntry ->
            OutfitBuilderScreen(
                outfitId = backStackEntry.arguments?.getString("outfitId"),
                onSaved = { navController.popBackStack() },
                onCancel = { navController.popBackStack() },
            )
        }
        composable(
            route = Destinations.OUTFIT_DETAIL,
            arguments = listOf(navArgument("outfitId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val outfitId = backStackEntry.arguments?.getString("outfitId") ?: return@composable
            OutfitDetailScreen(
                outfitId = outfitId,
                onEditClick = { id -> navController.navigate(Destinations.outfitBuilder(id)) },
                onDeleted = { navController.popBackStack() },
                onBack = { navController.popBackStack() },
            )
        }
        composable(Destinations.PROFILE) {
            ProfileScreen()
        }
    }
}
