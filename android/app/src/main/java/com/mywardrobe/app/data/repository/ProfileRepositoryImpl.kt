package com.mywardrobe.app.data.repository

import com.mywardrobe.app.data.local.datastore.UserProfileStore
import kotlinx.coroutines.flow.Flow

class ProfileRepositoryImpl(
    private val store: UserProfileStore,
) : ProfileRepository {
    override fun observeProfilePhotoUri(): Flow<String?> = store.profilePhotoUri

    override suspend fun setProfilePhotoUri(uri: String?) = store.setProfilePhotoUri(uri)
}
