const sql = require('mssql');
const { AsyncLocalStorage } = require('async_hooks');
require('dotenv').config();

const tenantStorage = new AsyncLocalStorage();
const tenantPools = new Map();
let defaultPool = null;
let repoPool = null;

/**
 * Desencripta credenciales de usuario/contraseña generadas por el sistema Delphi ERP.
 * Constantes nativas: c1 = 52845, c2 = 22719, key = 2000
 */
function desencriptarPassword(pass) {
  if (!pass) return '';
  pass = pass.replace(/\0/g, '').trim();
  if (!pass || pass.length % 2 !== 0) return pass || '';

  try {
    const c1 = 52845;
    const c2 = 22719;
    let key = 2000;

    let result = '';
    for (let i = 0; i < pass.length; i += 2) {
      const byteVal = parseInt(pass.substr(i, 2), 16);
      if (isNaN(byteVal)) return pass;
      const charCode = (byteVal ^ (key >> 8)) & 0xff;
      result += String.fromCharCode(charCode);
      key = ((byteVal + key) * c1 + c2) % 65536;
    }
    return result;
  } catch (err) {
    console.error('[DB] Error al desencriptar credencial Delphi:', err);
    return pass;
  }
}

/**
 * Normaliza servidores y puertos (ej. "127.0.0.1\SQL2025" o "108.181.198.178,1438")
 */
function parseServerConfig(rawServer, defaultPort = 1442) {
  let serverName = (rawServer || '38.247.136.37').trim();
  let instanceName = undefined;
  let port = defaultPort;

  if (serverName.includes(',')) {
    const parts = serverName.split(',');
    serverName = parts[0].trim();
    port = parseInt(parts[1].trim(), 10) || defaultPort;
  }
  if (serverName.includes('\\')) {
    const parts = serverName.split('\\');
    serverName = parts[0].trim();
    instanceName = parts[1].trim();
  }

  // Si el servidor es localhost o 127.0.0.1 pero no se especificó puerto, mantener defaultPort
  return { serverName, instanceName, port };
}

/**
 * Retorna el pool por defecto configurado en .env (para tareas generales o fallback)
 */
async function getDefaultPool() {
  if (!defaultPool) {
    const rawServer = process.env.DB_SERVER || '127.0.0.1';
    const { serverName, instanceName, port } = parseServerConfig(rawServer, parseInt(process.env.DB_PORT, 10) || 1433);

    const config = {
      user: process.env.DB_USER || 'sa',
      password: process.env.DB_PASSWORD || 'P@$$w0rd',
      server: serverName,
      database: process.env.DB_DATABASE || 'sws',
      options: {
        encrypt: process.env.DB_ENCRYPT === 'true',
        trustServerCertificate: process.env.DB_TRUST_SERVER_CERT !== 'false',
        enableArithAbort: true,
        ...(instanceName ? { instanceName } : {})
      },
      ...(instanceName ? {} : { port }),
      pool: { max: 10, min: 0, idleTimeoutMillis: 30000 },
      connectionTimeout: 10000,
      requestTimeout: 30000
    };

    try {
      defaultPool = await sql.connect(config);
      console.log(`[DB] Conectado a Pool Default (${config.server}:${instanceName || port} -> ${config.database})`);
    } catch (err) {
      defaultPool = null;
      throw err;
    }
  }
  return defaultPool;
}

/**
 * Retorna el pool conectado a CBSRepository para consultar el catálogo cfgEmpresa
 */
async function getRepoPool() {
  if (!repoPool) {
    const rawServer = process.env.REPO_SERVER || process.env.DB_SERVER || '38.247.136.37';
    const { serverName, instanceName, port } = parseServerConfig(rawServer, parseInt(process.env.REPO_PORT || process.env.DB_PORT, 10) || 1442);

    const config = {
      user: process.env.REPO_USER || process.env.DB_USER || 'sade',
      password: process.env.REPO_PASSWORD || process.env.DB_PASSWORD || 'sadeP@$$w0rd',
      server: serverName,
      database: process.env.REPO_DATABASE || 'CBSRepository',
      options: {
        encrypt: process.env.DB_ENCRYPT === 'true',
        trustServerCertificate: process.env.DB_TRUST_SERVER_CERT !== 'false',
        enableArithAbort: true,
        ...(instanceName ? { instanceName } : {})
      },
      ...(instanceName ? {} : { port }),
      pool: { max: 5, min: 0, idleTimeoutMillis: 30000 },
      connectionTimeout: 10000,
      requestTimeout: 30000
    };

    try {
      repoPool = new sql.ConnectionPool(config);
      await repoPool.connect();
      console.log(`[DB] Conectado a CBSRepository (${config.server}:${instanceName || port})`);
    } catch (err) {
      repoPool = null;
      console.warn(`[DB] No se pudo conectar a CBSRepository (${err.message}). Se usará pool default.`);
      throw err;
    }
  }
  return repoPool;
}

/**
 * Resuelve y conecta dinámicamente al pool de la base de datos de la empresa indicada
 */
async function getTenantPool(companyId) {
  if (!companyId) {
    return await getDefaultPool();
  }

  const cacheKey = String(companyId).trim().toLowerCase();
  if (tenantPools.has(cacheKey)) {
    const existing = tenantPools.get(cacheKey);
    if (existing && existing.connected) {
      return existing;
    }
  }

  try {
    const repo = await getRepoPool();
    const result = await repo.request()
      .input('id', sql.VarChar(50), companyId.trim())
      .query(`
        SELECT TOP 1 
          IdEmpresa, Empresa, Servidor, BaseDatos, Trusted, UserId, UserPwd, Encriptada 
        FROM cfgEmpresa 
        WHERE CAST(IdEmpresa AS VARCHAR(50)) = @id 
           OR Empresa = @id 
           OR BaseDatos = @id
           OR Empresa LIKE @id
      `);

    if (result.recordset.length === 0) {
      console.warn(`[Tenant] Empresa '${companyId}' no encontrada en cfgEmpresa. Usando pool default.`);
      return await getDefaultPool();
    }

    const row = result.recordset[0];
    const { serverName, instanceName, port } = parseServerConfig(row.Servidor);
    const databaseName = (row.BaseDatos || '').trim();

    let user = (row.UserId || '').trim();
    let pwd = (row.UserPwd || '').trim();

    if (row.Encriptada) {
      user = desencriptarPassword(user);
      pwd = desencriptarPassword(pwd);
    }

    if (!user) user = process.env.DB_USER || 'sade';
    if (!pwd) pwd = process.env.DB_PASSWORD || 'sadeP@$$w0rd';

    const tenantConfig = {
      user,
      password: pwd,
      server: serverName,
      database: databaseName,
      options: {
        encrypt: process.env.DB_ENCRYPT === 'true',
        trustServerCertificate: true,
        enableArithAbort: true,
        ...(instanceName ? { instanceName } : {})
      },
      ...(instanceName ? {} : { port }),
      pool: { max: 10, min: 0, idleTimeoutMillis: 30000 },
      connectionTimeout: 10000,
      requestTimeout: 30000
    };

    console.log(`[Tenant] Creando pool para empresa '${row.Empresa}' (${serverName} -> ${databaseName})`);
    const pool = new sql.ConnectionPool(tenantConfig);
    await pool.connect();
    tenantPools.set(cacheKey, pool);
    return pool;
  } catch (err) {
    console.error(`[Tenant] Error conectando a empresa '${companyId}':`, err.message);
    console.warn(`[Tenant] Intentando fallback a pool default...`);
    return await getDefaultPool();
  }
}

/**
 * Función principal para que los servicios obtengan el pool activo según el tenant actual
 */
async function getPool() {
  const store = tenantStorage.getStore();
  const companyId = store?.companyId;
  if (companyId) {
    return await getTenantPool(companyId);
  }
  return await getDefaultPool();
}

/**
 * Middleware de Express para capturar el tenant seleccionado en cada petición
 */
function tenantMiddleware(req, res, next) {
  const companyId = 
    req.headers['x-selected-company'] || 
    req.headers['x-empresa-id'] || 
    req.query.empresaId || 
    req.user?.empresaId ||
    null;

  tenantStorage.run({ companyId }, () => {
    next();
  });
}

module.exports = {
  sql,
  getPool,
  getDefaultPool,
  getTenantPool,
  tenantMiddleware,
  desencriptarPassword
};

