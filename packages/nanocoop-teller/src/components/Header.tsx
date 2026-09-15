import React, { useCallback } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useLedgerStore } from '../store/useLedgerStore';

export const Header: React.FC = React.memo(() => {
  const { isOnline, pendingQueue, flushPendingQueue, tellerKeyPair, setOnlineStatus } =
    useLedgerStore();

  const handleSync = useCallback(async () => {
    await flushPendingQueue();
  }, [flushPendingQueue]);

  const toggleNetwork = useCallback(() => {
    setOnlineStatus(!isOnline);
  }, [isOnline, setOnlineStatus]);

  const shortTellerKey = tellerKeyPair?.publicKeyHex
    ? `${tellerKeyPair.publicKeyHex.substring(0, 6)}...${tellerKeyPair.publicKeyHex.substring(58)}`
    : 'Initializing...';

  return (
    <View style={styles.headerContainer}>
      <View style={styles.topRow}>
        <View>
          <View style={styles.logoRow}>
            <View style={styles.logoIcon}>
              <Text style={styles.logoLetter}>N</Text>
            </View>
            <Text style={styles.title}>NanoCoop</Text>
            <View style={styles.badgeCoop}>
              <Text style={styles.badgeCoopText}>VSLA Core</Text>
            </View>
          </View>
          <Text style={styles.subtitle}>Teller Node: {shortTellerKey}</Text>
        </View>

        <View style={styles.statusRow}>
          <TouchableOpacity
            style={[styles.networkBadge, isOnline ? styles.badgeOnline : styles.badgeOffline]}
            onPress={toggleNetwork}
            activeOpacity={0.7}
          >
            <View
              style={[styles.statusDot, isOnline ? styles.dotOnline : styles.dotOffline]}
            />
            <Text
              style={[styles.statusText, isOnline ? styles.textOnline : styles.textOffline]}
            >
              {isOnline ? 'Online' : 'Offline Mode'}
            </Text>
          </TouchableOpacity>

          {pendingQueue.length > 0 && (
            <TouchableOpacity style={styles.syncButton} onPress={handleSync} activeOpacity={0.8}>
              <Text style={styles.syncButtonText}>
                Sync ({pendingQueue.length})
              </Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
});

Header.displayName = 'Header';

const styles = StyleSheet.create({
  headerContainer: {
    backgroundColor: '#0F172A',
    paddingTop: 48,
    paddingBottom: 16,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: '#10B981',
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoLetter: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: '#F8FAFC',
    letterSpacing: -0.5,
  },
  badgeCoop: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  badgeCoopText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#34D399',
    textTransform: 'uppercase',
  },
  subtitle: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 4,
    fontFamily: 'monospace',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  networkBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
  },
  badgeOnline: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  badgeOffline: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: 'rgba(239, 68, 68, 0.4)',
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginRight: 6,
  },
  dotOnline: {
    backgroundColor: '#10B981',
  },
  dotOffline: {
    backgroundColor: '#EF4444',
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  textOnline: {
    color: '#34D399',
  },
  textOffline: {
    color: '#F87171',
  },
  syncButton: {
    backgroundColor: '#3B82F6',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  syncButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
});
