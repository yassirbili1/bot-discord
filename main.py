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


#store invite data
invite_cache = {}


# Replace 'your_token_here' with your actual bot token
TOKEN = 'MTQxODU5NzgzMzMyNTQxMjU2NQ.GuKDvF.-kwXx77MSj5i32fVm1Tr9HhGcoSx5WuPZ-XR0Q'
LOG_CHANNEL_ID = 1418593690011828415 # Replace with your log channel ID

# Intents are required for accessing certain information
intents = discord.Intents.default()
intents.message_content = True  # Enable if you need to read message content





@bot.event
async def on_ready():
    print(f'✅bot is online goo{bot.user}')

    #set bot activity
    activity = streaming=discord.Streaming(name="Playing !help ", url="https://www.twitch.tv/ALXAFRICAHUB")
    

    await bot.change_presence(activity=activity)


####################################
# FUNCTION AUDIT LOG
####################################
def get_log_channel(guild):
    """Get the log channel for a guild."""
    return guild.get_channel(LOG_CHANNEL_ID)

def create_log_embed(title,description,color,guild,timestamp=None):
    """create a standardized log embed"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=timestamp or datetime.utcnow()
    )
    embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
    return embed

async def get_audit_log_entry(guild, action, target=None, limit=5):
    """get audit log entry for an action"""
    try:
        async for entry in guild.audit_logs(limit=limit, action=action):
            if target is None or entry.target.id == target.id:
                return entry
    except:
        pass
    return None

####################################
# MEMBER JOIN/LEAVE LOGS
####################################

@bot.event
async def on_member_update(before, after):
    """Log member updates (roles, nickname,)"""
    log_channel = get_log_channel(after.guild)
    if not log_channel:
        return
    
    # Role changes
    if before.roles != after.roles:
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)

        if added_roles:
            roles = ', '.join([role.mention for role in added_roles])
            #try to get user who added the role from audit logs
            added_by = "Unknown"
            try:
                entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, after.id)
                if entry and entry.user:
                    added_by = str(entry.user.mention)
            except Exception:
                pass
            embed = create_log_embed(
                title="➕ role added",
                description=f"**member:** {after.mention} ({after})\n"
                            f"**roles added:** {roles}\n"
                            f"**added by:** {added_by}",
                color=discord.Color.green(),
                guild=after.guild
            )
            await log_channel.send(embed=embed)

        if removed_roles:
            roles = ', '.join([role.mention for role in removed_roles])
            #try to get user who removed the role from audit logs
            removed_by = "Unknown"
            try:
                entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, after.id)
                if entry and entry.user:
                    removed_by = str(entry.user.mention)
            except Exception:
                pass
            embed = create_log_embed(
                title="➖ role removed",
                description=f"**member:** {after.mention} ({after})\n"
                            f"**removed by:** {removed_by.mention if isinstance(removed_by, discord.Member) else removed_by}\n",
                color=discord.Color.orange(),
                guild=after.guild
            )
            await log_channel.send(embed=embed)

    # Nickname changes
    if before.display_name != after.display_name:
        embed = create_log_embed(
            title="✏️ nickname changed",
            description=f"**Member:** {after.mention} ({after})\n"
                        f"**Before:** {before.display_name}\n"
                        f"**After:** {after.display_name}\n"
                        f"**Member ID:** {after.id}",
            color=discord.Color.blue(),
            guild=after.guild
        )
        await log_channel.send(embed=embed)





bot.run(TOKEN)