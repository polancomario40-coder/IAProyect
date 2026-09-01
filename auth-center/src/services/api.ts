import axios from 'axios';

// La URL base será la de tu nueva AuthGeneral API.
// Durante desarrollo apuntamos al puerto local. En producción se usará la URL publicada.
export const CENTRAL_API_URL = (import.meta as any).env.VITE_AUTH_API_URL || 'http://localhost:5200/api';

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
