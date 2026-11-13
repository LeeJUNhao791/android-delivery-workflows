package io.github.leejunhao791.deliverydemo

internal class BleRecovery {
    private var delay = 1000L
    private var subscribed = false
    private var hasStream = false
    private var lostAt: Long? = null

    fun retryDelay(now: Long): Long {
        if (hasStream && lostAt == null) lostAt = now
        subscribed = false
        val current = delay
        delay = (delay * 2).coerceAtMost(4000L)
        return current
    }

    fun subscribed() {
        subscribed = true
        hasStream = true
        delay = 1000L
    }

    fun notification(now: Long): Long? {
        if (!subscribed) return null
        val elapsed = lostAt?.let { now - it }
        lostAt = null
        return elapsed
    }
}
