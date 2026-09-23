package com.mywardrobe.app.ui.outfitbuilder

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.mywardrobe.app.domain.model.OutfitItemPlacement
import kotlin.math.roundToInt

private val ItemSize = 96.dp

/**
 * Холст: фото в полный рост фоном, поверх — вещи гардероба, которые можно
 * перетаскивать/масштабировать/поворачивать одним жестом (detectTransformGestures),
 * выбирать тапом и удалять долгим нажатием.
 */
@Composable
fun DraggableCanvas(
    backgroundImageUri: String?,
    placements: List<OutfitItemPlacement>,
    selectedPlacementId: String? = null,
    interactive: Boolean = true,
    onPlacementSelected: (String) -> Unit = {},
    onPlacementTransform: (id: String, dx: Float, dy: Float, scaleDelta: Float, rotationDelta: Float) -> Unit = { _, _, _, _, _ -> },
    onPlacementRemoved: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(modifier = modifier) {
        val canvasWidthPx = constraints.maxWidth.toFloat()
        val canvasHeightPx = constraints.maxHeight.toFloat()

        if (backgroundImageUri != null) {
            AsyncImage(
                model = backgroundImageUri,
                contentDescription = "Фото в полный рост",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.surfaceVariant),
            )
        }

        placements.sortedBy { it.zIndex }.forEach { placement ->
            key(placement.id) {
                val isSelected = placement.id == selectedPlacementId
                Box(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .placementOffset(canvasWidthPx, canvasHeightPx, placement.x, placement.y)
                        .size(ItemSize)
                        .graphicsLayer(
                            scaleX = placement.scale,
                            scaleY = placement.scale,
                            rotationZ = placement.rotationDegrees,
                        )
                        .clip(RoundedCornerShape(8.dp))
                        .then(
                            if (isSelected) {
                                Modifier.border(2.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(8.dp))
                            } else {
                                Modifier
                            },
                        )
                        .then(
                            if (interactive) {
                                Modifier
                                    .pointerInput(placement.id) {
                                        detectTransformGestures { _, pan, zoom, rotation ->
                                            onPlacementSelected(placement.id)
                                            onPlacementTransform(
                                                placement.id,
                                                pan.x / canvasWidthPx,
                                                pan.y / canvasHeightPx,
                                                zoom,
                                                rotation,
                                            )
                                        }
                                    }
                                    .pointerInput(placement.id) {
                                        detectTapGestures(
                                            onTap = { onPlacementSelected(placement.id) },
                                            onLongPress = { onPlacementRemoved(placement.id) },
                                        )
                                    }
                            } else {
                                Modifier
                            },
                        ),
                ) {
                    AsyncImage(
                        model = placement.item.displayImageUri,
                        contentDescription = placement.item.category.label,
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }
        }
    }
}

private fun Modifier.placementOffset(canvasWidthPx: Float, canvasHeightPx: Float, x: Float, y: Float): Modifier =
    this.then(
        Modifier.offset {
            val halfItemPx = (ItemSize.toPx() / 2f)
            IntOffset(
                (x * canvasWidthPx - halfItemPx).roundToInt(),
                (y * canvasHeightPx - halfItemPx).roundToInt(),
            )
        },
    )
