const express = require('express');
const controller = require('../controllers/bundleController');

const router = express.Router();

router.post('/generate', controller.generate);
router.get('/ticket/:id', controller.getByTicket);
router.delete('/ticket/:id', controller.remove);

module.exports = router;
