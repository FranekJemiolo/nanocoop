import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { SafeAreaView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Header } from './src/components/Header';
import { DashboardScreen } from './src/screens/DashboardScreen';
import { TransactionScreen } from './src/screens/TransactionScreen';
import { AuditScreen } from './src/screens/AuditScreen';
import { useLedgerStore } from './src/store/useLedgerStore';

export default function App() {
  const { activeTab, setActiveTab, initTellerKeys, fetchRemoteState } = useLedgerStore();

  useEffect(() => {
    initTellerKeys();
    fetchRemoteState();
  }, [initTellerKeys, fetchRemoteState]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <Header />

      <View style={styles.body}>
        {activeTab === 'dashboard' && <DashboardScreen />}
        {activeTab === 'transaction' && <TransactionScreen />}
        {activeTab === 'audit' && <AuditScreen />}
      </View>

      {/* Bottom Tab Navigation */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'dashboard' && styles.tabItemActive]}
          onPress={() => setActiveTab('dashboard')}
          activeOpacity={0.7}
        >
          <Text style={styles.tabIcon}>📊</Text>
          <Text
            style={[styles.tabLabel, activeTab === 'dashboard' && styles.tabLabelActive]}
          >
            Dashboard
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'transaction' && styles.tabItemActive]}
          onPress={() => setActiveTab('transaction')}
          activeOpacity={0.7}
        >
          <Text style={styles.tabIcon}>⚡</Text>
          <Text
            style={[styles.tabLabel, activeTab === 'transaction' && styles.tabLabelActive]}
          >
            Transact
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'audit' && styles.tabItemActive]}
          onPress={() => setActiveTab('audit')}
          activeOpacity={0.7}
        >
          <Text style={styles.tabIcon}>🛡️</Text>
          <Text
            style={[styles.tabLabel, activeTab === 'audit' && styles.tabLabelActive]}
          >
            Audit
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  body: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingVertical: 10,
    paddingBottom: 16,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabItemActive: {
    opacity: 1,
  },
  tabIcon: {
    fontSize: 18,
    marginBottom: 4,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
  },
  tabLabelActive: {
    color: '#10B981',
  },
});
