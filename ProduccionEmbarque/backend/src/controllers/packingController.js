const packingService = require('../services/packingService');

async function createContainer(req, res) {
  try {
    const { containerNumber, customer, shipDate, notes } = req.body;
    const result = await packingService.createOrGetPackingList(containerNumber, customer, shipDate, notes);
    return res.status(200).json({ message: 'Contenedor listo', data: result });
  } catch (err) {
    console.error('[Create Container Error]', err);
    return res.status(400).json({ error: err.message });
  }
}

async function listContainers(req, res) {
  try {
    const list = await packingService.getPackingLists();
    return res.json(list);
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}

async function scan(req, res) {
  try {
    const { barcode, idPackingList, boxNumber } = req.body;
    if (!barcode || !idPackingList) {
      return res.status(400).json({ error: 'barcode y idPackingList son requeridos.' });
    }

    const result = await packingService.scanBundle(barcode, parseInt(idPackingList, 10), boxNumber);
    return res.status(200).json({
      message: 'Lectura procesada con éxito',
      data: result
    });
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}

async function getReport(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const report = await packingService.getPackingReport(id);
    return res.json(report);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}

async function dispatch(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const result = await packingService.dispatchPackingList(id);
    return res.json(result);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}

async function unscan(req, res) {
  try {
    const id = parseInt(req.params.id, 10);
    const result = await packingService.unscanBundle(id);
    return res.json(result);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}

module.exports = {
  createContainer,
  listContainers,
  scan,
  getReport,
  dispatch,
  unscan
};
