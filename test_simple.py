#!/usr/bin/env python3
"""
Ultra simple test to see if telegram bot works at all
"""

import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler

load_dotenv()

async def start(update, context):
    await update.message.reply_text("Bot is working!")

def main():
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("No TELEGRAM_TOKEN found")
        return
    
    print("Creating application...")
    app = Application.builder().token(token).build()
    
    print("Adding handler...")
    app.add_handler(CommandHandler("start", start))
    
    print("Starting polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
