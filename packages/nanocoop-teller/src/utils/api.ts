export interface EventPayload {
  amount: number;
  currency: string;
  user_public_key: string;
  reference?: string;
  notes?: string;
  loan_id?: string;
  interest_rate?: number;
  term_months?: number;
}

export interface EventSignatures {
  teller_sig: string;
  user_sig?: string | null;
}

export interface EventModel {
  event_id: string;
  timestamp: number;
  event_type:
    | 'DEPOSIT_CASH'
    | 'WITHDRAWAL_CASH'
    | 'DEPOSIT_MOBILE_MONEY'
    | 'LOAN_DISBURSED'
    | 'LOAN_REPAID'
    | 'SOCIAL_FUND_CONTRIBUTION'
    | 'SOCIAL_FUND_PAYOUT'
    | 'INTEREST_APPLIED';
  payload: EventPayload;
  previous_hash: string;
  signatures: EventSignatures;
  current_hash: string;
}

export interface AccountState {
  user_public_key: string;
  current_balance: number;
  savings_balance?: number;
  loan_balance?: number;
  social_fund_contributions?: number;
  net_balance?: number;
  last_activity: number | null;
  currency: string;
}

export interface CommunityStats {
  total_balance: number;
  total_savings?: number;
  total_loans_outstanding?: number;
  total_social_fund?: number;
  total_capital?: number;
  total_members: number;
  total_events: number;
  merkle_root: string;
  is_chain_valid: boolean;
}

export interface AuditVerification {
  is_valid: boolean;
  total_events: number;
  merkle_root: string;
  last_hash: string;
  tamper_details?: string | null;
}

export interface PaginatedEvents {
  events: EventModel[];
  next_cursor: number | null;
  has_more: boolean;
  total_count: number;
}

const DEFAULT_API_URL =
  (process.env as Record<string, string | undefined>).EXPO_PUBLIC_API_URL ||
  'http://localhost:8000';

export class NanoCoopApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl || DEFAULT_API_URL).replace(/\/+$/, '');
  }

  public async getStats(): Promise<CommunityStats> {
    const res = await fetch(`${this.baseUrl}/api/v1/stats`);
    if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
    return await res.json();
  }

  public async getEvents(cursor?: number, limit: number = 50): Promise<PaginatedEvents> {
    const url = new URL(`${this.baseUrl}/api/v1/events`);
    if (cursor) url.searchParams.set('cursor', cursor.toString());
    url.searchParams.set('limit', limit.toString());

    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`Failed to fetch events: ${res.statusText}`);
    return await res.json();
  }

  public async getBalance(userPublicKey: string): Promise<AccountState> {
    const res = await fetch(`${this.baseUrl}/api/v1/balance/${userPublicKey}`);
    if (!res.ok) throw new Error(`Failed to fetch balance: ${res.statusText}`);
    return await res.json();
  }

  public async getAllAccounts(): Promise<Record<string, AccountState>> {
    const res = await fetch(`${this.baseUrl}/api/v1/accounts`);
    if (!res.ok) throw new Error(`Failed to fetch accounts: ${res.statusText}`);
    return await res.json();
  }

  public async createEvent(event: EventModel): Promise<EventModel> {
    const res = await fetch(`${this.baseUrl}/api/v1/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Failed to create event: ${res.status}`);
    }
    return await res.json();
  }

  public async verifyAudit(): Promise<AuditVerification> {
    const res = await fetch(`${this.baseUrl}/api/v1/audit/verify`);
    if (!res.ok) throw new Error(`Failed to verify audit: ${res.statusText}`);
    return await res.json();
  }

  public async verifyChain(): Promise<AuditVerification> {
    return this.verifyAudit();
  }
}
