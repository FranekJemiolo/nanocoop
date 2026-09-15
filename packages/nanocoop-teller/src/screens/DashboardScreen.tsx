import React, { memo, useCallback, useMemo } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLedgerStore } from '../store/useLedgerStore';
import { EventModel } from '../utils/api';

interface EventItemProps {
  event: EventModel;
}

const EventListItem = memo(({ event }: EventItemProps) => {
  const isDeposit =
    event.event_type === 'DEPOSIT_CASH' || event.event_type === 'DEPOSIT_MOBILE_MONEY';
  const isMobile = event.event_type === 'DEPOSIT_MOBILE_MONEY';

  const shortUser = event.payload.user_public_key
    ? `${event.payload.user_public_key.substring(0, 6)}...${event.payload.user_public_key.substring(58)}`
    : 'Unknown';

  const shortHash = `${event.current_hash.substring(0, 8)}...${event.current_hash.substring(56)}`;

  const formattedDate = useMemo(() => {
    return new Date(event.timestamp * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  }, [event.timestamp]);

  return (
    <View style={styles.eventItem}>
      <View style={styles.eventLeft}>
        <View
          style={[
            styles.eventIcon,
            isDeposit ? styles.depositIcon : styles.withdrawalIcon,
          ]}
        >
          <Text
            style={[
              styles.eventIconText,
              isDeposit ? styles.depositText : styles.withdrawalText,
            ]}
          >
            {isDeposit ? '+' : '-'}
          </Text>
        </View>
        <View>
          <View style={styles.typeBadgeRow}>
            <Text style={styles.eventTypeTitle}>
              {event.event_type.replace('_', ' ')}
            </Text>
            {isMobile && (
              <View style={styles.smsTag}>
                <Text style={styles.smsTagText}>SMS</Text>
              </View>
            )}
          </View>
          <Text style={styles.eventSub}>Member: {shortUser}</Text>
          <Text style={styles.hashSub}>Hash: {shortHash}</Text>
        </View>
      </View>

      <View style={styles.eventRight}>
        <Text
          style={[
            styles.eventAmount,
            isDeposit ? styles.depositAmount : styles.withdrawalAmount,
          ]}
        >
          {isDeposit ? '+' : '-'}${event.payload.amount.toFixed(2)}
        </Text>
        <Text style={styles.eventTime}>{formattedDate}</Text>
      </View>
    </View>
  );
});

EventListItem.displayName = 'EventListItem';

export const DashboardScreen: React.FC = memo(() => {
  const {
    communityStats,
    events,
    isLoading,
    fetchRemoteState,
    setActiveTab,
    isOnline,
  } = useLedgerStore();

  const handleRefresh = useCallback(() => {
    fetchRemoteState();
  }, [fetchRemoteState]);

  const recentEvents = useMemo(() => {
    return [...events].reverse();
  }, [events]);

  const renderItem = useCallback(
    ({ item }: { item: EventModel }) => <EventListItem event={item} />,
    []
  );

  const keyExtractor = useCallback((item: EventModel) => item.event_id, []);

  const formattedBalance = useMemo(() => {
    return communityStats ? `$${communityStats.total_balance.toFixed(2)}` : '$0.00';
  }, [communityStats]);

  return (
    <View style={styles.container}>
      {/* Community Balance Card */}
      <View style={styles.vaultCard}>
        <View style={styles.cardHeader}>
          <Text style={styles.vaultLabel}>COMMUNITY VAULT BALANCE</Text>
          <View
            style={[
              styles.verifiedBadge,
              communityStats?.is_chain_valid
                ? styles.badgeVerified
                : styles.badgeUnverified,
            ]}
          >
            <Text
              style={[
                styles.verifiedText,
                communityStats?.is_chain_valid
                  ? styles.textVerified
                  : styles.textUnverified,
              ]}
            >
              {communityStats?.is_chain_valid ? 'Chain Verified' : 'Checking'}
            </Text>
          </View>
        </View>

        <Text style={styles.balanceText}>{formattedBalance}</Text>
        <Text style={styles.currencySubtitle}>United States Dollar (USD)</Text>

        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>
              {communityStats?.total_members || 0}
            </Text>
            <Text style={styles.statLabel}>Members</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statBox}>
            <Text style={styles.statValue}>
              {communityStats?.total_events || 0}
            </Text>
            <Text style={styles.statLabel}>Events</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statBox}>
            <Text style={styles.statValue}>
              {communityStats?.merkle_root
                ? `${communityStats.merkle_root.substring(0, 6)}...`
                : 'Genesis'}
            </Text>
            <Text style={styles.statLabel}>Merkle Root</Text>
          </View>
        </View>
      </View>

      {/* Action Buttons */}
      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={[styles.actionBtn, styles.depositBtn]}
          onPress={() => setActiveTab('transaction')}
          activeOpacity={0.8}
        >
          <Text style={styles.depositBtnText}>+ Deposit Cash</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.withdrawBtn]}
          onPress={() => setActiveTab('transaction')}
          activeOpacity={0.8}
        >
          <Text style={styles.withdrawBtnText}>- Withdraw Cash</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.auditBtn]}
          onPress={() => setActiveTab('audit')}
          activeOpacity={0.8}
        >
          <Text style={styles.auditBtnText}>Audit</Text>
        </TouchableOpacity>
      </View>

      {/* Recent Activity Header */}
      <View style={styles.listHeader}>
        <Text style={styles.listTitle}>Immutable Event Log</Text>
        <Text style={styles.listSubtitle}>
          {recentEvents.length} transactions recorded
        </Text>
      </View>

      {/* Event Stream */}
      <FlatList
        data={recentEvents}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={handleRefresh}
            tintColor="#10B981"
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyTitle}>No Transactions Yet</Text>
            <Text style={styles.emptyText}>
              {isOnline
                ? 'Create a deposit or await an SMS payment to start the ledger.'
                : 'Offline mode active. Offline transactions will queue here.'}
            </Text>
          </View>
        }
      />
    </View>
  );
});

DashboardScreen.displayName = 'DashboardScreen';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  vaultCard: {
    backgroundColor: '#131B2E',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  vaultLabel: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
  },
  verifiedBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  badgeVerified: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
  },
  badgeUnverified: {
    backgroundColor: 'rgba(234, 179, 8, 0.15)',
  },
  verifiedText: {
    fontSize: 11,
    fontWeight: '700',
  },
  textVerified: {
    color: '#34D399',
  },
  textUnverified: {
    color: '#FBBF24',
  },
  balanceText: {
    color: '#F8FAFC',
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  currencySubtitle: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 2,
    marginBottom: 18,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0F172A',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  statBox: {
    alignItems: 'center',
    flex: 1,
  },
  statDivider: {
    width: 1,
    height: 24,
    backgroundColor: '#1E293B',
  },
  statValue: {
    color: '#F1F5F9',
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  statLabel: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '600',
    marginTop: 2,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 20,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  depositBtn: {
    backgroundColor: '#10B981',
  },
  depositBtnText: {
    color: '#0F172A',
    fontWeight: '700',
    fontSize: 13,
  },
  withdrawBtn: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
  },
  withdrawBtnText: {
    color: '#F8FAFC',
    fontWeight: '700',
    fontSize: 13,
  },
  auditBtn: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    flex: 0.7,
  },
  auditBtnText: {
    color: '#38BDF8',
    fontWeight: '700',
    fontSize: 13,
  },
  listHeader: {
    marginBottom: 10,
  },
  listTitle: {
    color: '#F8FAFC',
    fontSize: 15,
    fontWeight: '700',
  },
  listSubtitle: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 2,
  },
  listContent: {
    paddingBottom: 40,
  },
  eventItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1F2937',
  },
  eventLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  eventIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    justifyContent: 'center',
    alignItems: 'center',
  },
  depositIcon: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
  },
  withdrawalIcon: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
  },
  eventIconText: {
    fontWeight: 'bold',
    fontSize: 16,
  },
  depositText: {
    color: '#34D399',
  },
  withdrawalText: {
    color: '#F87171',
  },
  typeBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  eventTypeTitle: {
    color: '#F3F4F6',
    fontSize: 12,
    fontWeight: '700',
  },
  smsTag: {
    backgroundColor: '#0284C7',
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 4,
  },
  smsTagText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '800',
  },
  eventSub: {
    color: '#9CA3AF',
    fontSize: 10,
    marginTop: 2,
    fontFamily: 'monospace',
  },
  hashSub: {
    color: '#6B7280',
    fontSize: 9,
    fontFamily: 'monospace',
  },
  eventRight: {
    alignItems: 'flex-end',
  },
  eventAmount: {
    fontSize: 14,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  depositAmount: {
    color: '#34D399',
  },
  withdrawalAmount: {
    color: '#F87171',
  },
  eventTime: {
    color: '#6B7280',
    fontSize: 10,
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 50,
  },
  emptyTitle: {
    color: '#94A3B8',
    fontSize: 15,
    fontWeight: '600',
  },
  emptyText: {
    color: '#64748B',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 6,
    paddingHorizontal: 30,
  },
});
