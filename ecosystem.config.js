module.exports = {
  apps: [
    {
      name: "ai_chatbot_shop",
      script: "main.py",
      interpreter: "/usr/bin/python3",
      env: {
        PORT: "1551",
      },
      watch: true,
    },
  ],
};
