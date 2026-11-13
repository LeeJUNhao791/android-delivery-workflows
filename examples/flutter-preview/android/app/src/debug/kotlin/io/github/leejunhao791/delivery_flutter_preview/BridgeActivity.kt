package io.github.leejunhao791.delivery_flutter_preview

import android.content.Intent
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import io.github.leejunhao791.deliverydemo.NativePreviewActivity

class BridgeActivity : FlutterActivity() {
    private var channel: MethodChannel? = null

    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        val bridge = MethodChannel(engine.dartExecutor.binaryMessenger, "delivery/preview")
        channel = bridge
        NativePreviewActivity.statusListener = { status ->
            Log.i("DeliveryPreviewBridge", status)
            bridge.invokeMethod("status", status)
        }
        bridge.setMethodCallHandler { call, result ->
            when (call.method) {
                "signalPort" -> result.success(intent.getIntExtra("signalPort", 0))
                "start" -> {
                    val port = call.arguments as? Int
                    if (port == null || port !in 1..65535) {
                        result.error("invalid_port", "Enter a signaling port between 1 and 65535.", null)
                    } else {
                        bridge.invokeMethod("status", "Starting preview")
                        startActivity(Intent(this, NativePreviewActivity::class.java).putExtra("signalPort", port))
                        result.success(null)
                    }
                }
                "stop" -> {
                    NativePreviewActivity.stopPreview?.invoke()
                    bridge.invokeMethod("status", "Stopped")
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun cleanUpFlutterEngine(engine: FlutterEngine) {
        NativePreviewActivity.statusListener = null
        channel?.setMethodCallHandler(null)
        channel = null
        super.cleanUpFlutterEngine(engine)
    }
}
