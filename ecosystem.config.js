module.exports = {
  apps: [
    {
      name: "pombot",
      script: "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/bin/gunicorn",
      args: "main:app -c gunicorn.conf.py",
      cwd: "/home/bsuadmin/marcjames/ai_chatbot_shop",
      interpreter: null,
      instances: 1,
      exec_mode: "fork",
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "true",
        PYTHONPATH: "/home/bsuadmin/marcjames/ai_chatbot_shop",
        PATH: "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/bin:$PATH",
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
