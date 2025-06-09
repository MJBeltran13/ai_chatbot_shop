module.exports = {
  apps: [
    {
      name: 'ai-chatbot-pomworkz',
      script: 'python',
      args: 'start_production.py',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      restart_delay: 4000,
      env: {
        NODE_ENV: 'production',
        FLASK_ENV: 'production',
        HOST: '0.0.0.0',
        PORT: 1551,
        THREADS: 4,
        PDF_PATH: 'POMWORKZ AUTO PARTS CATALOG.pdf'
      },
      env_development: {
        NODE_ENV: 'development',
        FLASK_ENV: 'development',
        HOST: '127.0.0.1',
        PORT: 1551,
        THREADS: 2,
        PDF_PATH: 'POMWORKZ AUTO PARTS CATALOG.pdf'
      },
      error_file: './logs/err.log',
      out_file: './logs/out.log',
      log_file: './logs/combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm Z'
    },
  ],
};
