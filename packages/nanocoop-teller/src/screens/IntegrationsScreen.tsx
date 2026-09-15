import React, { useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLedgerStore } from '../store/useLedgerStore';

export const IntegrationsScreen: React.FC = () => {
  const {
    simulateDarajaStk,
    simulateMtnMoMo,
    simulateAirtelMoney,
    simulateOrangeMoney,
    simulateWave,
    simulateAfricasTalkingSms,
  } = useLedgerStore();

  const [phone, setPhone] = useState('254712345678');
  const [amount, setAmount] = useState('50.00');
  const [isProcessing, setIsProcessing] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  const handleTestDaraja = async () => {
    setIsProcessing(true);
    try {
      await simulateDarajaStk({
        phoneNumber: phone,
        amount: parseFloat(amount) || 50.0,
      });
      setNotification(`✓ STK Push successfully simulated for ${phone}: $${amount} credited to Ledger!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTestMoMo = async () => {
    setIsProcessing(true);
    try {
      await simulateMtnMoMo({
        phoneNumber: phone,
        amount: parseFloat(amount) || 50.0,
        currency: 'UGX',
      });
      setNotification(`✓ MTN MoMo RequestToPay payment confirmed for ${phone}!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTestAirtel = async () => {
    setIsProcessing(true);
    try {
      await simulateAirtelMoney({
        phoneNumber: phone,
        amount: parseFloat(amount) || 50.0,
        currency: 'KES',
      });
      setNotification(`✓ Airtel Money USSD prompt confirmed: $${amount} deposited to Ledger!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTestOrange = async () => {
    setIsProcessing(true);
    try {
      await simulateOrangeMoney({
        phoneNumber: phone,
        amount: parseFloat(amount) || 50.0,
        currency: 'XOF',
      });
      setNotification(`✓ Orange Money Web Payment confirmed: $${amount} deposited to Ledger!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTestWave = async () => {
    setIsProcessing(true);
    try {
      await simulateWave({
        phoneNumber: phone,
        amount: parseFloat(amount) || 50.0,
        currency: 'XOF',
      });
      setNotification(`✓ Wave Mobile Money checkout confirmed: $${amount} deposited to Ledger!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTestAT = async () => {
    setIsProcessing(true);
    try {
      const text = `NANOCOOP DEPOSIT ${amount} REF NC${Math.floor(Math.random() * 90000 + 10000)}`;
      await simulateAfricasTalkingSms({
        fromPhone: phone,
        text,
      });
      setNotification(`✓ Inbound SMS receipt parsed & deposited via Africa's Talking Webhook!`);
      setTimeout(() => setNotification(null), 5000);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.headerTitle}>Telecom Gateways & Integrations</Text>
      <Text style={styles.headerSubtitle}>
        Production-ready mobile money connectors. Just supply API keys in .env to go live.
      </Text>

      {notification && (
        <View style={styles.notificationBox}>
          <Text style={styles.notificationText}>{notification}</Text>
        </View>
      )}

      {/* Gateway Cards */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🟢</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Safaricom Daraja M-Pesa</Text>
            <Text style={styles.cardStatus}>STK Push & C2B Paybill Connector • Kenya & East Africa</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          Direct USSD PIN prompt on member phones. Auto-deposits upon confirmed callback.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>SHORTCODE: 174379</Text>
          <Text style={styles.badge}>ENV: SANDBOX/LIVE</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🟡</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>MTN Mobile Money (MoMo)</Text>
            <Text style={styles.cardStatus}>Collections Open API • Uganda, Ghana, Rwanda, Nigeria</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          RequestToPay collection prompts with automatic status polling and webhook deduplication.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>PRODUCT: COLLECTIONS</Text>
          <Text style={styles.badge}>X-REFERENCE-ID: UUID v4</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🔴</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Airtel Money Africa</Text>
            <Text style={styles.cardStatus}>USSD Push & Merchant API • 14 African Countries</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          Direct merchant collection push prompt on Airtel subscribers with instant settlement.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>PRODUCT: MERCHANTPAY</Text>
          <Text style={styles.badge}>ENV: STAGING/PROD</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🟠</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Orange Money Africa</Text>
            <Text style={styles.cardStatus}>Web Payment & USSD • Francophone Africa</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          Secure Web Payment session generation and instant callback notification processing.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>API: OM-WEBPAY</Text>
          <Text style={styles.badge}>CURRENCY: XOF/XAF</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🌊</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Wave Mobile Money</Text>
            <Text style={styles.cardStatus}>Instant QR & Mobile Checkout • West Africa</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          Fast Wave checkout sessions with cryptographically verified HMAC-SHA256 webhooks.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>AUTH: HMAC-SHA256</Text>
          <Text style={styles.badge}>ENV: LIVE/SANDBOX</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardIcon}>🔵</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Africa's Talking Cloud SMS</Text>
            <Text style={styles.cardStatus}>2G Feature Phone SMS Gateway & Webhooks</Text>
          </View>
        </View>
        <Text style={styles.cardDesc}>
          Parses incoming mobile money SMS receipts and sends outbound cryptographic passbook statements.
        </Text>
        <View style={styles.configBadges}>
          <Text style={styles.badge}>WEBHOOK: /api/v1/integrations/africas-talking/inbound</Text>
        </View>
      </View>

      {/* Interactive Simulator Card */}
      <View style={[styles.card, { borderColor: '#3B82F6' }]}>
        <Text style={styles.cardTitle}>Interactive Integration Tester</Text>
        <Text style={styles.helperText}>
          Test live callback handlers and event ledger auto-crediting with 1-click simulations.
        </Text>

        <Text style={styles.inputLabel}>Mobile Phone Number</Text>
        <TextInput
          style={styles.input}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
        />

        <Text style={styles.inputLabel}>Deposit Amount (USD)</Text>
        <TextInput
          style={styles.input}
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
        />

        <View style={styles.buttonStack}>
          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#16A34A' }]}
            onPress={handleTestDaraja}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate Safaricom M-Pesa STK Push</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#D97706', marginTop: 8 }]}
            onPress={handleTestMoMo}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate MTN MoMo Payment</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#DC2626', marginTop: 8 }]}
            onPress={handleTestAirtel}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate Airtel Money USSD Push</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#EA580C', marginTop: 8 }]}
            onPress={handleTestOrange}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate Orange Money Payment</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#0284C7', marginTop: 8 }]}
            onPress={handleTestWave}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate Wave Mobile Money</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.simButton, { backgroundColor: '#2563EB', marginTop: 8 }]}
            onPress={handleTestAT}
            disabled={isProcessing}
          >
            <Text style={styles.simButtonText}>Simulate Africa's Talking Inbound SMS</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginBottom: 16,
  },
  notificationBox: {
    backgroundColor: 'rgba(59, 130, 246, 0.15)',
    borderColor: '#3B82F6',
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  notificationText: {
    color: '#60A5FA',
    fontSize: 13,
    fontWeight: '600',
  },
  card: {
    backgroundColor: '#0F172A',
    borderColor: '#1E293B',
    borderWidth: 1,
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardIcon: {
    fontSize: 20,
    marginRight: 10,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  cardStatus: {
    fontSize: 11,
    color: '#10B981',
    fontWeight: '500',
  },
  cardDesc: {
    fontSize: 13,
    color: '#94A3B8',
    lineHeight: 18,
    marginBottom: 10,
  },
  configBadges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  badge: {
    backgroundColor: '#1E293B',
    color: '#CBD5E1',
    fontSize: 10,
    fontWeight: '600',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginRight: 6,
    marginBottom: 4,
  },
  helperText: {
    fontSize: 12,
    color: '#94A3B8',
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 12,
    color: '#94A3B8',
    marginBottom: 4,
    marginTop: 8,
  },
  input: {
    backgroundColor: '#1E293B',
    borderColor: '#334155',
    borderWidth: 1,
    borderRadius: 8,
    color: '#F8FAFC',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  buttonStack: {
    marginTop: 16,
  },
  simButton: {
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  simButtonText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
});
