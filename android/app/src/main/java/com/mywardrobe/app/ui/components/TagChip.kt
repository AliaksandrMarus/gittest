package com.mywardrobe.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp

/** Переиспользуемая группа чипов — и для одиночного выбора (категория), и для множественного (сезон/повод). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun <T> ChipGroup(
    items: List<T>,
    isSelected: (T) -> Boolean,
    label: (T) -> String,
    onToggle: (T) -> Unit,
) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.forEach { item ->
            FilterChip(
                selected = isSelected(item),
                onClick = { onToggle(item) },
                label = { Text(label(item)) },
            )
        }
    }
}
