import axios from 'axios';
import storageService from './storage';

// Nota: Para probar en el simulador puedes usar tu IP o 10.0.2.2 en Android / localhost en iOS
// Local Wi-Fi IP usada para el dispositivo físico:
export const API_URL = 'http://10.0.0.6:5039/api';

const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use(
    async (config) => {
        const token = await storageService.getItem('jwt_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        const empresaRaw = await storageService.getItem('empresa');
        if (empresaRaw) {
            try {
                const empresa = JSON.parse(empresaRaw);
                if (empresa && empresa.idEmpresa) {
                    config.headers['X-Selected-Company'] = empresa.idEmpresa;
                }
            } catch (e) {
                console.error("Error parsing empresa for API interceptor", e);
            }
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response && [401, 403].includes(error.response.status)) {
            // Forzar cierre de sesión limpiando storage
            await storageService.removeItem('jwt_token');
            await storageService.removeItem('empresa');
            await storageService.removeItem('usuario');

            // Intentar redirección si Expo Router lo permite globalmente
            try {
                const { router } = require('expo-router');
                if (router && router.replace) {
                    router.replace('/login');
                }
            } catch (e) { }
        }
        return Promise.reject(error);
    }
);

export default api;
