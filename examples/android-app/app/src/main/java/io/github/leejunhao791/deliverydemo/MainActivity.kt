package io.github.leejunhao791.deliverydemo

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private var client: BleCounterClient? = null
    private lateinit var status: TextView
    private lateinit var values: TextView
    private lateinit var recovery: TextView
    private lateinit var history: TextView
    private lateinit var control: Button
    private val events = ArrayDeque<String>()
    private var read = "—"
    private var notification = "—"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val background = Color.rgb(15, 24, 35)
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(32), dp(22), dp(24))
            setBackgroundColor(background)
        }
        body.addView(label("BLE counter", 30, Color.WHITE))
        status = label("Ready", 18, Color.rgb(109, 227, 193))
        values = label("", 18, Color.WHITE)
        recovery = label("Recovery —", 15, Color.rgb(177, 200, 219))
        control = Button(this).apply {
            text = "Start BLE session"
            setOnClickListener { if (client == null) checkPermissions() else stopSession() }
        }
        history = label("", 14, Color.rgb(177, 200, 219)).apply {
            typeface = android.graphics.Typeface.MONOSPACE
        }
        for (view in listOf(status, values, recovery, control, history)) body.addView(view)
        updateValues()
        setContentView(ScrollView(this).apply {
            isFillViewport = true
            setBackgroundColor(background)
            addView(body, ViewGroup.LayoutParams(-1, -2))
        })
    }

    private fun label(value: String, size: Int, color: Int) = TextView(this).apply {
        text = value
        textSize = size.toFloat()
        setTextColor(color)
        setPadding(0, dp(8), 0, dp(8))
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private fun checkPermissions() {
        val permissions = if (Build.VERSION.SDK_INT >= 31) {
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isEmpty()) startSession() else requestPermissions(missing.toTypedArray(), 1)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1 && grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            startSession()
        } else {
            status.text = "Bluetooth permission is required"
        }
    }

    private fun startSession() {
        val adapter = getSystemService(BluetoothManager::class.java)?.adapter
        if (adapter == null) {
            status.text = "Bluetooth LE unavailable"
            return
        }
        events.clear()
        history.text = ""
        read = "—"
        notification = "—"
        recovery.text = "Recovery —"
        updateValues()
        control.text = "Stop BLE session"
        client = BleCounterClient(this, adapter, ::showEvent).also { it.start() }
    }

    private fun stopSession() {
        client?.stop()
        client = null
        status.text = "Stopped"
        control.text = "Start BLE session"
    }

    private fun updateValues() {
        values.text = "Read $read   ·   Notification $notification"
    }

    private fun showEvent(event: String, detail: String) {
        Log.i("BleCounter", "$event $detail")
        when (event) {
            "READ" -> read = detail
            "NOTIFY" -> notification = detail
            "RECOVERED" -> recovery.text = "Recovered in $detail"
            else -> status.text = "$event · $detail"
        }
        updateValues()
        if (event != "NOTIFY") {
            events.addFirst("$event $detail")
            if (events.size > 8) events.removeLast()
            history.text = events.joinToString("\n")
        }
    }

    override fun onDestroy() {
        client?.stop()
        super.onDestroy()
    }
}
