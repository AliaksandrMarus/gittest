package com.mywardrobe.app

import android.app.Application
import com.mywardrobe.app.di.AppContainer

class WardrobeApplication : Application() {
    val container: AppContainer by lazy { AppContainer(this) }
}
