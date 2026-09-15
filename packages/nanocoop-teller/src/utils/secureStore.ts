import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const memoryFallback: Record<string, string> = {};

export class SecureStorage {
  /**
   * Save a key-value pair securely using hardware keychain/keystore on iOS/Android.
   */
  public static async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.setItem(key, value);
          return;
        }
      } catch {
        // Fallback to memory
      }
      memoryFallback[key] = value;
      return;
    }

    try {
      await SecureStore.setItemAsync(key, value, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED,
      });
    } catch {
      memoryFallback[key] = value;
    }
  }

  /**
   * Retrieve a securely stored value.
   */
  public static async getItem(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          return window.localStorage.getItem(key);
        }
      } catch {
        // Fallback to memory
      }
      return memoryFallback[key] ?? null;
    }

    try {
      return await SecureStore.getItemAsync(key);
    } catch {
      return memoryFallback[key] ?? null;
    }
  }

  /**
   * Delete a securely stored key.
   */
  public static async deleteItem(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        if (typeof window !== 'undefined' && window.localStorage) {
          window.localStorage.removeItem(key);
          return;
        }
      } catch {
        // Fallback
      }
      delete memoryFallback[key];
      return;
    }

    try {
      await SecureStore.deleteItemAsync(key);
    } catch {
      delete memoryFallback[key];
    }
  }
}
