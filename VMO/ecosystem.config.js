module.exports = {
  apps: [
    {
      name: 'vmo-backend',
      script: 'iniciar_servicio.bat',
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      watch: false
    }
  ]
};
