package com.mywardrobe.app.di

import android.content.Context
import com.mywardrobe.app.domain.advisor.OutfitAdvisor
import com.mywardrobe.app.domain.advisor.RuleBasedOutfitAdvisor
import com.mywardrobe.app.data.imaging.BackgroundRemover
import com.mywardrobe.app.data.imaging.ImageStorage
import com.mywardrobe.app.data.imaging.MlKitBackgroundRemover
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

    val imageStorage: ImageStorage by lazy { ImageStorage(appContext) }

    /** Единственная точка замены реализации вырезания фона (см. BackgroundRemover). */
    val backgroundRemover: BackgroundRemover by lazy { MlKitBackgroundRemover() }

    /** Единственная точка замены на LLM-советчика позже (см. OutfitAdvisor). */
    val outfitAdvisor: OutfitAdvisor by lazy { RuleBasedOutfitAdvisor() }
}
