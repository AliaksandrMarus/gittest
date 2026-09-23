package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.mywardrobe.app.domain.model.Category
import com.mywardrobe.app.domain.model.ClothingItem

/**
 * Плоский коллаж («flat lay») — вещи аккуратно выстраиваются друг под другом
 * по категориям на нейтральной подложке. Без жестов и без фото в полный рост:
 * используется и как живое превью в конструкторе, и как просмотр сохранённого
 * образа — раскладка целиком определяется категориями вещей.
 */
@Composable
fun FlatLayCollage(items: List<ClothingItem>, modifier: Modifier = Modifier) {
    val outerwear = items.firstOrNull { it.category == Category.OUTERWEAR }
    val dress = items.firstOrNull { it.category == Category.DRESS }
    val top = items.firstOrNull { it.category == Category.TOP }
    val bottom = items.firstOrNull { it.category == Category.BOTTOM }
    val shoes = items.firstOrNull { it.category == Category.SHOES }
    val accessory = items.firstOrNull { it.category == Category.ACCESSORY }

    Box(
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
        contentAlignment = Alignment.Center,
    ) {
        if (items.isEmpty()) {
            Text(
                text = "Выберите вещи ниже, чтобы собрать образ",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(24.dp),
            )
        } else {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                outerwear?.let { FlatLayTile(it, 110.dp) }
                if (dress != null) {
                    FlatLayTile(dress, 150.dp)
                } else {
                    top?.let { FlatLayTile(it, 110.dp) }
                    bottom?.let { FlatLayTile(it, 110.dp) }
                }
                shoes?.let { FlatLayTile(it, 80.dp) }
                accessory?.let { FlatLayTile(it, 60.dp) }
            }
        }
    }
}

@Composable
private fun FlatLayTile(item: ClothingItem, size: Dp) {
    Card(modifier = Modifier.size(size)) {
        AsyncImage(
            model = item.displayImageUri,
            contentDescription = item.category.label,
            contentScale = ContentScale.Fit,
            modifier = Modifier
                .fillMaxSize()
                .padding(4.dp),
        )
    }
}
