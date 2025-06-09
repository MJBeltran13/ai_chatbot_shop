# PM2 Setup Guide for PomWorkz AI Chatbot

## 📋 **Prerequisites**

1. **Install Node.js and npm** (required for PM2)
2. **Install PM2 globally**:
   ```bash
   npm install -g pm2
   ```

3. **Install Python dependencies** (if not already done):
   ```bash
   pip install waitress
   ```

## 🚀 **Quick Start Commands**

### **1. Start the Application**
```bash
# Start with ecosystem file (recommended)
pm2 start ecosystem.config.js

# Or start directly
pm2 start start_production.py --name "ai-chatbot-pomworkz" --interpreter python
```

### **2. Essential PM2 Commands**
```bash
# View running applications
pm2 list

# View logs (real-time)
pm2 logs ai-chatbot-pomworkz

# View monitoring dashboard
pm2 monit

# Restart application
pm2 restart ai-chatbot-pomworkz

# Stop application
pm2 stop ai-chatbot-pomworkz

# Delete application from PM2
pm2 delete ai-chatbot-pomworkz

# Reload application (zero-downtime)
pm2 reload ai-chatbot-pomworkz
```

### **3. Production Deployment**
```bash
# Start in production mode
pm2 start ecosystem.config.js --env production

# Save PM2 configuration
pm2 save

# Setup PM2 to start on system boot
pm2 startup
# Follow the instructions provided by the command above
```

### **4. Development Mode**
```bash
# Start in development mode
pm2 start ecosystem.config.js --env development
```

## 📊 **Monitoring and Logs**

### **View Logs**
```bash
# All logs
pm2 logs

# Specific app logs
pm2 logs ai-chatbot-pomworkz

# Error logs only
pm2 logs ai-chatbot-pomworkz --err

# Output logs only
pm2 logs ai-chatbot-pomworkz --out

# Last 100 lines
pm2 logs ai-chatbot-pomworkz --lines 100
```

### **Log Files Location**
- Error logs: `./logs/err.log`
- Output logs: `./logs/out.log`
- Combined logs: `./logs/combined.log`

### **Real-time Monitoring**
```bash
# CPU, Memory, and other metrics
pm2 monit

# Process information
pm2 show ai-chatbot-pomworkz

# Process list with details
pm2 list
```

## 🔧 **Configuration**

### **Environment Variables** (in ecosystem.config.js)
- `PORT`: Server port (default: 1551)
- `HOST`: Server host (production: 0.0.0.0, development: 127.0.0.1)
- `THREADS`: Number of threads (production: 4, development: 2)
- `PDF_PATH`: Path to the PDF knowledge base file

### **Memory Management**
- Auto-restart when memory usage exceeds 1GB
- Restart delay: 4 seconds after crash

## 🔄 **Auto-restart and Recovery**

PM2 automatically:
- ✅ Restarts the app if it crashes
- ✅ Manages memory usage
- ✅ Handles log rotation
- ✅ Provides zero-downtime reloads

## 🌐 **Access Your Application**

After starting with PM2:
- **Local**: http://127.0.0.1:1551
- **Network**: http://YOUR_SERVER_IP:1551

### **Health Check**
```bash
curl http://127.0.0.1:1551/health
```

### **Test API**
```bash
curl -X POST http://127.0.0.1:1551/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Port already in use**:
   ```bash
   pm2 stop ai-chatbot-pomworkz
   # Or change PORT in ecosystem.config.js
   ```

2. **Python not found**:
   ```bash
   # Use full Python path in ecosystem.config.js
   which python3
   ```

3. **PDF not found**:
   ```bash
   # Ensure PDF file exists in project directory
   ls -la "POMWORKZ AUTO PARTS CATALOG.pdf"
   ```

4. **Ollama not running**:
   ```bash
   # Start Ollama service
   ollama serve
   ```

### **Debug Commands**
```bash
# Check application status
pm2 describe ai-chatbot-pomworkz

# View environment variables
pm2 env 0

# Restart with verbose logging
pm2 restart ai-chatbot-pomworkz --log-date-format="YYYY-MM-DD HH:mm Z"
```

## 📱 **PM2 Plus (Optional)**

For advanced monitoring, you can connect to PM2 Plus:
```bash
pm2 plus
```

This provides:
- Web dashboard
- Real-time monitoring
- Alerts and notifications
- Performance metrics

---

## 🎯 **Production Checklist**

- [ ] PM2 installed globally
- [ ] Ecosystem file configured
- [ ] Logs directory created
- [ ] PDF knowledge base file exists
- [ ] Ollama service running
- [ ] Application starts successfully
- [ ] Health check returns "healthy"
- [ ] PM2 startup configured
- [ ] PM2 configuration saved

**Your AI Chatbot is now production-ready with PM2! 🚀** 