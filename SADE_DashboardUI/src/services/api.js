import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5015/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const empresaRaw = localStorage.getItem('empresa');
    if (empresaRaw) {
      try {
        const empresa = JSON.parse(empresaRaw);
        if (empresa && empresa.idEmpresa) {
          config.headers['X-Selected-Company'] = empresa.idEmpresa;
        }
      } catch (e) {
        console.error('Error parsing company for api headers', e);
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
  (error) => {
    if (error.response && [401, 403].includes(error.response.status)) {
      // Force clean session
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('empresa');
      localStorage.removeItem('usuario');
      
      // Redirect to Auth Center
      const redirectUri = window.location.origin + '/auth-callback';
      window.location.href = `https://auth.sade.com.do/?client_id=sade-dashboard&redirect_uri=${encodeURIComponent(redirectUri)}`;
    }
    return Promise.reject(error);
  }
);

export default api;
