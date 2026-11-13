package io.github.leejunhao791.deliverydemo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BleRecoveryTest {
    @Test
    fun backsOffUntilSubscriptionIsRestored() {
        val recovery = BleRecovery()
        assertEquals(1000L, recovery.retryDelay(100))
        assertEquals(2000L, recovery.retryDelay(1100))
        assertEquals(4000L, recovery.retryDelay(3100))
        assertEquals(4000L, recovery.retryDelay(7100))
        recovery.subscribed()
        assertEquals(1000L, recovery.retryDelay(11100))
    }

    @Test
    fun measuresRecoveryOnlyAfterAResubscribedNotification() {
        val recovery = BleRecovery()
        recovery.subscribed()
        assertNull(recovery.notification(100))
        recovery.retryDelay(200)
        recovery.retryDelay(1200)
        assertNull(recovery.notification(2000))
        recovery.subscribed()
        assertEquals(1900L, recovery.notification(2100))
        assertNull(recovery.notification(2200))
    }

    @Test
    fun startupRetryDoesNotCountAsRecovery() {
        val recovery = BleRecovery()
        recovery.retryDelay(100)
        recovery.subscribed()
        assertNull(recovery.notification(1200))
    }
}
