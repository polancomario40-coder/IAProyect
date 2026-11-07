const app = require('./app');
const { getPool } = require('./config/db');
require('dotenv').config();

const PORT = process.env.PORT || 3000;

// Levantar el servidor HTTP inmediatamente para que IIS y Cloudflare siempre reciban respuesta
const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`====================================================`);
  console.log(`Servidor SWS Textil Produccion corriendo en http://localhost:${PORT}`);
  console.log(`Fase 1: Ingesta y Packing List lista.`);
  console.log(`====================================================`);
});

// Probar conexión a la base de datos en segundo plano sin tumbar el servidor
getPool()
  .then(() => {
    console.log(`[DB] Conexion inicial establecida correctamente.`);
  })
  .catch((err) => {
    console.warn(`----------------------------------------------------`);
    console.warn(`[AVISO DB] No se pudo conectar inmediatamente a SQL Server:`);
    console.warn(`--> Mensaje: ${err.message}`);
    console.warn(`--> El servidor HTTP PERMANECE ACTIVO en el puerto ${PORT}.`);
    console.warn(`--> Revisa los valores en C:\\inetpub\\Textil\\.env si necesitas cambiar servidor, usuario, password o puerto.`);
    console.warn(`----------------------------------------------------`);
  });

