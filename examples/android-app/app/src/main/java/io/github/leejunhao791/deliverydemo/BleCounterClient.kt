package io.github.leejunhao791.deliverydemo

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.os.SystemClock
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

@SuppressLint("MissingPermission") // MainActivity grants permissions before creating the client.
internal class BleCounterClient(
    private val context: Context,
    private val adapter: BluetoothAdapter,
    private val display: (event: String, detail: String) -> Unit,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var recovery = BleRecovery()
    private var active = false
    private var ready = false
    private var scan: ScanCallback? = null
    private var gatt: BluetoothGatt? = null
    private val timeout = Runnable { retry("Operation timed out") }
    private val nextScan = Runnable { scanForCounter() }

    fun start() {
        if (active) return
        active = true
        recovery = BleRecovery()
        scanForCounter()
    }

    fun stop() {
        active = false
        closeTransport()
    }

    private fun closeTransport() {
        handler.removeCallbacks(timeout)
        handler.removeCallbacks(nextScan)
        stopScan()
        ready = false
        val previous = gatt
        gatt = null
        previous?.close()
    }

    private fun stopScan() {
        val previous = scan ?: return
        scan = null
        adapter.bluetoothLeScanner?.stopScan(previous)
    }

    private fun retry(reason: String) {
        closeTransport()
        if (!active) return
        val delay = recovery.retryDelay(SystemClock.elapsedRealtime())
        display("RETRY", "$reason · retry in ${delay / 1000}s")
        handler.postDelayed(nextScan, delay)
    }

    private fun armTimeout() {
        handler.removeCallbacks(timeout)
        handler.postDelayed(timeout, 12000)
    }

    private fun scanForCounter() {
        if (!active) return
        val scanner = adapter.bluetoothLeScanner ?: return retry("Bluetooth is off")
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                handler.post {
                    if (scan !== this) return@post
                    stopScan()
                    display("CONNECTING", "Windows BLE counter")
                    gatt = result.device.connectGatt(
                        context, false, gattCallback, BluetoothDevice.TRANSPORT_LE
                    )
                    if (gatt == null) retry("Could not start connection") else armTimeout()
                }
            }

            override fun onScanFailed(errorCode: Int) {
                handler.post { if (scan === this) retry("Scan error $errorCode") }
            }
        }
        scan = callback
        display("SCANNING", "Looking for the counter service")
        val filter = ScanFilter.Builder().setServiceUuid(ParcelUuid(SERVICE)).build()
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        scanner.startScan(listOf(filter), settings, callback)
        armTimeout()
    }

    private fun withCurrent(connection: BluetoothGatt, action: () -> Unit) {
        handler.post { if (gatt === connection && active) action() }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(connection: BluetoothGatt, status: Int, state: Int) {
            withCurrent(connection) {
                if (status != BluetoothGatt.GATT_SUCCESS || state == BluetoothProfile.STATE_DISCONNECTED) {
                    retry("GATT disconnected ($status)")
                } else if (state == BluetoothProfile.STATE_CONNECTED) {
                    display("CONNECTED", "Discovering services")
                    if (connection.discoverServices()) armTimeout() else retry("Discovery could not start")
                }
            }
        }

        override fun onServicesDiscovered(connection: BluetoothGatt, status: Int) {
            withCurrent(connection) {
                val counter = connection.getService(SERVICE)?.getCharacteristic(COUNTER)
                if (status != BluetoothGatt.GATT_SUCCESS || counter == null || !connection.readCharacteristic(counter)) {
                    retry("Counter service or read unavailable ($status)")
                } else {
                    armTimeout()
                }
            }
        }

        override fun onCharacteristicRead(
            connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic,
            value: ByteArray, status: Int,
        ) {
            handleRead(connection, characteristic, value, status)
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicRead(
            connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int,
        ) {
            handleRead(connection, characteristic, characteristic.value?.copyOf(), status)
        }

        override fun onDescriptorWrite(connection: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            withCurrent(connection) {
                if (descriptor.uuid != CCCD || status != BluetoothGatt.GATT_SUCCESS) {
                    retry("Subscription failed ($status)")
                } else {
                    handler.removeCallbacks(timeout)
                    ready = true
                    recovery.subscribed()
                    display("SUBSCRIBED", "Waiting for a counter notification")
                }
            }
        }

        override fun onCharacteristicChanged(
            connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray,
        ) {
            handleNotification(connection, characteristic, value)
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(
            connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic,
        ) {
            handleNotification(connection, characteristic, characteristic.value?.copyOf())
        }
    }

    private fun handleRead(
        connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray?, status: Int,
    ) {
        withCurrent(connection) {
            val counter = decode(value)
            if (status != BluetoothGatt.GATT_SUCCESS || counter == null) {
                return@withCurrent retry("Read failed ($status)")
            }
            display("READ", counter)
            val descriptor = characteristic.getDescriptor(CCCD)
            if (descriptor == null || !connection.setCharacteristicNotification(characteristic, true)
                || !enableNotifications(connection, descriptor)) {
                retry("Could not start subscription")
            } else {
                armTimeout()
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun enableNotifications(connection: BluetoothGatt, descriptor: BluetoothGattDescriptor): Boolean {
        val value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        if (Build.VERSION.SDK_INT >= 33) {
            return connection.writeDescriptor(descriptor, value) == BluetoothStatusCodes.SUCCESS
        }
        descriptor.value = value
        return connection.writeDescriptor(descriptor)
    }

    private fun handleNotification(
        connection: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray?,
    ) {
        withCurrent(connection) {
            if (!ready || characteristic.uuid != COUNTER) return@withCurrent
            val counter = decode(value) ?: return@withCurrent
            display("NOTIFY", counter)
            recovery.notification(SystemClock.elapsedRealtime())?.let {
                display("RECOVERED", "$it ms")
            }
        }
    }

    private fun decode(value: ByteArray?): String? = value?.takeIf { it.size == 4 }?.let {
        ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).int.toUInt().toString()
    }

    private companion object {
        val SERVICE: UUID = UUID.fromString("af727351-9e73-4412-a11b-44ef95814b20")
        val COUNTER: UUID = UUID.fromString("af727352-9e73-4412-a11b-44ef95814b20")
        val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    }
}
