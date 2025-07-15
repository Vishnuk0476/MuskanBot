# 🎶 Muskan Music Bot 🎶

Muskan Music Bot is a feature-rich Telegram bot designed to manage music playback in groups and assist with various group administration tasks. It allows users to play songs, search for music, manage a queue, and provides powerful moderation tools for group admins.

## ✨ Features

**🔊 Music Features:**
* `/play <song name>`: Play a song (192kbps HQ audio).
* `/search <query>`: Search for songs and display top results.
* `/queue`: Show the current music playlist.
* `/skip`: Skip the current song (Admins or requester only).
* `/clear`: Clear the entire music queue (Admins only).
* `/np` (Now Playing): (Placeholder - not yet implemented in code)
* `/shuffle`: (Placeholder - not yet implemented in code)
* `/remove <index>`: (Placeholder - not yet implemented in code)
* `/lyrics <song>`: (Placeholder - not yet implemented in code)
* `/volume <level>`: (Placeholder - not yet implemented in code)
* `/mystats`: (Placeholder - not yet implemented in code)

**👥 Group Management Features:**
* `/setup`: Initialize the bot in a group and set the first admin.
* `/settings`: Configure group-specific settings via inline buttons (e.g., enable/disable music, welcome messages).
* `/welcome <message>`: Set a custom welcome message for new members.
* Automatic welcome messages for new chat members.

**💬 General Chat Features:**
* `/start`: Start interaction with the bot.
* `/help`: Display a list of all available commands.
* `/admin <message>`: Send a message directly to the bot's administrator.
* `/reply <user_id> <message>`: (Admin only) Reply to a user who messaged the admin via `/admin`.

**⚙️ Admin-Only Features:**
* `/ban <user_id>`: Ban a user from using the bot.
* `/unban <user_id>`: Unban a user.
* `/broadcast <message>`: Send a message to all users who have interacted with the bot.
* `/stats`: Display bot usage statistics (number of users, groups, queue length, etc.).

## 🚀 Getting Started

This bot is designed to be easily deployed on cloud platforms like Replit or Render.

### Prerequisites

Before you start, make sure you have:

* **Python 3.8+** installed.
* A **Telegram Bot Token** from [@BotFather](https://t.me/botfather).
* Your **Telegram User ID** (you can get this from bots like [@userinfobot](https://t.me/userinfobot)).
* A **GitHub account** (recommended for deployment on Render).

### Local Setup (for Development/Testing)

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YourUsername/MuskanMusicBot.git](https://github.com/YourUsername/MuskanMusicBot.git) # Replace with your actual GitHub repo URL
    cd MuskanMusicBot
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows: .\venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create a `.env` file:**
    * In the root directory of your project, create a file named `.env`.
    * Add your bot token and admin ID:
        ```
        TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
        ADMIN_ID=YOUR_TELEGRAM_ADMIN_USER_ID_HERE
        ```
        *Replace the placeholders with your actual token and ID.*
5.  **Run the bot:**
    ```bash
    python main.py
    ```

### Deployment on Replit (Recommended Free Hosting)

Replit is an excellent free platform for hosting your bot 24/7 (with a small workaround).

1.  **Create a New Repl:**
    * Go to [Replit.com](https://replit.com/).
    * Click "+ Create Repl", select "Python" template, and give your Repl a name.
2.  **Add Files:**
    * Copy the content of your `main.py` into Replit's `main.py` file.
    * Create a new file named `keep_alive.py` and paste the `keep_alive.py` code into it.
    * Create a new file named `requirements.txt` and paste the content from the `requirements.txt` section above.
    * Create a new file named `Procfile` and add the line: `web: python main.py`
3.  **Set Secrets (Environment Variables):**
    * In Replit, click the **"Secrets"** icon (padlock) on the left sidebar.
    * Add two secrets:
        * `Key`: `TOKEN`, `Value`: Your Telegram Bot Token
        * `Key`: `ADMIN_ID`, `Value`: Your Telegram User ID
4.  **Install Dependencies:**
    * Go to the "Shell" tab in Replit.
    * Run: `pip install -r requirements.txt`
5.  **Enable 24/7 Uptime:**
    * Your `main.py` should already include `from keep_alive import keep_alive` and `keep_alive()` call *before* `asyncio.run(main())` in the `if __name__ == '__main__':` block. This starts a small web server.
    * **Crucially:** You need an external uptime monitoring service like [UptimeRobot](https://uptimerobot.com/).
        * Sign up for UptimeRobot.
        * Create a new "HTTP(s) Monitor".
        * For the URL, use the public URL of your Replit Repl (visible in the "Preview" pane when your bot is running, e.g., `https://your-repl-name.your-username.repl.co`).
        * Set the monitoring interval to 5 or 10 minutes. This will periodically ping your Replit web server, preventing it from sleeping.
6.  **Run the Bot:**
    * Click the green **"Run"** button in Replit. Check the "Console" tab for any errors. If successful, your bot will be online!

### Deployment on Render (Alternative Free Hosting)

Render provides a more production-like environment for web services.

1.  **Push to GitHub:** Ensure your entire bot code (including `main.py`, `requirements.txt`, and `Procfile`) is pushed to a GitHub repository. **Make sure you have removed `keep_alive.py` and all references to it from `main.py` when deploying to Render, as it's not needed there.** Your `if __name__ == '__main__':` block in `main.py` should be simply `asyncio.run(main())`.
2.  **Create Web Service on Render:**
    * Go to [Render.com](https://render.com/) and sign in with GitHub.
    * Click **"New +"** -> **"Web Service"**.
    * Connect your GitHub repository (e.g., `MuskanMusicBot`).
    * **Configure:**
        * **Name:** `muskan-music-bot` (or your preferred name)
        * **Region:** Choose a suitable region.
        * **Branch:** `main` (or `master`)
        * **Root Directory:** (leave blank)
        * **Runtime:** `Python 3`
        * **Build Command:** `pip install -r requirements.txt`
        * **Start Command:** `python main.py` (Render reads `Procfile` by default, but confirm this here).
        * **Instance Type:** `Free`
    * **Add Environment Variables (Advanced Section):**
        * `TOKEN`: Your Telegram Bot Token
        * `ADMIN_ID`: Your Telegram User ID
3.  **Deploy:** Click **"Create Web Service"** and monitor the build logs.
4.  **Uptime on Render Free Tier:** Similar to Replit, Render's free web services will spin down after 15 minutes of inactivity. To keep your bot always active, use an uptime monitoring service like [UptimeRobot](https://uptimerobot.com/) and point it to your bot's public Render URL (e.g., `https://your-service-name.onrender.com`).

## ⚠️ Troubleshooting

* **Bot not responding:**
    * Check the **Replit/Render console logs** for any `Error` or `Traceback` messages. This is the most crucial step.
    * Ensure your **bot token and admin ID are correct** in your environment variables/secrets.
    * Verify your **`requirements.txt`** is correct and all dependencies are installed.
    * Confirm your **UptimeRobot (or similar) is actively pinging** your bot's URL if using a free hosting tier.
* **"RuntimeError: This event loop is already running"**: This means you have duplicate `asyncio.run(main())` calls or `keep_alive()` calls. Ensure your `main.py` matches the correct structure where `keep_alive()` is called once *outside* and *before* `asyncio.run(main())` (for Replit), or removed entirely (for Render).

## 🤝 Contributing

Feel free to fork this repository, open issues, or submit pull requests to improve the Muskan Music Bot!

## 📝 License
MIT License
