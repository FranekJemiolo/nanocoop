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

export const VslaScreen: React.FC = () => {
  const {
    communityStats,
    accounts,
    sampleMembers,
    disburseLoan,
    repayLoan,
    contributeSocialFund,
    payoutSocialFund,
    isDemoMode,
  } = useLedgerStore();

  const [activeSegment, setActiveSegment] = useState<'disburse' | 'repay' | 'welfare'>('disburse');
  const [selectedMemberIndex, setSelectedMemberIndex] = useState(0);
  const [amount, setAmount] = useState('100.00');
  const [interestRate, setInterestRate] = useState('5.0');
  const [termMonths, setTermMonths] = useState('3');
  const [notes, setNotes] = useState('Crop planting input loan');
  const [welfarePurpose, setWelfarePurpose] = useState('Clinic medical prescription assistance');
  const [isProcessing, setIsProcessing] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const currentMember = sampleMembers[selectedMemberIndex] || sampleMembers[0];
  const memberAccount = accounts[currentMember?.publicKey] || {
    current_balance: 0,
    savings_balance: 0,
    loan_balance: 0,
    social_fund_contributions: 0,
    net_balance: 0,
  };

  const handleDisburseLoan = async () => {
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid loan principal amount');
      return;
    }
    setIsProcessing(true);
    try {
      await disburseLoan({
        amount: numAmount,
        borrowerPublicKey: currentMember.publicKey,
        borrowerPrivateKeyHex: currentMember.privateKey,
        interestRate: parseFloat(interestRate) || 5.0,
        termMonths: parseInt(termMonths, 10) || 3,
        notes,
      });
      setSuccessMessage(`Disbursed loan of $${numAmount.toFixed(2)} to ${currentMember.name}`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Loan disbursement failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRepayLoan = async () => {
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid repayment amount');
      return;
    }
    setIsProcessing(true);
    try {
      await repayLoan({
        amount: numAmount,
        borrowerPublicKey: currentMember.publicKey,
        borrowerPrivateKeyHex: currentMember.privateKey,
        notes: 'Monthly installment payment',
      });
      setSuccessMessage(`Repaid $${numAmount.toFixed(2)} for ${currentMember.name}`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Loan repayment failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleContributeSocial = async () => {
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid contribution');
      return;
    }
    setIsProcessing(true);
    try {
      await contributeSocialFund({
        amount: numAmount,
        memberPublicKey: currentMember.publicKey,
        memberPrivateKeyHex: currentMember.privateKey,
        notes: 'Weekly social fund safety net contribution',
      });
      setSuccessMessage(`Contributed $${numAmount.toFixed(2)} to Welfare Emergency Safety Net`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Contribution failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePayoutSocial = async () => {
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid payout grant amount');
      return;
    }
    setIsProcessing(true);
    try {
      await payoutSocialFund({
        amount: numAmount,
        memberPublicKey: currentMember.publicKey,
        memberPrivateKeyHex: currentMember.privateKey,
        purpose: welfarePurpose,
      });
      setSuccessMessage(`Emergency relief grant of $${numAmount.toFixed(2)} issued to ${currentMember.name}`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Welfare grant failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Overview Cards */}
      <View style={styles.metricsRow}>
        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>Total Savings</Text>
          <Text style={styles.metricValue}>
            ${(communityStats?.total_savings ?? communityStats?.total_balance ?? 0).toFixed(2)}
          </Text>
        </View>

        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>Loans Outstanding</Text>
          <Text style={[styles.metricValue, { color: '#F59E0B' }]}>
            ${(communityStats?.total_loans_outstanding ?? 0).toFixed(2)}
          </Text>
        </View>
      </View>

      <View style={styles.metricsRow}>
        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>Social Fund (Safety Net)</Text>
          <Text style={[styles.metricValue, { color: '#10B981' }]}>
            ${(communityStats?.total_social_fund ?? 0).toFixed(2)}
          </Text>
        </View>

        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>Cooperative Capital</Text>
          <Text style={[styles.metricValue, { color: '#6366F1' }]}>
            ${(communityStats?.total_capital ?? communityStats?.total_balance ?? 0).toFixed(2)}
          </Text>
        </View>
      </View>

      {successMessage && (
        <View style={styles.successBanner}>
          <Text style={styles.successText}>✓ {successMessage}</Text>
        </View>
      )}

      {/* Member Selection */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Selected VSLA Member</Text>
        <View style={styles.memberSelector}>
          {sampleMembers.map((m, idx) => (
            <TouchableOpacity
              key={m.publicKey}
              style={[
                styles.memberPill,
                selectedMemberIndex === idx && styles.memberPillActive,
              ]}
              onPress={() => setSelectedMemberIndex(idx)}
            >
              <Text
                style={[
                  styles.memberPillText,
                  selectedMemberIndex === idx && styles.memberPillTextActive,
                ]}
              >
                {m.name.split(' ')[0]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.memberStatsBox}>
          <View style={styles.statLine}>
            <Text style={styles.statLineLabel}>Savings Balance:</Text>
            <Text style={styles.statLineValue}>
              ${(memberAccount.savings_balance ?? memberAccount.current_balance ?? 0).toFixed(2)}
            </Text>
          </View>
          <View style={styles.statLine}>
            <Text style={styles.statLineLabel}>Outstanding Loan Debt:</Text>
            <Text style={[styles.statLineValue, { color: '#F59E0B' }]}>
              ${(memberAccount.loan_balance ?? 0).toFixed(2)}
            </Text>
          </View>
          <View style={styles.statLine}>
            <Text style={styles.statLineLabel}>Welfare Contributions:</Text>
            <Text style={styles.statLineValue}>
              ${(memberAccount.social_fund_contributions ?? 0).toFixed(2)}
            </Text>
          </View>
          <View style={styles.statLine}>
            <Text style={styles.statLineLabel}>Net Position:</Text>
            <Text style={[styles.statLineValue, { color: '#38BDF8', fontWeight: 'bold' }]}>
              ${(memberAccount.net_balance ?? 0).toFixed(2)}
            </Text>
          </View>
        </View>
      </View>

      {/* Segment Selector */}
      <View style={styles.segmentContainer}>
        <TouchableOpacity
          style={[styles.segmentBtn, activeSegment === 'disburse' && styles.segmentBtnActive]}
          onPress={() => {
            setActiveSegment('disburse');
            setAmount('150.00');
          }}
        >
          <Text
            style={[styles.segmentBtnText, activeSegment === 'disburse' && styles.segmentBtnTextActive]}
          >
            Disburse Loan
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segmentBtn, activeSegment === 'repay' && styles.segmentBtnActive]}
          onPress={() => {
            setActiveSegment('repay');
            setAmount('50.00');
          }}
        >
          <Text
            style={[styles.segmentBtnText, activeSegment === 'repay' && styles.segmentBtnTextActive]}
          >
            Repay Loan
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.segmentBtn, activeSegment === 'welfare' && styles.segmentBtnActive]}
          onPress={() => {
            setActiveSegment('welfare');
            setAmount('5.00');
          }}
        >
          <Text
            style={[styles.segmentBtnText, activeSegment === 'welfare' && styles.segmentBtnTextActive]}
          >
            Social Fund
          </Text>
        </TouchableOpacity>
      </View>

      {/* Action Forms */}
      {activeSegment === 'disburse' && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Disburse Cooperative Micro-Loan</Text>
          <Text style={styles.helperText}>
            Requires dual Ed25519 signature: Teller Hardware Key + Borrower NFC Card.
          </Text>

          <Text style={styles.inputLabel}>Principal Amount (USD)</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
          />

          <View style={styles.inputRow}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <Text style={styles.inputLabel}>Interest Rate (%)</Text>
              <TextInput
                style={styles.input}
                value={interestRate}
                onChangeText={setInterestRate}
                keyboardType="numeric"
              />
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Text style={styles.inputLabel}>Term (Months)</Text>
              <TextInput
                style={styles.input}
                value={termMonths}
                onChangeText={setTermMonths}
                keyboardType="numeric"
              />
            </View>
          </View>

          <Text style={styles.inputLabel}>Purpose / Notes</Text>
          <TextInput
            style={styles.input}
            value={notes}
            onChangeText={setNotes}
          />

          <TouchableOpacity
            style={[styles.actionBtn, isProcessing && styles.btnDisabled]}
            onPress={handleDisburseLoan}
            disabled={isProcessing}
          >
            <Text style={styles.actionBtnText}>
              {isProcessing ? 'Cryptographically Signing...' : '✍️ Dual-Sign & Disburse Loan'}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {activeSegment === 'repay' && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Record Loan Repayment</Text>
          <Text style={styles.helperText}>
            Reduces borrower debt and returns capital to cooperative lending pool.
          </Text>

          <Text style={styles.inputLabel}>Repayment Amount (USD)</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
          />

          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#10B981' }, isProcessing && styles.btnDisabled]}
            onPress={handleRepayLoan}
            disabled={isProcessing}
          >
            <Text style={styles.actionBtnText}>
              {isProcessing ? 'Processing...' : '💳 Authorize & Repay Loan'}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {activeSegment === 'welfare' && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Social Emergency Safety Net</Text>
          <Text style={styles.helperText}>
            Fixed community solidarity fund for medical, funeral, and emergency support.
          </Text>

          <Text style={styles.inputLabel}>Amount (USD)</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
          />

          <View style={{ flexDirection: 'row', marginTop: 12 }}>
            <TouchableOpacity
              style={[styles.halfBtn, { backgroundColor: '#4F46E5', marginRight: 6 }]}
              onPress={handleContributeSocial}
              disabled={isProcessing}
            >
              <Text style={styles.halfBtnText}>+ Contribute to Safety Net</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.halfBtn, { backgroundColor: '#DC2626', marginLeft: 6 }]}
              onPress={handlePayoutSocial}
              disabled={isProcessing}
            >
              <Text style={styles.halfBtnText}>- Emergency Relief Grant</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
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
  metricsRow: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  metricCard: {
    flex: 1,
    backgroundColor: '#0F172A',
    borderColor: '#1E293B',
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 4,
  },
  metricLabel: {
    fontSize: 11,
    color: '#94A3B8',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  metricValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  successBanner: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: '#10B981',
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  successText: {
    color: '#34D399',
    fontSize: 13,
    fontWeight: '600',
  },
  card: {
    backgroundColor: '#0F172A',
    borderColor: '#1E293B',
    borderWidth: 1,
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 4,
  },
  helperText: {
    fontSize: 12,
    color: '#94A3B8',
    marginBottom: 12,
  },
  memberSelector: {
    flexDirection: 'row',
    marginVertical: 10,
  },
  memberPill: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 20,
    backgroundColor: '#1E293B',
    marginRight: 8,
  },
  memberPillActive: {
    backgroundColor: '#6366F1',
  },
  memberPillText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  memberPillTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  memberStatsBox: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 12,
    marginTop: 6,
  },
  statLine: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 3,
  },
  statLineLabel: {
    color: '#94A3B8',
    fontSize: 13,
  },
  statLineValue: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '500',
  },
  segmentContainer: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderRadius: 10,
    padding: 4,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  segmentBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  segmentBtnActive: {
    backgroundColor: '#2563EB',
  },
  segmentBtnText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  segmentBtnTextActive: {
    color: '#FFFFFF',
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
  inputRow: {
    flexDirection: 'row',
  },
  actionBtn: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 16,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  btnDisabled: {
    opacity: 0.5,
  },
  halfBtn: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  halfBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
});
