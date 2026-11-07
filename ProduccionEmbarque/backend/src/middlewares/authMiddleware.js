const jwt = require('jsonwebtoken');
require('dotenv').config();

const JWT_SECRET = process.env.JWT_SECRET || 'super-secret-key-for-jwt-token-generation-that-should-be-long-enough';
const JWT_ISSUER = process.env.JWT_ISSUER || 'AuthGeneral';
const JWT_AUDIENCE = process.env.JWT_AUDIENCE || 'AuthClients';
const AUTH_REQUIRED = process.env.AUTH_REQUIRED !== 'false';

/**
 * Middleware para validar el token JWT emitido por la App de Login centralizada (AuthGeneral).
 */
function authenticateToken(req, res, next) {
  if (!AUTH_REQUIRED) {
    req.user = { username: 'DEV_USER', offline: true };
    return next();
  }

  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.startsWith('Bearer ') 
    ? authHeader.substring(7) 
    : (req.query && req.query.token);

  if (!token) {
    return res.status(401).json({
      success: false,
      error: 'Acceso no autorizado: No se proporciono el token de autenticacion (JWT).'
    });
  }

  // Validar firma criptográfica y expiración (compatible con CxpApi en SADE y AuthGeneral en VMO)
  jwt.verify(token, JWT_SECRET, {
    algorithms: ['HS256']
  }, (err, decoded) => {
    if (err) {
      console.warn('[AUTH] Token invalido o expirado:', err.message);
      return res.status(401).json({
        success: false,
        error: 'Sesion expirada o token invalido. Por favor inicia sesion nuevamente.',
        details: err.message
      });
    }

    req.user = {
      username: decoded.sub || decoded.nameid || 'USUARIO',
      ...decoded
    };

    next();
  });
}

module.exports = authenticateToken;
