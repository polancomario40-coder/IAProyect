const bundleService = require('../services/bundleService');

async function generate(req, res) {
  try {
    const { idCutTicket, bundleSize } = req.body;
    if (!idCutTicket) {
      return res.status(400).json({ error: 'idCutTicket es requerido.' });
    }

    const result = await bundleService.generateBundles(parseInt(idCutTicket, 10), bundleSize);
    return res.status(200).json({
      message: `Se generaron exitosamente ${result.totalBundles} etiquetas.`,
      data: result
    });
  } catch (err) {
    console.error('[Generate Bundles Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function getByTicket(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const result = await bundleService.getBundlesByCutTicket(id);
    if (!result) {
      return res.status(404).json({ error: 'Cut Ticket no encontrado.' });
    }
    return res.json(result);
  } catch (err) {
    console.error('[Get Bundles Error]', err);
    return res.status(500).json({ error: err.message });
  }
}

async function remove(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const result = await bundleService.deleteBundles(id);
    return res.json({ message: 'Etiquetas eliminadas', result });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}

module.exports = {
  generate,
  getByTicket,
  remove
};
