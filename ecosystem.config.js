module.exports = {
  apps: [
    {
      name: "pombot",
      script: "/usr/local/bin/gunicorn",
      args: "main:app -c gunicorn.conf.py",
      interpreter: null,
      instances: 1,
      exec_mode: "fork",
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "true",
        PYTHONPATH: "/home/bsuadmin/marcjames/ai_chatbot_shop",
      },
      error_file: "logs/err.log",
      out_file: "logs/out.log",
      log_file: "logs/combined.log",
      time: true,
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 4000,
    },
  ],
};
