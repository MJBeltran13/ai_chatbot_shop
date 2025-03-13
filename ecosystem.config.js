module.exports = {
  apps: [
    {
      name: "ai_chatbot_shop",
      script: "main.py",
      interpreter: "python",
      env: {
        PORT: "1551",
      },
      watch: true,
    },
  ],
};
