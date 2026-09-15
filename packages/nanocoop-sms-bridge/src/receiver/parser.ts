/** Telecom SMS mobile money receipt parsers. */

export interface ParsedSmsReceipt {
  transactionCode: string;
  amount: number;
  currency: string;
  senderPhone: string;
  timestamp: number;
  provider: 'MPESA' | 'MTN_MOMO' | 'AIRTEL' | 'GENERIC';
  rawMessage: string;
}

export class TelecomSmsParser {
  /**
   * Parse incoming SMS message into a structured receipt.
   * Supports M-Pesa, MTN Mobile Money, Airtel Money, and generic receipt patterns.
   */
  public static parse(message: string, timestamp: number = Date.now()): ParsedSmsReceipt | null {
    const trimmed = message.trim();

    // 1. M-Pesa format:
    // e.g. "QA12BC34DE Confirmed. You have received USD 25.00 from Jane Doe 254712345678 on 15/09/2026."
    // or "QA12BC34DE Confirmed. You have received $50.00 from John Doe +254712345678"
    const mpesaRegex = /([A-Z0-9]{8,12})\s+Confirmed\.\s+You have received\s+([A-Z]{3}|\$)?\s*([0-9,.]+)\s+from\s+(?:[A-Za-z\s]+\s+)?(\+?[0-9]{9,15})/i;
    const mpesaMatch = trimmed.match(mpesaRegex);

    if (mpesaMatch) {
      const code = mpesaMatch[1];
      const currency = mpesaMatch[2] === '$' ? 'USD' : (mpesaMatch[2] || 'USD').toUpperCase();
      const amount = parseFloat(mpesaMatch[3].replace(/,/g, ''));
      const phone = mpesaMatch[4];
      return {
        transactionCode: code,
        amount,
        currency,
        senderPhone: phone.startsWith('+') ? phone : `+${phone}`,
        timestamp,
        provider: 'MPESA',
        rawMessage: trimmed,
      };
    }

    // 2. MTN Mobile Money format:
    // e.g. "You have received 40.00 USD from Mary Smith (256772123456). Transaction ID: MTN998877."
    const mtnRegex = /You have received\s+([0-9,.]+)\s*([A-Z]{3}|\$)\s+from\s+[^(]+\(([0-9+]+)\)\.\s+Transaction ID:\s*([A-Z0-9]+)/i;
    const mtnMatch = trimmed.match(mtnRegex);
    if (mtnMatch) {
      const amount = parseFloat(mtnMatch[1].replace(/,/g, ''));
      const currency = mtnMatch[2] === '$' ? 'USD' : mtnMatch[2].toUpperCase();
      const phone = mtnMatch[3];
      const code = mtnMatch[4];
      return {
        transactionCode: code,
        amount,
        currency,
        senderPhone: phone.startsWith('+') ? phone : `+${phone}`,
        timestamp,
        provider: 'MTN_MOMO',
        rawMessage: trimmed,
      };
    }

    // 3. Airtel Money format:
    // e.g. "Txn ID: AIR883321. Received USD 15.50 from +254733000111."
    const airtelRegex = /Txn ID:?\s*([A-Z0-9]+)\.?\s*Received\s*([A-Z]{3}|\$)?\s*([0-9,.]+)\s+from\s+(\+?[0-9]+)/i;
    const airtelMatch = trimmed.match(airtelRegex);
    if (airtelMatch) {
      const code = airtelMatch[1];
      const currency = airtelMatch[2] === '$' ? 'USD' : (airtelMatch[2] || 'USD').toUpperCase();
      const amount = parseFloat(airtelMatch[3].replace(/,/g, ''));
      const phone = airtelMatch[4];
      return {
        transactionCode: code,
        amount,
        currency,
        senderPhone: phone.startsWith('+') ? phone : `+${phone}`,
        timestamp,
        provider: 'AIRTEL',
        rawMessage: trimmed,
      };
    }

    // 4. Generic Mock Telecom format:
    // e.g. "Confirmed: You received $10 from +123456789"
    const genericRegex = /Confirmed:?\s*You received\s*([$A-Z]{1,4})?\s*([0-9,.]+)\s+from\s+(\+?[0-9]+)/i;
    const genericMatch = trimmed.match(genericRegex);
    if (genericMatch) {
      const currSymbol = genericMatch[1] || 'USD';
      const currency = currSymbol === '$' ? 'USD' : currSymbol.toUpperCase();
      const amount = parseFloat(genericMatch[2].replace(/,/g, ''));
      const phone = genericMatch[3];
      // Deterministic synthetic code from phone & amount & timestamp if unstated
      const code = `TX_${Math.abs(amount * 100)}_${phone.replace(/\+/g, '')}`;
      return {
        transactionCode: code,
        amount,
        currency,
        senderPhone: phone.startsWith('+') ? phone : `+${phone}`,
        timestamp,
        provider: 'GENERIC',
        rawMessage: trimmed,
      };
    }

    return null;
  }
}
