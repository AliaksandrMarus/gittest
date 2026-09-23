package com.mywardrobe.app.ui.profile

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mywardrobe.app.data.repository.ProfileRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class ProfileViewModel(private val repository: ProfileRepository) : ViewModel() {

    val profilePhotoUri: StateFlow<String?> = repository.observeProfilePhotoUri()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun setProfilePhoto(uri: Uri) {
        viewModelScope.launch { repository.setProfilePhotoUri(uri.toString()) }
    }
}
