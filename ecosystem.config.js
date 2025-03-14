module.exports = {
  apps: [
    {
      name: "pombot",
      script: "wsgi.py",
      interpreter: "python3",
      instances: 1,
      exec_mode: "fork",
      max_memory_restart: "500M",
      env: {
        PORT: 1551,
        PYTHONUNBUFFERED: "true",
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
