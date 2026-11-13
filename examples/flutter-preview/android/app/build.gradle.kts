plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "io.github.leejunhao791.delivery_flutter_preview"
    compileSdk = 35
    ndkVersion = "27.0.12077973"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "io.github.leejunhao791.delivery_flutter_preview"
        minSdk = flutter.minSdkVersion
        targetSdk = 35
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    sourceSets.getByName("debug") {
        java.srcDir("../../../android-app/app/src/debug/java")
        res.srcDir("../../../android-app/app/src/debug/res")
    }
}

dependencies {
    debugImplementation("io.github.webrtc-sdk:android:150.7871.01")
}

flutter {
    source = "../.."
}
