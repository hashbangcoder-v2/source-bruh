package com.sourcebruh.mobile

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.core.content.FileProvider
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class ImageClipboardModule(private val reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName(): String = "ImageClipboard"

    @ReactMethod
    fun copyImageUrlToClipboard(url: String, promise: Promise) {
        Thread {
            try {
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.connectTimeout = 30000
                connection.readTimeout = 30000
                connection.instanceFollowRedirects = true
                connection.setRequestProperty("User-Agent", "SourceBruh/1.0")

                val contentType = connection.contentType ?: "image/jpeg"
                val extension = when {
                    contentType.contains("png", ignoreCase = true) -> "png"
                    contentType.contains("webp", ignoreCase = true) -> "webp"
                    else -> "jpg"
                }

                val dir = File(reactContext.cacheDir, "clipboard_images")
                dir.mkdirs()
                val file = File(dir, "sourcebruh_clipboard.$extension")
                connection.inputStream.use { input ->
                    file.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
                connection.disconnect()

                val uri = FileProvider.getUriForFile(
                    reactContext,
                    "${reactContext.packageName}.fileprovider",
                    file,
                )
                val clipboard = reactContext.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newUri(reactContext.contentResolver, "SourceBruh image", uri)
                clipboard.setPrimaryClip(clip)
                promise.resolve(true)
            } catch (error: Exception) {
                promise.reject("COPY_IMAGE_FAILED", error.message, error)
            }
        }.start()
    }
}
