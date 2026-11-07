const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const authenticateToken = require('./middlewares/authMiddleware');
const cutTicketRoutes = require('./routes/cutTicketRoutes');
const bundleRoutes = require('./routes/bundleRoutes');
const packingRoutes = require('./routes/packingRoutes');
const trimmingRoutes = require('./routes/trimmingRoutes');

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Cargar index.html embebido (vía esbuild --loader:.html=text) con fallback a disco
let embeddedHtml = null;
try {
  embeddedHtml = require('../public/index.html');
} catch (e) {
  // Si se ejecuta en modo dev sin empaquetado
}

const publicPath = fs.existsSync(path.join(__dirname, 'public'))
  ? path.join(__dirname, 'public')
  : path.join(__dirname, '..', 'public');

// Ruta raíz: si existe HTML embebido en el bundle, servirlo directamente desde memoria
// Esto garantiza que copiar únicamente 'server.bundle.js' actualice 100% el frontend
app.get(['/', '/index.html'], (req, res, next) => {
  if (embeddedHtml && typeof embeddedHtml === 'string') {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.send(embeddedHtml);
  }
  next();
});

app.use(express.static(publicPath));

// Health check público (utilizado por balanceadores, monitoreo o IIS)
app.get('/health', (req, res) => {
  res.json({ 
    status: 'OK', 
    message: 'Servicio de Ingesta Textil SWS activo', 
    appUrl: `${req.protocol}://${req.get('host')}/` 
  });
});

// Endpoint público para login automático en entorno local / desarrollo
app.get('/api/auth/dev-token', (req, res) => {
  const jwt = require('jsonwebtoken');
  const secret = process.env.JWT_SECRET || 'super-secret-key-for-jwt-token-generation-that-should-be-long-enough';
  const issuer = process.env.JWT_ISSUER || 'AuthGeneral';
  const audience = process.env.JWT_AUDIENCE || 'AuthClients';
  const token = jwt.sign(
    { sub: 'operador.sade', nameid: 'operador.sade', role: 'ADMIN', empresaId: 'sws' },
    secret,
    { expiresIn: '30d', issuer, audience }
  );
  res.json({
    token,
    empresa: { idEmpresa: 'sws', empresa: 'SWS Textiles', rnc: '' }
  });
});

const { tenantMiddleware } = require('./config/db');

// Rutas de API protegidas con JWT del Login Centralizado y Multi-Tenant por Empresa
app.use('/api', authenticateToken, tenantMiddleware);
app.use('/api/cut-tickets', cutTicketRoutes);
app.use('/api/bundles', bundleRoutes);
app.use('/api/packing', packingRoutes);
app.use('/api/trimmings', trimmingRoutes);

module.exports = app;
