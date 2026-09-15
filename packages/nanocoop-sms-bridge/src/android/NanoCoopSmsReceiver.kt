package com.nanocoop.smsbridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log

/**
 * Android BroadcastReceiver listening for android.provider.Telephony.SMS_RECEIVED.
 * Extracts incoming telecom receipts and forwards them to the React Native bridge or local WorkManager queue.
 */
class NanoCoopSmsReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "NanoCoopSmsReceiver"
        var smsListener: ((sender: String, message: String, timestamp: Long) -> Unit)? = null
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Telephony.Sms.Intents.SMS_RECEIVED_ACTION) {
            val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
            if (messages.isNullOrEmpty()) {
                return
            }

            for (sms in messages) {
                val sender = sms.displayOriginatingAddress ?: ""
                val body = sms.displayMessageBody ?: ""
                val timestamp = sms.timestampMillis

                Log.d(TAG, "Intercepted SMS from: $sender length: ${body.length}")

                // Forward to in-process listener / React Native NativeEventEmitter
                smsListener?.invoke(sender, body, timestamp)
            }
        }
    }
}
