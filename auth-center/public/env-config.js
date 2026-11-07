// Configuración dinámica del Centro de Autenticación (Editable en el servidor)
window.__AUTH_CONFIG__ = {
  // Dejar '/api' para usar la API local del servidor IIS donde está instalado AuthGeneral.
  // Si AuthGeneral corre en un puerto diferente (ej: 5200), configurar: 'http://localhost:5200/api'
  API_URL: '/api'
};
