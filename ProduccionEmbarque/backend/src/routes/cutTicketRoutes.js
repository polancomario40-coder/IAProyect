const express = require('express');
const multer = require('multer');
const controller = require('../controllers/cutTicketController');

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage() });

// Carga de Cut Ticket vía archivo Excel multipart
router.post('/upload', upload.single('file'), controller.uploadCutTicket);

// Ingesta automática desde carpeta local
router.post('/import-folder', controller.importFromFolder);

// Resumen de métricas WIP
router.get('/wip/summary', controller.getWipSummary);

// Consultas
router.get('/', controller.listCutTickets);
router.get('/:id', controller.getCutTicket);

// Actualizar Estatus (WIP)
router.patch('/:id/status', controller.updateStatus);

module.exports = router;
