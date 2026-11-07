const trimmingService = require('../services/trimmingService');

/**
 * Controlador para el módulo de Trimmings / Accesorios de Inventario
 */

async function searchStyles(req, res) {
  try {
    const q = req.query.q || '';
    const results = await trimmingService.searchProducts(q);
    return res.json(results);
  } catch (err) {
    console.error('[Trimming searchStyles Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function getCutsList(req, res) {
  try {
    const filters = {
      search: req.query.search,
      status: req.query.status,
      trimmingStatus: req.query.trimmingStatus,
      startDate: req.query.startDate,
      endDate: req.query.endDate
    };
    const list = await trimmingService.getCutsTrimmingList(filters);
    return res.json(list);
  } catch (err) {
    console.error('[Trimming getCutsList Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function getCutExplosion(req, res) {
  try {
    const idCutTicket = req.params.id ? parseInt(req.params.id, 10) : null;
    const { style, totalUnits, customProductId } = req.query;

    const explosion = await trimmingService.getExplosionData({
      idCutTicket,
      style,
      totalUnits,
      customProductId
    });

    return res.json(explosion);
  } catch (err) {
    console.error('[Trimming getCutExplosion Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function generateOutput(req, res) {
  try {
    const idCutTicket = parseInt(req.params.id, 10);
    const { items, idAlmacen, usuario, postNow, notes } = req.body;

    const result = await trimmingService.generateTrimmingOutput({
      idCutTicket,
      items,
      idAlmacen: idAlmacen || 'Stock',
      usuario: usuario || req.user?.username || 'SWS_OPERADOR',
      postNow: !!postNow,
      notes
    });

    return res.status(200).json(result);
  } catch (err) {
    console.error('[Trimming generateOutput Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function getMovement(req, res) {
  try {
    const id = req.params.id;
    const movementData = await trimmingService.getProMovDetails(id);
    if (!movementData) {
      return res.status(404).json({ error: 'Movimiento no encontrado.' });
    }
    return res.json(movementData);
  } catch (err) {
    console.error('[Trimming getMovement Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

module.exports = {
  searchStyles,
  getCutsList,
  getCutExplosion,
  generateOutput,
  getMovement
};
