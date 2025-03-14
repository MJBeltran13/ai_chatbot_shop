module.exports = {
  apps: [
    {
      name: "PomBot",
      script: "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/bin/gunicorn",
      args: "main:app -b 0.0.0.0:1551 --timeout 60 --workers 1 --access-logfile - --error-logfile - --capture-output",
      interpreter: "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/bin/python3",
      env: {
        PYTHONPATH: "/home/bsuadmin/marcjames/ai_chatbot_shop",
        PATH: "/usr/local/bin:/usr/bin:/bin:" + process.env.PATH,
      },
      watch: false,
      instances: 1,
      exec_mode: "fork",
      max_memory_restart: "500M",
      restart_delay: 4000,
    },
  ],
};
