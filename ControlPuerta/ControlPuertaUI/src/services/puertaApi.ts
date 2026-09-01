import axios from 'axios';

// ─── Axios instance con interceptor JWT ───────────────────────────────────────
const TOKEN_KEY      = 'jwt_token';   // misma clave que usa auth-center y cuadre-caja
const EMPRESA_KEY    = 'empresa';
const AUTH_CENTER    = import.meta.env.VITE_AUTH_CENTER_URL || 'http://localhost:5174';
const CLIENT_ID      = 'control-puerta';

export const puertaApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Interceptor de Request: adjunta el token JWT en cada llamada
puertaApi.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor de Response: si el token expiró → redirige a auth-center
puertaApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EMPRESA_KEY);
      const redirectUri = encodeURIComponent(window.location.origin + '/auth-callback');
      window.location.href = `${AUTH_CENTER}/?client_id=${CLIENT_ID}&redirect_uri=${redirectUri}`;
    }
    return Promise.reject(error);
  }
);

// ─── API functions ────────────────────────────────────────────────────────────

export const ocrPlaca = (imagenBase64: string, mimeType = 'image/jpeg') =>
  puertaApi.post('/puerta/ocr-placa', { imagenBase64, mimeType });

// Alias para OCR de texto genérico (conduce, etc.) — usa el mismo endpoint de Azure AI
export const extraerTextoPlaca = (imagenBase64: string, mimeType = 'image/jpeg') =>
  puertaApi.post('/puerta/ocr-placa', { imagenBase64, mimeType });

export const validarTransportista = (placa: string) =>
  puertaApi.get(`/puerta/validar-transportista`, { params: { placa } });

export const buscarPlacas = (q: string) =>
  puertaApi.get(`/puerta/buscar-placas`, { params: { q } });

export const listarProductos = () =>
  puertaApi.get('/puerta/productos');

export const listarChoferes = (idTransportista: string) =>
  puertaApi.get(`/puerta/choferes/${idTransportista}`);

export const registrarEntrada = (data: object) =>
  puertaApi.post('/puerta/registrar-entrada', data);

export const cancelarEntrada = (id: string) =>
  puertaApi.put(`/puerta/${id}/cancelar`);

// Fase 2 - Recepción
export interface ConfirmarRecepcionRequest {
  idEntradaCamion: string;
  conduce: string;
  conduceTransporte: string;
  fotoConduceBase64?: string;
  fotoConduceMime?: string;
  firmaDigitalBase64?: string;
  idSuplidor?: string;
  nombreSuplidor?: string;
  idProductoReal?: string;
  nombreProductoReal?: string;
  idAlmacen?: string;
  cantidadRecibida: number;
  notas?: string;
  evidenciasBase64?: string[];
}

export const obtenerEntradasHoy = (idPuerta?: string) =>
  puertaApi.get('/puerta/entradas-hoy', { params: { idPuerta } });

export const obtenerRecepcion = (id: string) =>
  puertaApi.get(`/recepcion/${id}`);

export const buscarProductosReales = (q: string) =>
  puertaApi.get(`/puerta/productos-reales?q=${encodeURIComponent(q)}`);

export const buscarSuplidores = (q: string) =>
  puertaApi.get(`/recepcion/suplidores?q=${encodeURIComponent(q)}`);

export const listarAlmacenes = () =>
  puertaApi.get('/recepcion/almacenes');

export const confirmarRecepcion = (id: string, data: ConfirmarRecepcionRequest) =>
  puertaApi.put(`/recepcion/${id}/confirmar`, data);

export const guardarEvidencia = (id: string, data: object) =>
  puertaApi.post(`/recepcion/${id}/evidencia`, data);

export const descargarEvidencia = (id: string, tipo: string) =>
  puertaApi.get(`/recepcion/${id}/evidencia/${tipo}`, { responseType: 'blob' });

export const notificarRecepcion = (id: string, data: object) =>
  puertaApi.post(`/recepcion/${id}/notificar`, data);

export const obtenerTicket = (id: string) =>
  puertaApi.get(`/recepcion/${id}/ticket`);

export const consultarRecepciones = (filtros: object) =>
  puertaApi.get('/cierre/recepciones', { params: filtros });

export const obtenerPendientesCierre = (fecha?: string) =>
  puertaApi.get('/cierre/pendientes', { params: { fecha } });

export const asignarOc = (data: object) =>
  puertaApi.put('/cierre/asignar-oc', data);

export const ejecutarCierre = (data: object) =>
  puertaApi.post('/cierre/ejecutar', data);

export const buscarOrdenes = (q?: string, fecha?: string) =>
  puertaApi.get('/cierre/ordenes', { params: { q, fecha } });

// ─── Auth helpers ─────────────────────────────────────────────────────────────
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const getUsuario = (): { username: string; nombre: string } | null => {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return {
      username: payload['idSegUserGrp'] || payload['sub'] || payload['unique_name'] || '',
      nombre:   payload['nombre'] || payload['name'] || payload['unique_name'] || '',
    };
  } catch {
    return null;
  }
};

export const getMe = () => puertaApi.get('/usuario/me');
