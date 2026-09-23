package com.mywardrobe.app.di

import android.content.Context
import com.mywardrobe.app.data.local.datastore.UserProfileStore
import com.mywardrobe.app.data.local.db.AppDatabase
import com.mywardrobe.app.data.repository.OutfitRepository
import com.mywardrobe.app.data.repository.OutfitRepositoryImpl
import com.mywardrobe.app.data.repository.ProfileRepository
import com.mywardrobe.app.data.repository.ProfileRepositoryImpl
import com.mywardrobe.app.data.repository.WardrobeRepository
import com.mywardrobe.app.data.repository.WardrobeRepositoryImpl

/**
 * Ручной контейнер зависимостей — без Hilt: для одного Gradle-модуля с
 * несколькими репозиториями отдельный DI-фреймворк добавляет риск версийной
 * несовместимости без реальной выгоды на этом масштабе.
 */
class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    private val database: AppDatabase by lazy { AppDatabase.getInstance(appContext) }
    private val userProfileStore: UserProfileStore by lazy { UserProfileStore(appContext) }

    val wardrobeRepository: WardrobeRepository by lazy {
        WardrobeRepositoryImpl(database.clothingItemDao())
    }

    val outfitRepository: OutfitRepository by lazy {
        OutfitRepositoryImpl(database.outfitDao(), database.outfitItemDao(), database.clothingItemDao())
    }

    val profileRepository: ProfileRepository by lazy {
        ProfileRepositoryImpl(userProfileStore)
    }
}
