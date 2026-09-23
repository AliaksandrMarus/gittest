package com.mywardrobe.app.data.repository

import kotlinx.coroutines.flow.Flow

interface ProfileRepository {
    fun observeProfilePhotoUri(): Flow<String?>
    suspend fun setProfilePhotoUri(uri: String?)
}
