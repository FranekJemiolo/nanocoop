import React, { memo, useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLedgerStore } from '../store/useLedgerStore';
import { generateKeyPair } from '../utils/crypto';
import { EventModel } from '../utils/api';

export const TransactionScreen: React.FC = memo(() => {
  const { submitTransaction, tellerKeyPair, isOnline, setActiveTab } = useLedgerStore();

  const [eventType, setEventType] = useState<'DEPOSIT_CASH' | 'WITHDRAWAL_CASH'>('DEPOSIT_CASH');
  const [amountInput, setAmountInput] = useState<string>('50');
  const [userPublicKey, setUserPublicKey] = useState<string>('');
  const [userPrivateKey, setUserPrivateKey] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submittedEvent, setSubmittedEvent] = useState<EventModel | null>(null);
  const [isQueuedOffline, setIsQueuedOffline] = useState<boolean>(false);

  // Quick helper to generate / simulate a customer member keypair (NFC card)
  const handleGenerateMemberKey = useCallback(() => {
    const keyPair = generateKeyPair();
    setUserPublicKey(keyPair.publicKeyHex);
    setUserPrivateKey(keyPair.privateKeyHex);
  }, []);

  const handleSubmit = useCallback(async () => {
    const numAmount = parseFloat(amountInput);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid positive dollar amount.');
      return;
    }

    if (!userPublicKey || userPublicKey.length < 32) {
      Alert.alert('Missing Member Public Key', 'Please select or generate a member public key.');
      return;
    }

    if (!userPrivateKey || userPrivateKey.length < 32) {
      Alert.alert(
        'Awaiting NFC / QR Signature',
        'Customer NFC card or QR key is required to authorize this cash transaction.'
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await submitTransaction({
        amount: numAmount,
        currency: 'USD',
        userPublicKey,
        eventType,
        userPrivateKeyHex: userPrivateKey,
        notes,
      });

      setSubmittedEvent(result.event);
      setIsQueuedOffline(result.isQueued);
    } catch (err: any) {
      Alert.alert('Transaction Failed', err?.message || 'Failed to submit transaction');
    } finally {
      setIsSubmitting(false);
    }
  }, [amountInput, userPublicKey, userPrivateKey, eventType, notes, submitTransaction]);

  const handleDoneModal = useCallback(() => {
    setSubmittedEvent(null);
    setAmountInput('');
    setNotes('');
    setActiveTab('dashboard');
  }, [setActiveTab]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      <View style={styles.header}>
        <Text style={styles.title}>Branch Multi-Sig Transaction</Text>
        <Text style={styles.subtitle}>
          Zero-trust cash exchange with dual Ed25519 authorization (Teller + Customer NFC).
        </Text>
      </View>

      {/* Transaction Type Tabs */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tabBtn, eventType === 'DEPOSIT_CASH' && styles.tabActiveDeposit]}
          onPress={() => setEventType('DEPOSIT_CASH')}
          activeOpacity={0.8}
        >
          <Text
            style={[styles.tabText, eventType === 'DEPOSIT_CASH' && styles.tabTextActiveDeposit]}
          >
            + Cash Deposit
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabBtn, eventType === 'WITHDRAWAL_CASH' && styles.tabActiveWithdraw]}
          onPress={() => setEventType('WITHDRAWAL_CASH')}
          activeOpacity={0.8}
        >
          <Text
            style={[styles.tabText, eventType === 'WITHDRAWAL_CASH' && styles.tabTextActiveWithdraw]}
          >
            - Cash Withdrawal
          </Text>
        </TouchableOpacity>
      </View>

      {/* Form Fields */}
      <View style={styles.card}>
        <Text style={styles.inputLabel}>AMOUNT (USD)</Text>
        <TextInput
          style={styles.amountInput}
          value={amountInput}
          onChangeText={setAmountInput}
          keyboardType="decimal-pad"
          placeholder="0.00"
          placeholderTextColor="#475569"
        />

        <View style={styles.memberSection}>
          <View style={styles.memberHeaderRow}>
            <Text style={styles.inputLabel}>CUSTOMER MEMBER PUBLIC KEY</Text>
            <TouchableOpacity onPress={handleGenerateMemberKey} activeOpacity={0.7}>
              <Text style={styles.generateLink}>+ Generate / Sim NFC</Text>
            </TouchableOpacity>
          </View>
          <TextInput
            style={styles.keyInput}
            value={userPublicKey}
            onChangeText={setUserPublicKey}
            placeholder="Ed25519 Public Key (hex string)"
            placeholderTextColor="#475569"
            autoCapitalize="none"
          />
        </View>

        <View style={styles.memberSection}>
          <Text style={styles.inputLabel}>CUSTOMER PRIVATE KEY (NFC SIMULATION)</Text>
          <TextInput
            style={styles.keyInput}
            value={userPrivateKey}
            onChangeText={setUserPrivateKey}
            placeholder="Private Key (supplied temporarily by NFC scan / QR)"
            placeholderTextColor="#475569"
            secureTextEntry
            autoCapitalize="none"
          />
          <Text style={styles.hintText}>
            Simulates reading cryptographic signature token via NFC Card tap.
          </Text>
        </View>

        <View style={styles.memberSection}>
          <Text style={styles.inputLabel}>LEDGER NOTES (OPTIONAL)</Text>
          <TextInput
            style={styles.textInput}
            value={notes}
            onChangeText={setNotes}
            placeholder="e.g., Weekly cooperative contribution"
            placeholderTextColor="#475569"
          />
        </View>
      </View>

      {/* Cryptographic Signature Checklist */}
      <View style={styles.cryptoChecklistCard}>
        <Text style={styles.checklistTitle}>CRYPTOGRAPHIC AUTHORIZATION</Text>

        <View style={styles.checkItem}>
          <View
            style={[styles.checkCircle, tellerKeyPair ? styles.checkDone : styles.checkPending]}
          >
            <Text style={styles.checkSymbol}>{tellerKeyPair ? '✓' : '•'}</Text>
          </View>
          <View style={styles.checkTextCol}>
            <Text style={styles.checkItemTitle}>1. Teller Signature (Local Key)</Text>
            <Text style={styles.checkItemSub}>
              {tellerKeyPair ? 'Hardware Secure Store Unlocked' : 'Key missing'}
            </Text>
          </View>
        </View>

        <View style={styles.checkItem}>
          <View
            style={[styles.checkCircle, userPrivateKey ? styles.checkDone : styles.checkPending]}
          >
            <Text style={styles.checkSymbol}>{userPrivateKey ? '✓' : '•'}</Text>
          </View>
          <View style={styles.checkTextCol}>
            <Text style={styles.checkItemTitle}>2. Customer Signature (NFC / QR)</Text>
            <Text style={styles.checkItemSub}>
              {userPrivateKey ? 'Customer Token Ready' : 'Awaiting Card Tap or QR scan'}
            </Text>
          </View>
        </View>
      </View>

      {/* Submit Button */}
      <TouchableOpacity
        style={[styles.submitButton, isSubmitting && styles.submitButtonDisabled]}
        onPress={handleSubmit}
        disabled={isSubmitting}
        activeOpacity={0.8}
      >
        {isSubmitting ? (
          <ActivityIndicator color="#0F172A" />
        ) : (
          <Text style={styles.submitButtonText}>
            {isOnline ? 'Sign & Post to Ledger' : 'Sign & Queue Offline'}
          </Text>
        )}
      </TouchableOpacity>

      {/* Receipt Modal */}
      <Modal visible={submittedEvent !== null} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalSuccessIcon}>
              <Text style={styles.modalSuccessSymbol}>✓</Text>
            </View>

            <Text style={styles.modalTitle}>
              {isQueuedOffline ? 'Transaction Queued Offline' : 'Transaction Committed'}
            </Text>
            <Text style={styles.modalSubtitle}>
              {isQueuedOffline
                ? 'Your transaction has been cryptographically signed and buffered locally. It will auto-sync when network returns.'
                : 'Appended to the immutable append-only ledger with dual Ed25519 signatures.'}
            </Text>

            {submittedEvent && (
              <View style={styles.receiptBox}>
                <Text style={styles.receiptRow}>
                  Amount: ${submittedEvent.payload.amount.toFixed(2)} {submittedEvent.payload.currency}
                </Text>
                <Text style={styles.receiptRow}>
                  Event ID: {submittedEvent.event_id.substring(0, 16)}...
                </Text>
                <Text style={styles.receiptRow}>
                  Hash: {submittedEvent.current_hash.substring(0, 20)}...
                </Text>
                <Text style={styles.receiptRow}>
                  Previous: {submittedEvent.previous_hash.substring(0, 20)}...
                </Text>
              </View>
            )}

            <TouchableOpacity style={styles.modalCloseBtn} onPress={handleDoneModal}>
              <Text style={styles.modalCloseText}>Done & Return to Dashboard</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
});

TransactionScreen.displayName = 'TransactionScreen';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  subtitle: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
    lineHeight: 18,
  },
  tabRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
  },
  tabActiveDeposit: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    borderColor: '#10B981',
  },
  tabActiveWithdraw: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    borderColor: '#EF4444',
  },
  tabText: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '700',
  },
  tabTextActiveDeposit: {
    color: '#34D399',
  },
  tabTextActiveWithdraw: {
    color: '#F87171',
  },
  card: {
    backgroundColor: '#131B2E',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 16,
  },
  inputLabel: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  amountInput: {
    backgroundColor: '#0F172A',
    borderRadius: 10,
    color: '#F8FAFC',
    fontSize: 26,
    fontWeight: '800',
    paddingHorizontal: 16,
    paddingVertical: 10,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  memberSection: {
    marginBottom: 14,
  },
  memberHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  generateLink: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 6,
  },
  keyInput: {
    backgroundColor: '#0F172A',
    borderRadius: 8,
    color: '#E2E8F0',
    fontSize: 11,
    fontFamily: 'monospace',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  hintText: {
    color: '#64748B',
    fontSize: 10,
    marginTop: 4,
  },
  textInput: {
    backgroundColor: '#0F172A',
    borderRadius: 8,
    color: '#E2E8F0',
    fontSize: 13,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  cryptoChecklistCard: {
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 20,
  },
  checklistTitle: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
    marginBottom: 10,
  },
  checkItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  checkCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  checkDone: {
    backgroundColor: '#10B981',
  },
  checkPending: {
    backgroundColor: '#334155',
  },
  checkSymbol: {
    color: '#0F172A',
    fontSize: 12,
    fontWeight: 'bold',
  },
  checkTextCol: {
    flex: 1,
  },
  checkItemTitle: {
    color: '#F1F5F9',
    fontSize: 12,
    fontWeight: '600',
  },
  checkItemSub: {
    color: '#64748B',
    fontSize: 10,
  },
  submitButton: {
    backgroundColor: '#10B981',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    color: '#0F172A',
    fontSize: 15,
    fontWeight: '800',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    backgroundColor: '#131B2E',
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 420,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  modalSuccessIcon: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: '#10B981',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalSuccessSymbol: {
    color: '#0F172A',
    fontSize: 28,
    fontWeight: '900',
  },
  modalTitle: {
    color: '#F8FAFC',
    fontSize: 18,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 8,
  },
  modalSubtitle: {
    color: '#94A3B8',
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 16,
  },
  receiptBox: {
    backgroundColor: '#0F172A',
    borderRadius: 10,
    padding: 12,
    width: '100%',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  receiptRow: {
    color: '#CBD5E1',
    fontSize: 11,
    fontFamily: 'monospace',
    marginBottom: 4,
  },
  modalCloseBtn: {
    backgroundColor: '#3B82F6',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 24,
    width: '100%',
    alignItems: 'center',
  },
  modalCloseText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
});
