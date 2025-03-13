module.exports = {
  apps: [
    {
      name: "ai_chatbot_shop",
      script: "main.py",
      interpreter: "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/bin/python3",
      env: {
        PORT: "1551",
        PYTHONPATH:
          "/home/bsuadmin/marcjames/ai_chatbot_shop/venv/lib/python3.8/site-packages",
      },
      watch: true,
    },
  ],
};
