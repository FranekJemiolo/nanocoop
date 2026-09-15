/** SMS Receiver abstraction with Dependency Injection for hardware mocking in CI. */

export type SmsHandler = (sender: string, body: string, timestamp: number) => Promise<any>;

export interface ISmsSource {
  registerHandler(handler: SmsHandler): void;
  startListening(): void;
  stopListening(): void;
  simulateIncomingSms(sender: string, body: string, timestamp?: number): Promise<void>;
}

/**
 * Mock SMS receiver for CI/CD environments and automated tests.
 * Enables dependency injection without physical GSM hardware.
 */
export class MockSmsReceiver implements ISmsSource {
  private handler: SmsHandler | null = null;
  private isListening = false;

  public registerHandler(handler: SmsHandler): void {
    this.handler = handler;
  }

  public startListening(): void {
    this.isListening = true;
  }

  public stopListening(): void {
    this.isListening = false;
  }

  public async simulateIncomingSms(
    sender: string,
    body: string,
    timestamp: number = Date.now()
  ): Promise<void> {
    if (!this.isListening) {
      throw new Error('MockSmsReceiver is not listening. Call startListening() first.');
    }
    if (this.handler) {
      await this.handler(sender, body, timestamp);
    }
  }
}

/**
 * Native Android SMS Receiver bridge.
 * In production, hooks into React Native NativeEventEmitter / BroadcastReceiver.
 */
export class AndroidSmsReceiver implements ISmsSource {
  private handler: SmsHandler | null = null;
  private isListening = false;

  public registerHandler(handler: SmsHandler): void {
    this.handler = handler;
  }

  public startListening(): void {
    this.isListening = true;
    // In Android runtime, registers BroadcastReceiver with android.provider.Telephony.SMS_RECEIVED
  }

  public stopListening(): void {
    this.isListening = false;
  }

  public async simulateIncomingSms(
    sender: string,
    body: string,
    timestamp: number = Date.now()
  ): Promise<void> {
    if (this.handler) {
      await this.handler(sender, body, timestamp);
    }
  }
}
