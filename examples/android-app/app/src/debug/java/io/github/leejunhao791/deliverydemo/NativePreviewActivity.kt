package io.github.leejunhao791.deliverydemo

import android.app.Activity
import android.os.Bundle
import android.os.SystemClock
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import org.webrtc.*
import java.net.HttpURLConnection
import java.net.Proxy
import java.net.URL
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit

class NativePreviewActivity : Activity() {
    companion object {
        var statusListener: ((String) -> Unit)? = null
        var stopPreview: (() -> Unit)? = null
    }

    private lateinit var egl: EglBase
    private lateinit var renderer: SurfaceEglRenderer
    private lateinit var factory: PeerConnectionFactory
    private lateinit var peer: PeerConnection
    @Volatile private var track: VideoTrack? = null
    private var worker: Thread? = null
    private val lock = Any()
    private var started = 0L
    private var restored = 0L
    private var first: Long? = null
    private var recovered: Long? = null
    private var rendered = 0
    @Volatile private var complete = false
    @Volatile private var candidate: IceCandidate? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val port = intent.getIntExtra("signalPort", 0)
        if (port !in 1..65535) {
            finish()
            return
        }
        stopPreview = { finish() }
        statusListener?.invoke("Waiting for video")
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val status = TextView(this).apply {
            text = "Waiting for WebRTC video"
            textSize = 20f
            setPadding(24, 24, 24, 24)
        }
        val surface = SurfaceView(this)
        val stop = Button(this).apply {
            text = "Stop preview"
            setOnClickListener { finish() }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(status)
            addView(surface, LinearLayout.LayoutParams(-1, 0, 1f))
            addView(stop)
        })
        egl = EglBase.create()
        renderer = SurfaceEglRenderer("NativePreview")
        renderer.init(egl.eglBaseContext, EglBase.CONFIG_PLAIN, GlRectDrawer())
        surface.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) = renderer.surfaceCreated(holder)
            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
                renderer.surfaceChanged(holder, format, width, height)
                renderer.setLayoutAspectRatio(width.toFloat() / height.coerceAtLeast(1))
            }
            override fun surfaceDestroyed(holder: SurfaceHolder) = renderer.surfaceDestroyed(holder)
        })
        renderer.addRenderListener {
            val update = synchronized(lock) {
                val now = SystemClock.elapsedRealtime()
                rendered++
                if (first == null && started > 0) first = now - started
                if (recovered == null && restored > 0) recovered = now - restored
                if (rendered == 1 || rendered % 5 == 0) "Rendered $rendered frames · First frame $first ms" else null
            }
            if (update != null) runOnUiThread {
                if (!complete) {
                    status.text = update
                    statusListener?.invoke(update)
                }
            }
        }
        PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(this).createInitializationOptions())
        factory = PeerConnectionFactory.builder().setVideoDecoderFactory(DefaultVideoDecoderFactory(egl.eglBaseContext))
            .createPeerConnectionFactory()
        peer = createPeer()
        worker = Thread({
            try {
                val url = URL("http://127.0.0.1:$port/command")
                while (!Thread.currentThread().isInterrupted) {
                    val command = request(url)
                    if (command == null) {
                        Thread.sleep(75)
                        continue
                    }
                    val result = try {
                        execute(command, status)
                    } catch (error: Exception) {
                        JSONObject().put("error", error.message ?: error.javaClass.simpleName)
                    }
                    request(url, result)
                    if (command.getString("action") == "complete") {
                        runOnUiThread {
                            status.text = "Preview passed"
                            statusListener?.invoke("Preview passed")
                        }
                        break
                    }
                }
            } catch (error: InterruptedException) {
                Thread.currentThread().interrupt()
            } catch (error: Exception) {
                runOnUiThread {
                    status.text = "Preview ended: ${error.message}"
                    statusListener?.invoke(status.text.toString())
                }
            }
        }, "preview-signal").apply { start() }
    }

    private fun createPeer(): PeerConnection {
        val config = PeerConnection.RTCConfiguration(emptyList()).apply {
            sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
        }
        return checkNotNull(factory.createPeerConnection(config, object : PeerConnection.Observer {
            override fun onSignalingChange(state: PeerConnection.SignalingState) {}
            override fun onIceConnectionChange(state: PeerConnection.IceConnectionState) {}
            override fun onIceConnectionReceivingChange(receiving: Boolean) {}
            override fun onIceGatheringChange(state: PeerConnection.IceGatheringState) {}
            override fun onIceCandidate(value: IceCandidate) {
                val fields = value.sdp.split(' ')
                if (fields.getOrNull(2).equals("udp", ignoreCase = true) &&
                    fields.getOrNull(4)?.matches(Regex("\\d+\\.\\d+\\.\\d+\\.\\d+")) == true &&
                    fields.getOrNull(7) == "host" && candidate == null) candidate = value
            }
            override fun onIceCandidatesRemoved(candidates: Array<IceCandidate>) {}
            override fun onAddStream(stream: MediaStream) {}
            override fun onRemoveStream(stream: MediaStream) {}
            override fun onDataChannel(channel: DataChannel) {}
            override fun onRenegotiationNeeded() {}
            override fun onTrack(transceiver: RtpTransceiver) {
                track = transceiver.receiver.track() as? VideoTrack
                track?.addSink(renderer)
            }
        }))
    }

    private fun execute(command: JSONObject, status: TextView): JSONObject = when (command.getString("action")) {
        "reset" -> {
            runOnUiThread {
                status.text = "Reconnecting video"
                statusListener?.invoke("Reconnecting video")
            }
            val replacement = createPeer()
            track?.removeSink(renderer)
            track = null
            peer.dispose()
            candidate = null
            synchronized(lock) {
                started = 0L
                restored = 0L
                first = null
                recovered = null
                rendered = 0
            }
            peer = replacement
            JSONObject()
        }
        "offer" -> {
            sdp { peer.setRemoteDescription(it, SessionDescription(SessionDescription.Type.OFFER, command.getString("sdp"))) }
            val answer = sdp { peer.createAnswer(it, MediaConstraints()) }
            sdp { peer.setLocalDescription(it, SessionDescription(SessionDescription.Type.ANSWER, answer)) }
            JSONObject().put("sdp", answer)
        }
        "candidate" -> {
            val result = JSONObject()
            candidate?.let {
                result.put("candidate", "candidate:${it.sdp.removePrefix("candidate:")}")
                    .put("sdpMid", it.sdpMid).put("sdpMLineIndex", it.sdpMLineIndex)
            }
            result
        }
        "connect" -> {
            synchronized(lock) { started = SystemClock.elapsedRealtime() }
            val ice = IceCandidate(command.getString("sdpMid"), command.getInt("sdpMLineIndex"),
                command.getString("candidate"))
            check(peer.addIceCandidate(ice)) { "Could not add relay ICE candidate" }
            JSONObject()
        }
        "restore" -> {
            synchronized(lock) {
                restored = SystemClock.elapsedRealtime()
                recovered = null
            }
            JSONObject()
        }
        "sample" -> sample()
        "complete" -> {
            complete = true
            JSONObject()
        }
        else -> error("Unknown preview command")
    }

    private fun sample(): JSONObject {
        val stats = ArrayBlockingQueue<RTCStatsReport>(1)
        peer.getStats { stats.offer(it) }
        val map = checkNotNull(stats.poll(3, TimeUnit.SECONDS)) { "WebRTC stats timeout" }.statsMap
        val video = map.values.firstOrNull { it.type == "inbound-rtp" && it.members["kind"] == "video" }
        val transport = map.values.firstOrNull { it.type == "transport" && it.members.containsKey("selectedCandidatePairId") }
        val pair = map[transport?.members?.get("selectedCandidatePairId") as? String]
        val remote = map[pair?.members?.get("remoteCandidateId") as? String]
        val iceState = peer.iceConnectionState().name.lowercase()
        return synchronized(lock) {
            JSONObject().put("rendered", rendered)
                .put("firstFrameMs", first ?: JSONObject.NULL)
                .put("recoveryMs", recovered ?: JSONObject.NULL)
                .put("iceState", iceState)
                .put("remotePort", remote?.members?.get("port") ?: JSONObject.NULL)
                .put("framesDropped", video?.members?.get("framesDropped") ?: JSONObject.NULL)
                .put("packetsLost", video?.members?.get("packetsLost") ?: JSONObject.NULL)
        }
    }

    private fun sdp(action: (SdpObserver) -> Unit): String {
        val result = ArrayBlockingQueue<Result<String>>(1)
        action(object : SdpObserver {
            override fun onCreateSuccess(description: SessionDescription) {
                result.offer(Result.success(description.description))
            }
            override fun onSetSuccess() { result.offer(Result.success("")) }
            override fun onCreateFailure(error: String) { onSetFailure(error) }
            override fun onSetFailure(error: String) {
                result.offer(Result.failure(IllegalStateException(error)))
            }
        })
        return checkNotNull(result.poll(4, TimeUnit.SECONDS)) { "WebRTC SDP timeout" }.getOrThrow()
    }

    private fun request(url: URL, body: JSONObject? = null): JSONObject? {
        val connection = url.openConnection(Proxy.NO_PROXY) as HttpURLConnection
        try {
            connection.connectTimeout = 1500
            connection.readTimeout = 1500
            if (body != null) {
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            return when (val status = connection.responseCode) {
                204 -> null
                200 -> JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                else -> error("Preview signaling HTTP $status")
            }
        } finally {
            connection.disconnect()
        }
    }

    override fun onDestroy() {
        worker?.interrupt()
        worker?.join(2000)
        if (::peer.isInitialized) {
            track?.removeSink(renderer)
            peer.dispose()
        }
        if (::factory.isInitialized) factory.dispose()
        if (::renderer.isInitialized) renderer.release()
        if (::egl.isInitialized) egl.release()
        stopPreview = null
        statusListener?.invoke("Stopped")
        super.onDestroy()
    }
}
