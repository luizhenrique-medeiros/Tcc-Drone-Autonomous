plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "br.edu.devcore.drone_delivery_mobile"
    // flutter_secure_storage 11 exige API 37 para compilar. targetSdk continua
    // controlado pelo Flutter para não antecipar mudanças de comportamento.
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "br.edu.devcore.drone_delivery_mobile"
        // flutter_secure_storage exige API 23; o baseline deste Flutter é API 24.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    // Release signing is intentionally not mapped to the public debug key.
    // Configure a private external keystore before producing an APK/AAB.
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
