const express = require('express');
const controller = require('../controllers/trimmingController');

const router = express.Router();

// Búsqueda de estilos / productos en ERP SADE
router.get('/styles/search', controller.searchStyles);

// Consulta de órdenes de corte con su estado de trimmings
router.get('/cuts', controller.getCutsList);

// Explosión recursiva de materiales (para un corte o simulación)
router.get('/cuts/:id/explosion', controller.getCutExplosion);
router.get('/explosion', controller.getCutExplosion);

// Generar la salida de almacén en ProMov / ProMovDet
router.post('/cuts/:id/generate', controller.generateOutput);

// Consultar movimiento ProMov generado
router.get('/promov/:id', controller.getMovement);

module.exports = router;
