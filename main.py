import discord
from discord.ext import commands
from pystyle import Colors,Colorate  # type: ignore
from datetime import datetime
import random
import asyncio
import os
import yt_dlp
import aiohttp



# ========================================
# BOT INSTANCE
# ========================================
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.voice_states = True
intents.invites = True
bot = commands.Bot(command_prefix="!", intents=intents)





# Replace 'your_token_here' with your actual bot token
TOKEN = 'MTQxODU5NzgzMzMyNTQxMjU2NQ.GuKDvF.-kwXx77MSj5i32fVm1Tr9HhGcoSx5WuPZ-XR0Q'

# Intents are required for accessing certain information
intents = discord.Intents.default()
intents.message_content = True  # Enable if you need to read message content





@bot.event
async def on_ready():
    print(f'✅bot is online goo{bot.user}')

    #set bot activity
    activity = streaming=discord.Streaming(name="Playing !help ", url="https://www.twitch.tv/ALXAFRICAHUB")
    

    await bot.change_presence(activity=activity)








bot.run(TOKEN)