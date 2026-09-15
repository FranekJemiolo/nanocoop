import { TelecomSmsParser } from '../src/receiver/parser';

describe('TelecomSmsParser', () => {
  it('parses M-Pesa transaction receipts', () => {
    const msg = 'QA12BC34DE Confirmed. You have received USD 50.00 from John Doe 254712345678 on 15/09/2026.';
    const parsed = TelecomSmsParser.parse(msg);

    expect(parsed).not.toBeNull();
    expect(parsed?.transactionCode).toBe('QA12BC34DE');
    expect(parsed?.amount).toBe(50.0);
    expect(parsed?.currency).toBe('USD');
    expect(parsed?.senderPhone).toBe('+254712345678');
    expect(parsed?.provider).toBe('MPESA');
  });

  it('parses MTN Mobile Money receipts', () => {
    const msg = 'You have received 75.25 USD from Alice Smith (256772998877). Transaction ID: MTN112233.';
    const parsed = TelecomSmsParser.parse(msg);

    expect(parsed).not.toBeNull();
    expect(parsed?.transactionCode).toBe('MTN112233');
    expect(parsed?.amount).toBe(75.25);
    expect(parsed?.currency).toBe('USD');
    expect(parsed?.senderPhone).toBe('+256772998877');
    expect(parsed?.provider).toBe('MTN_MOMO');
  });

  it('parses Airtel Money receipts', () => {
    const msg = 'Txn ID: AIR445566. Received USD 30.00 from +254733112233.';
    const parsed = TelecomSmsParser.parse(msg);

    expect(parsed).not.toBeNull();
    expect(parsed?.transactionCode).toBe('AIR445566');
    expect(parsed?.amount).toBe(30.0);
    expect(parsed?.currency).toBe('USD');
    expect(parsed?.senderPhone).toBe('+254733112233');
    expect(parsed?.provider).toBe('AIRTEL');
  });

  it('parses generic receipts', () => {
    const msg = 'Confirmed: You received $10 from +123456789';
    const parsed = TelecomSmsParser.parse(msg);

    expect(parsed).not.toBeNull();
    expect(parsed?.amount).toBe(10);
    expect(parsed?.currency).toBe('USD');
    expect(parsed?.senderPhone).toBe('+123456789');
    expect(parsed?.provider).toBe('GENERIC');
  });

  it('ignores spam or non-banking SMS', () => {
    const spam = 'Hey are you coming to lunch today?';
    expect(TelecomSmsParser.parse(spam)).toBeNull();
  });
});
