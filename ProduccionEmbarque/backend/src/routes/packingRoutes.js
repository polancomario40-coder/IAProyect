const express = require('express');
const controller = require('../controllers/packingController');

const router = express.Router();

router.post('/create', controller.createContainer);
router.get('/lists', controller.listContainers);
router.post('/scan', controller.scan);
router.get('/:id/report', controller.getReport);
router.post('/:id/dispatch', controller.dispatch);
router.delete('/bundle/:id', controller.unscan);

module.exports = router;
