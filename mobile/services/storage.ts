import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

class StorageService {
    async setItem(key: string, value: string): Promise<void> {
        try {
            if (Platform.OS === 'web') {
                localStorage.setItem(key, value);
            } else {
                await AsyncStorage.setItem(key, value);
            }
        } catch (error) {
            console.error(`Error saving ${key} to storage`, error);
        }
    }

    async getItem(key: string): Promise<string | null> {
        try {
            if (Platform.OS === 'web') {
                return localStorage.getItem(key);
            } else {
                return await AsyncStorage.getItem(key);
            }
        } catch (error) {
            console.error(`Error getting ${key} from storage`, error);
            return null;
        }
    }

    async removeItem(key: string): Promise<void> {
        try {
            if (Platform.OS === 'web') {
                localStorage.removeItem(key);
            } else {
                await AsyncStorage.removeItem(key);
            }
        } catch (error) {
            console.error(`Error removing ${key} from storage`, error);
        }
    }
}

export default new StorageService();
