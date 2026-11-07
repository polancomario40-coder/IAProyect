import axios from 'axios';

// Obtención dinámica de la URL del API de AuthGeneral:
// 1. window.__AUTH_CONFIG__?.API_URL (configurable en runtime desde env-config.js o index.html)
// 2. Parámetro query ?api_url=... (enviado opcionalmente por la aplicación cliente)
// 3. Fallback relativo '/api' (para producción en IIS en el mismo servidor / Reverse Proxy)
// 4. http://localhost:5200/api (para desarrollo local)
function resolveApiUrl(): string {
  if (typeof window !== 'undefined') {
    const queryApi = new URLSearchParams(window.location.search).get('api_url');
    if (queryApi) return queryApi;

    const windowConfig = (window as any).__AUTH_CONFIG__?.API_URL;
    if (windowConfig) return windowConfig;

    if (window.location.port === '5174') return 'http://localhost:5200/api';
    return '/api';
  }
  return '/api';
}

export const CENTRAL_API_URL = resolveApiUrl();

const api = axios.create({
  baseURL: CENTRAL_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Interceptor para inyectar el token en cada petición
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('jwt_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para manejar errores 401/403 (token inválido o expirado)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && [401, 403].includes(error.response.status)) {
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('empresa');
      localStorage.removeItem('usuario');
    }
    return Promise.reject(error);
  }
);

// Puesto que AuthGeneral ahora centraliza la validación para TODAS las aplicaciones, 
// no necesitamos crear una instancia cliente dinámica por cada app.
export function createClientApi() {
  return api;
}

export default api;
