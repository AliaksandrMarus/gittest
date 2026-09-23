package com.mywardrobe.app.data.local.datastore

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "user_profile")

class UserProfileStore(private val context: Context) {
    private val profilePhotoUriKey = stringPreferencesKey("profile_photo_uri")

    val profilePhotoUri: Flow<String?> =
        context.dataStore.data.map { prefs -> prefs[profilePhotoUriKey] }

    suspend fun setProfilePhotoUri(uri: String?) {
        context.dataStore.edit { prefs ->
            if (uri == null) prefs.remove(profilePhotoUriKey) else prefs[profilePhotoUriKey] = uri
        }
    }
}
