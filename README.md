# Bypass Bot

A Telegram bot for bypassing links with premium features and user management.

## Deployment Guide for Render

### Prerequisites
1. A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
2. API ID and API Hash (from [my.telegram.org](https://my.telegram.org))
3. Bypass Session String (generate using `generate_session.py`)
4. Render Account (sign up at [render.com](https://render.com))

### Deploy to Render

1. **Fork or Clone this Repository**
   - Fork this repository to your GitHub account

2. **Create New Web Service on Render**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" and select "Web Service"
   - Connect your GitHub account if not done already
   - Select this repository

3. **Configure the Web Service**
   - Name: Choose a name for your service (e.g., `bypass-bot`)
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `bash start.sh`
   - Plan: Choose "Free"
   - Select the region closest to you

4. **Add Environment Variables**
   Click on "Environment" and add these variables:
   ```
   API_ID=your_api_id
   API_HASH=your_api_hash
   BOT_TOKEN=your_bot_token
   OWNER_ID=your_telegram_id
   BYPASS_API_ID=your_bypass_api_id
   BYPASS_API_HASH=your_bypass_api_hash
   BYPASS_SESSION_STRING=your_session_string
   PORT=8080
   ```
   (Replace values with your actual credentials)

5. **Optional Environment Variables**
   ```
   FORCE_SUB_CHANNEL1=channel_id
   FORCE_SUB_CHANNEL2=channel_id
   FORCE_SUB_CHANNEL3=channel_id
   CHANNEL_ID=log_channel_id
   ```

6. **Deploy**
   - Click "Create Web Service"
   - Wait for the deployment to complete

### Keep Bot Active (Prevent Sleep)

To prevent the bot from sleeping on Render's free tier:

1. Create an account on [UptimeRobot](https://uptimerobot.com)
2. Add a new monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: Bypass Bot
   - URL: `https://your-app-name.onrender.com/keep-alive`
   - Monitoring Interval: 5 minutes

### Important Notes
- The bot will be accessible at `https://your-app-name.onrender.com`
- Free tier may have cold starts
- UptimeRobot helps keep the bot active
- Monitor your usage on Render dashboard

### Support
For support, contact [@Athithpm](https://t.me/Athithpm)