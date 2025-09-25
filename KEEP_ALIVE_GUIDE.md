# Keep-Alive Setup Guide

To keep your bot running 24/7 on Render's free tier, follow these steps:

## 1. GitHub Repository Setup

After deploying to Render, go to your GitHub repository:

1. Go to Settings > Secrets and Variables > Actions
2. Add a new repository secret:
   - Name: `RENDER_URL`
   - Value: `https://your-app-name.onrender.com` (Your Render deployment URL)

## 2. Uptime Robot Setup (Primary Method)

1. Create an account at [UptimeRobot](https://uptimerobot.com)
2. Add a new monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: Bypass Bot
   - URL: `https://your-app-name.onrender.com/keep-alive`
   - Monitoring Interval: 5 minutes

## 3. GitHub Actions (Backup Method)

The workflow is already set up in `.github/workflows/keep_alive.yml`:
- Pings your bot every 10 minutes
- Can be manually triggered if needed
- Works as a backup to Uptime Robot

## 4. Verifying It Works

1. Check your Render logs to see incoming ping requests
2. Monitor your bot's uptime in UptimeRobot dashboard
3. Check GitHub Actions to see successful pings

## Important Notes

1. The bot has two keep-alive endpoints:
   - `/keep-alive` - Main health check endpoint
   - `/` - Root endpoint for basic health check

2. Both Uptime Robot and GitHub Actions are used for redundancy:
   - If one system fails, the other continues pinging
   - Helps maintain maximum uptime

3. The free tier of Render will still have cold starts:
   - First request after inactivity may be slow
   - Subsequent requests will be faster
   - Both monitoring systems help minimize cold starts

4. Monitor your Render dashboard:
   - Keep an eye on usage metrics
   - Check for any errors or issues
   - Ensure you stay within free tier limits