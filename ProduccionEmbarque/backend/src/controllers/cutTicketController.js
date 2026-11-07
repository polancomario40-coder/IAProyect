const path = require('path');
const fs = require('fs');
const cutTicketService = require('../services/cutTicketService');

/**
 * Endpoint para subir un archivo Excel de Cut Ticket vía formulario multipart.
 */
async function uploadCutTicket(req, res) {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Debes enviar un archivo Excel (.xlsx).' });
    }

    const result = await cutTicketService.importCutTicket(req.file.buffer, req.file.originalname);
    return res.status(200).json({
      message: 'Cut Ticket procesado con éxito',
      data: result
    });
  } catch (err) {
    console.error('[Upload Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

/**
 * Endpoint utilitario para importar automáticamente todos los MTO-*.xlsx
 * desde una ruta de carpeta local.
 */
async function importFromFolder(req, res) {
  try {
    const targetDir = req.body?.folderPath || 'C:\\DEV\\IAProyect\\ProduccionEmbarque';
    if (!fs.existsSync(targetDir)) {
      return res.status(400).json({ error: `La carpeta ${targetDir} no existe.` });
    }

    const files = fs.readdirSync(targetDir).filter(f => f.startsWith('MTO-') && f.endsWith('.xlsx'));
    const results = [];

    for (const file of files) {
      const fullPath = path.join(targetDir, file);
      try {
        const importResult = await cutTicketService.importCutTicket(fullPath, file);
        results.push({ file, success: true, details: importResult });
      } catch (e) {
        results.push({ file, success: false, error: e.message });
      }
    }

    return res.status(200).json({
      message: `Procesados ${results.length} archivos`,
      results
    });
  } catch (err) {
    console.error('[Folder Import Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function listCutTickets(req, res) {
  try {
    const list = await cutTicketService.getAllCutTickets();
    return res.json(list);
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}

async function getCutTicket(req, res) {
  try {
    const ticket = await cutTicketService.getCutTicketById(parseInt(req.params.id, 10));
    if (!ticket) return res.status(404).json({ error: 'Cut Ticket no encontrado' });
    return res.json(ticket);
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}

async function updateStatus(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const { status, changedBy, notes } = req.body;

    if (!status) {
      return res.status(400).json({ error: 'El campo status es requerido.' });
    }

    const result = await cutTicketService.updateCutTicketStatus(id, status, changedBy, notes);
    return res.json({
      message: 'Estatus actualizado exitosamente',
      data: result
    });
  } catch (err) {
    console.error('[Update Status Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function getWipSummary(req, res) {
  try {
    const summary = await cutTicketService.getWipSummary();
    return res.json(summary);
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}

module.exports = {
  uploadCutTicket,
  importFromFolder,
  listCutTickets,
  getCutTicket,
  updateStatus,
  getWipSummary
};

