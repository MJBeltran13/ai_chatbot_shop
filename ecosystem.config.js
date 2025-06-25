module.exports = {
  apps: [
    {
      name: 'mj-chatbot',
      script: 'gunicorn',
      args: 'main:app --bind 0.0.0.0:1551 --workers 2 --threads 4 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 --preload',
      interpreter: '/usr/bin/python3',
      exec_mode: 'fork',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      restart_delay: 4000,
      env: {
        NODE_ENV: 'production',
        FLASK_ENV: 'production',
        PORT: 1551,
        PDF_PATH: 'POMWORKZ AUTO PARTS CATALOG.pdf',
        PYTHONPATH: '.'
      },
      env_development: {
        NODE_ENV: 'development',
        FLASK_ENV: 'development',
        PORT: 1551,
        PDF_PATH: 'POMWORKZ AUTO PARTS CATALOG.pdf',
        PYTHONPATH: '.'
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
