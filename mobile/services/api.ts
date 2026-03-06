import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Nota: Para probar en el simulador puedes usar tu IP o 10.0.2.2 en Android / localhost en iOS
// Asumiremos localhost para desarrollo iOS y Web, 10.0.2.2 para Android Emuladores o la IP local 10.0.0.6
export const API_URL = 'http://localhost:5039/api';

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use(
    async (config) => {
        const token = await AsyncStorage.getItem('jwt_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

export default api;
