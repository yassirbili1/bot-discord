import discord
from discord.ext import commands
import asyncio
import os
import yt_dlp
import aiohttp
from pystyle import Colors, Colorate
import random
import shutil
import subprocess
from datetime import datetime


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
intents.moderation = True  # Required for audit logs


#store invite data
invite_cache = {}


# Replace 'your_token_here' with your actual bot token
TOKEN = 'MTQxODU5NzgzMzMyNTQxMjU2NQ.GuKDvF.-kwXx77MSj5i32fVm1Tr9HhGcoSx5WuPZ-XR0Q'
LOG_CHANNEL_ID = 1418593690011828415 # Replace with your log channel ID

# Intents are required for accessing certain information
intents = discord.Intents.default()
intents.message_content = True  # Enable if you need to read message content


# Store voice clients and queues
voice_clients = {}
music_queues = {}
current_playing = {}

# YouTube DLP options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)



@bot.event
async def on_ready():
    """Cache all invites when bot starts up and set activity"""
    print(f'{bot.user} has logged in!')
    
    # Set bot activity/status
    activity = discord.Streaming(
        name="Playing !help",  # What the bot appears to be streaming
        url="https://www.twitch.tv/alxafricahub"  # Replace with actual Twitch URL
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    # Cache invites for all guilds
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            print(f"No permission to view invites in {guild.name}")
        except Exception as e:
            print(f"Error caching invites for {guild.name}: {e}")
    
    print(f"Bot is ready and streaming! Cached invites for {len(bot.guilds)} guilds.")


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
# MEMBER ACTION LOGS
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
            
            # Try to get user who added the role from audit logs
            added_by = "Unknown"
            try:
                entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, after)
                if entry and entry.user:
                    added_by = entry.user.mention
                    # Check if it was the member themselves (via role reaction, etc.)
                    if entry.user.id == after.id:
                        added_by = f"{entry.user.mention} (self-assigned)"
            except Exception as e:
                print(f"Error getting audit log for role add: {e}")
            
            embed = create_log_embed(
                title="➕ Role Added",
                description=f"**Member:** {after.mention} ({after})\n"
                            f"**Roles Added:** {roles}\n"
                            f"**Added By:** {added_by}\n"
                            f"**Member ID:** {after.id}",
                color=discord.Color.green(),
                guild=after.guild
            )
            await log_channel.send(embed=embed)

        if removed_roles:
            roles = ', '.join([role.mention for role in removed_roles])
            
            # Try to get user who removed the role from audit logs
            removed_by = "Unknown"
            try:
                entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.member_role_update, after)
                if entry and entry.user:
                    removed_by = entry.user.mention
                    # Check if it was the member themselves
                    if entry.user.id == after.id:
                        removed_by = f"{entry.user.mention} (self-removed)"
                    # Check for common bot actions
                    elif entry.user.bot:
                        removed_by = f"{entry.user.mention} (Bot)"
            except Exception as e:
                print(f"Error getting audit log for role remove: {e}")
            
            embed = create_log_embed(
                title="➖ Role Removed",
                description=f"**Member:** {after.mention} ({after})\n"
                            f"**Roles Removed:** {roles}\n"
                            f"**Removed By:** {removed_by}\n"
                            f"**Member ID:** {after.id}",
                color=discord.Color.orange(),
                guild=after.guild
            )
            await log_channel.send(embed=embed)

    # Nickname changes
    if before.display_name != after.display_name:
        # Try to get who changed the nickname
        changed_by = "Unknown"
        try:
            entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.member_update, after)
            if entry and entry.user:
                changed_by = entry.user.mention
                if entry.user.id == after.id:
                    changed_by = f"{entry.user.mention} (self-changed)"
        except Exception as e:
            print(f"Error getting audit log for nickname change: {e}")
        
        embed = create_log_embed(
            title="✏️ Nickname Changed",
            description=f"**Member:** {after.mention} ({after})\n"
                        f"**Before:** {before.display_name}\n"
                        f"**After:** {after.display_name}\n"
                        f"**Changed By:** {changed_by}\n"
                        f"**Member ID:** {after.id}",
            color=discord.Color.blue(),
            guild=after.guild
        )
        await log_channel.send(embed=embed)

################################
# ban/unban logs
################################# 
@bot.event
async def on_member_ban(guild, user):
    """Log when a member is banned"""
    log_channel = get_log_channel(guild)
    if not log_channel:
        return
    
    # Get ban info from audit logs
    entry = await get_audit_log_entry(guild, discord.AuditLogAction.ban, user)
    ban_reason = entry.reason if entry and entry.reason else "No reason provided"
    banned_by = entry.user.mention if entry and entry.user else "Unknown"  # Fixed typo here
    
    embed = create_log_embed(
        title="🔨 Member Banned",
        description=(
            f"**Member:** {user} ({user.id})\n"
            f"**Banned by:** {banned_by}\n"
            f"**Reason:** {ban_reason}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.red(),
        guild=guild
    )
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    else:
        embed.set_thumbnail(url=user.default_avatar.url)

    await log_channel.send(embed=embed)

@bot.event
async def on_member_unban(guild, user):
    """Log when a member is unbanned"""
    log_channel = get_log_channel(guild)
    if not log_channel:
        return
    
    # Get unban info from audit logs
    entry = await get_audit_log_entry(guild, discord.AuditLogAction.unban, user)
    unbanned_by = entry.user.mention if entry and entry.user else "Unknown"
    unban_reason = entry.reason if entry and entry.reason else "No reason provided"
    
    embed = create_log_embed(
        title="🔓 Member Unbanned",
        description=(
            f"**Member:** {user} ({user.id})\n"
            f"**Unbanned by:** {unbanned_by}\n"
            f"**Reason:** {unban_reason}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.green(),
        guild=guild
    )
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)
    else:
        embed.set_thumbnail(url=user.default_avatar.url)

    await log_channel.send(embed=embed)


################################
# kick/unkick logs
#################################

@bot.event
async def on_member_remove(member):
    """Log when a member leaves or is kicked"""
    log_channel = get_log_channel(member.guild)
    if not log_channel:
        return
    
    # Wait a bit for audit logs to populate
    await asyncio.sleep(1)
    
    # Check if it was a kick
    kick_entry = await get_audit_log_entry(member.guild, discord.AuditLogAction.kick, member)
    
    if kick_entry:
        # Member was kicked
        kick_reason = kick_entry.reason if kick_entry.reason else "No reason provided"
        kicked_by = kick_entry.user.mention if kick_entry.user else "Unknown"
        
        embed = create_log_embed(
            title="👢 Member Kicked",
            description=(
                f"**Member:** {member.mention} ({member})\n"
                f"**Kicked by:** {kicked_by}\n"
                f"**Reason:** {kick_reason}\n"
                f"**Member ID:** {member.id}\n"
                f"**Account Created:** {member.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            ),
            color=discord.Color.orange(),
            guild=member.guild
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)
            
        await log_channel.send(embed=embed)


###############################
# message delete/edit logs
###############################

@bot.event
async def on_message_delete(message):
    """Log when a message is deleted"""
    if message.author.bot:
        return  # Ignore bot messages
    
    log_channel = get_log_channel(message.guild)
    if not log_channel:
        return
    
    embed = create_log_embed(
        title="🗑️ Message Deleted",
        description=(
            f"**Author:** {message.author.mention} ({message.author})\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Message ID:** {message.id}\n"
            f"**Content:** {message.content if message.content else 'No text content'}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.dark_grey(),
        guild=message.guild
    )
    if message.attachments:
        embed.add_field(name="Attachments", value='\n'.join([att.url for att in message.attachments]), inline=False)
    
    await log_channel.send(embed=embed)


@bot.event
async def on_message_edit(before, after):
    """Log when a message is edited"""
    if before.author.bot:
        return  # Ignore bot messages
    
    log_channel = get_log_channel(before.guild)
    if not log_channel:
        return
    
    if before.content == after.content:
        return  # Ignore embed or attachment-only edits
    
    embed = create_log_embed(
        title="✏️ Message Edited",
        description=(
            f"**Author:** {before.author.mention} ({before.author})\n"
            f"**Channel:** {before.channel.mention}\n"
            f"**Message ID:** {before.id}\n"
            f"**Before:** {before.content if before.content else 'No text content'}\n"
            f"**After:** {after.content if after.content else 'No text content'}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.blue(),
        guild=before.guild
    )
    await log_channel.send(embed=embed)

###############################
# voice join/leave/move logs
###############################

@bot.event
async def on_voice_state_update(member, before, after):
    """Log when a member joins, leaves, or moves voice channels"""
    log_channel = get_log_channel(member.guild)
    if not log_channel:
        return

    action = None
    if before.channel is None and after.channel is not None:
        action = "🔊 Joined Voice Channel"
        description = (
            f"**Member:** {member.mention} ({member})\n"
            f"**Channel:** {after.channel.mention}\n"
            f"**Member ID:** {member.id}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        color = discord.Color.green()
    elif before.channel is not None and after.channel is None:
        action = "🔇 Left Voice Channel"
        description = (
            f"**Member:** {member.mention} ({member})\n"
            f"**Channel:** {before.channel.mention}\n"
            f"**Member ID:** {member.id}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        color = discord.Color.red()
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        action = "🔀 Moved Voice Channel"
        description = (
            f"**Member:** {member.mention} ({member})\n"
            f"**From:** {before.channel.mention}\n"
            f"**To:** {after.channel.mention}\n"
            f"**Member ID:** {member.id}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        color = discord.Color.orange()

    if action:
        embed = create_log_embed(
            title=action,
            description=description,
            color=color,
            guild=member.guild
        )
        await log_channel.send(embed=embed)

###############################
# server role/channel/invite updates
###############################

@bot.event
async def on_guild_role_create(role):
    """Log when a role is created"""
    log_channel = get_log_channel(role.guild)
    if not log_channel:
        return
    
    # Get who created the role from audit logs
    entry = await get_audit_log_entry(role.guild, discord.AuditLogAction.role_create, role)
    created_by = entry.user.mention if entry and entry.user else "Unknown"
    
    embed = create_log_embed(
        title="🆕 Role Created",
        description=(
            f"**Role:** {role.name} ({role.id})\n"
            f"**Created by:** {created_by}\n"
            f"**Color:** {role.color}\n"
            f"**Hoisted:** {role.hoist}\n"
            f"**Mentionable:** {role.mentionable}\n"
            f"**Position:** {role.position}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.green(),
        guild=role.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    """Log when a role is deleted"""
    log_channel = get_log_channel(role.guild)
    if not log_channel:
        return
    
    # Get who deleted the role from audit logs
    entry = await get_audit_log_entry(role.guild, discord.AuditLogAction.role_delete, role)
    deleted_by = entry.user.mention if entry and entry.user else "Unknown"
    
    embed = create_log_embed(
        title="🗑️ Role Deleted",
        description=(
            f"**Role:** {role.name} ({role.id})\n"
            f"**Deleted by:** {deleted_by}\n"
            f"**Color:** {role.color}\n"
            f"**Hoisted:** {role.hoist}\n"
            f"**Mentionable:** {role.mentionable}\n"
            f"**Position:** {role.position}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.red(),
        guild=role.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    """Log when a role is updated"""
    log_channel = get_log_channel(after.guild)
    if not log_channel:
        return
    
    # Get who updated the role from audit logs
    entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.role_update, after)
    updated_by = entry.user.mention if entry and entry.user else "Unknown"
    
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** {before.name} ➔ {after.name}")
    if before.color != after.color:
        changes.append(f"**Color:** {before.color} ➔ {after.color}")
    if before.hoist != after.hoist:
        changes.append(f"**Hoisted:** {before.hoist} ➔ {after.hoist}")
    if before.mentionable != after.mentionable:
        changes.append(f"**Mentionable:** {before.mentionable} ➔ {after.mentionable}")
    if before.position != after.position:
        changes.append(f"**Position:** {before.position} ➔ {after.position}")
    
    if not changes:
        return  # No significant changes to log
    
    embed = create_log_embed(
        title="✏️ Role Updated",
        description=(
            f"**Role:** {after.name} ({after.id})\n"
            f"**Updated by:** {updated_by}\n"
            f"**Changes:**\n" + "\n".join(changes) + "\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.blue(),
        guild=after.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_create(channel):
    """Log when a channel is created"""
    log_channel = get_log_channel(channel.guild)
    if not log_channel:
        return
    
    # Get who created the channel from audit logs
    entry = await get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_create, channel)
    created_by = entry.user.mention if entry and entry.user else "Unknown"
    
    embed = create_log_embed(
        title="🆕 Channel Created",
        description=(
            f"**Channel:** {channel.mention} ({channel.id})\n"
            f"**Type:** {str(channel.type).split('.')[-1].title()}\n"
            f"**Created by:** {created_by}\n"
            f"**Category:** {channel.category.mention if channel.category else 'None'}\n"
            f"**NSFW:** {channel.is_nsfw()}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.green(),
        guild=channel.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    """Log when a channel is deleted"""
    log_channel = get_log_channel(channel.guild)
    if not log_channel:
        return
    
    # Get who deleted the channel from audit logs
    entry = await get_audit_log_entry(channel.guild, discord.AuditLogAction.channel_delete, channel)
    deleted_by = entry.user.mention if entry and entry.user else "Unknown"
    
    embed = create_log_embed(
        title="🗑️ Channel Deleted",
        description=(
            f"**Channel:** {channel.name} ({channel.id})\n"
            f"**Type:** {str(channel.type).split('.')[-1].title()}\n"
            f"**Deleted by:** {deleted_by}\n"
            f"**Category:** {channel.category.mention if channel.category else 'None'}\n"
            f"**NSFW:** {channel.is_nsfw()}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.red(),
        guild=channel.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_channel_update(before, after):
    """Log when a channel is updated"""
    log_channel = get_log_channel(after.guild)
    if not log_channel:
        return
    
    # Get who updated the channel from audit logs
    entry = await get_audit_log_entry(after.guild, discord.AuditLogAction.channel_update, after)
    updated_by = entry.user.mention if entry and entry.user else "Unknown"
    
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** {before.name} ➔ {after.name}")
    if before.category != after.category:
        changes.append(f"**Category:** {before.category.mention if before.category else 'None'} ➔ {after.category.mention if after.category else 'None'}")
    if hasattr(before, 'is_nsfw') and before.is_nsfw() != after.is_nsfw():
        changes.append(f"**NSFW:** {before.is_nsfw()} ➔ {after.is_nsfw()}")
    if hasattr(before, 'bitrate') and before.bitrate != after.bitrate:
        changes.append(f"**Bitrate:** {before.bitrate} ➔ {after.bitrate}")
    if hasattr(before, 'user_limit') and before.user_limit != after.user_limit:
        changes.append(f"**User Limit:** {before.user_limit} ➔ {after.user_limit}")
    
    if not changes:
        return  # No significant changes to log
    
    embed = create_log_embed(
        title="✏️ Channel Updated",
        description=(
            f"**Channel:** {after.mention} ({after.id})\n"
            f"**Updated by:** {updated_by}\n"
            f"**Changes:**\n" + "\n".join(changes) + "\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.blue(),
        guild=after.guild
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_guild_invite_create(invite):
    """Log when an invite is created"""
    log_channel = get_log_channel(invite.guild)
    if not log_channel:
        return
    
    # Get who created the invite from audit logs
    entry = await get_audit_log_entry(invite.guild, discord.AuditLogAction.invite_create, None)
    created_by = entry.user.mention if entry and entry.user else "Unknown"
    
    embed = create_log_embed(
        title="🆕 Invite Created",
        description=(
            f"**Invite:** {invite.url}\n"
            f"**Code:** {invite.code}\n"
            f"**Created by:** {created_by}\n"
            f"**Channel:** {invite.channel.mention if invite.channel else 'Unknown'}\n"
            f"**Max Uses:** {invite.max_uses if invite.max_uses else 'Unlimited'}\n"
            f"**Temporary:** {invite.temporary}\n"
            f"**Expires At:** {invite.expires_at.strftime('%Y-%m-%d %H:%M:%S') if invite.expires_at else 'Never'} UTC\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ),
        color=discord.Color.green(),
        guild=invite.guild
    )
    await log_channel.send(embed=embed)

#######################################################################
# FUNCTION HELP
#######################################################################

@bot.command(name='help')
async def help_command(ctx, section=None):
    """Comprehensive help command for the bot"""
    
    if section is None:
        # Main help embed
        embed = discord.Embed(
            title="🤖 Bot Help Center",
            description="Welcome to the help center! This bot provides comprehensive server logging and music functionality.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Add bot info
        embed.add_field(
            name="📊 Bot Information",
            value=f"**Status:** Online\n**Prefix:** `!`\n**Servers:** {len(bot.guilds)}\n**Latency:** {round(bot.latency * 1000)}ms",
            inline=True
        )
        
        # Add help sections
        embed.add_field(
            name="🎵 Music Commands",
            value="`!help music` - View music commands",
            inline=True
        )
        
        embed.add_field(
            name="📝 Logging Features",
            value="`!help logging` - View logging features",
            inline=True
        )
        
        embed.add_field(
            name="🛠️ Utility Commands",
            value="`!help utility` - View utility commands",
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ Bot Info",
            value="`!help info` - View detailed bot information",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Support",
            value="`!help support` - Get support information",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
        
        await ctx.send(embed=embed)
    
    elif section.lower() == 'music':
        # Music help embed
        embed = discord.Embed(
            title="🎵 Music Commands",
            description="Control music playback in voice channels",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        music_commands = [
            ("!play <song/url>", "Play a song from YouTube or search"),
            ("!pause", "Pause the current song"),
            ("!resume", "Resume playback"),
            ("!skip", "Skip the current song"),
            ("!stop", "Stop playback and clear queue"),
            ("!queue", "View the current music queue"),
            ("!volume <1-100>", "Adjust playback volume"),
            ("!nowplaying", "Show currently playing song"),
            ("!disconnect", "Disconnect from voice channel")
        ]
        
        for command, description in music_commands:
            embed.add_field(name=command, value=description, inline=False)
        
        embed.add_field(
            name="📋 Requirements",
            value="• You must be in a voice channel\n• Bot needs permission to join voice channels\n• Supports YouTube URLs and search queries",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
    
    elif section.lower() == 'logging':
        # Logging help embed
        embed = discord.Embed(
            title="📝 Server Logging Features",
            description="Automatic logging of server activities to the configured log channel",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        logging_features = [
            ("👤 Member Actions", "Join/Leave tracking\nRole additions/removals\nNickname changes"),
            ("🔨 Moderation", "Bans/Unbans\nKicks\nTimeouts"),
            ("💬 Messages", "Message deletions\nMessage edits\nAttachment logging"),
            ("🔊 Voice Activity", "Voice channel joins/leaves\nVoice channel moves"),
            ("🛠️ Server Changes", "Role creation/deletion/updates\nChannel creation/deletion/updates\nInvite creation"),
            ("🎯 Invite Tracking", "Track who joins with which invite\nInvite usage statistics")
        ]
        
        for feature, description in logging_features:
            embed.add_field(name=feature, value=description, inline=True)
        
        embed.add_field(
            name="⚙️ Configuration",
            value=f"**Log Channel ID:** {LOG_CHANNEL_ID}\n**Audit Log Access:** Required for detailed logging\n**Automatic:** All logging is automatic once configured",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
    
    elif section.lower() == 'utility':
        # Utility help embed
        embed = discord.Embed(
            title="🛠️ Utility Commands",
            description="Helpful utility commands for server management",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
        
        utility_commands = [
            ("!help", "Show this help menu"),
            ("!help <section>", "Show help for specific section"),
            ("!ping", "Check bot latency"),
            ("!serverinfo", "Display server information"),
            ("!userinfo [@user]", "Display user information"),
            ("!inviteinfo", "Show server invite statistics")
        ]
        
        for command, description in utility_commands:
            embed.add_field(name=command, value=description, inline=False)
        
        embed.add_field(
            name="📊 Available Sections",
            value="`music` • `logging` • `utility` • `info` • `support`",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
    
    elif section.lower() == 'info':
        # Bot info embed
        embed = discord.Embed(
            title="ℹ️ Bot Information",
            description="Detailed information about this Discord bot",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🤖 Bot Details",
            value=f"**Name:** {bot.user.name}\n**ID:** {bot.user.id}\n**Created:** {bot.user.created_at.strftime('%Y-%m-%d')}\n**Prefix:** `!`",
            inline=True
        )
        
        embed.add_field(
            name="📊 Statistics",
            value=f"**Servers:** {len(bot.guilds)}\n**Users:** {len(bot.users)}\n**Channels:** {len(list(bot.get_all_channels()))}\n**Commands:** 15+",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Technical Info",
            value=f"**Python Version:** 3.8+\n**Discord.py Version:** 2.0+\n**Latency:** {round(bot.latency * 1000)}ms\n**Uptime:** Since last restart",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Main Features",
            value="• **Comprehensive Logging** - Track all server activities\n• **Music Player** - Play music from YouTube\n• **Invite Tracking** - Monitor server invites\n• **Moderation Logs** - Track bans, kicks, and more",
            inline=False
        )
        
        embed.add_field(
            name="🔐 Permissions Required",
            value="• Read Messages\n• Send Messages\n• Embed Links\n• Connect to Voice\n• Speak in Voice\n• View Audit Log\n• Manage Channels (for logging)",
            inline=False
        )
        
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
    
    elif section.lower() == 'support':
        # Support embed
        embed = discord.Embed(
            title="🔧 Support & Information",
            description="Need help or have questions? Here's how to get support",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🆘 Common Issues",
            value="• **Music not playing:** Check voice channel permissions\n• **Logs not appearing:** Verify log channel ID and permissions\n• **Commands not working:** Ensure proper prefix `!`",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Troubleshooting",
            value="1. Check bot permissions in channel\n2. Verify bot role hierarchy\n3. Ensure bot has required intents\n4. Try rejoining voice channel for music issues",
            inline=False
        )
        
        embed.add_field(
            name="📞 Getting Help",
            value="• Use `!help <section>` for specific help\n• Check bot permissions if commands fail\n• Contact server administrators for setup issues",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Useful Links",
            value="• **Streaming:** [Twitch](https://www.twitch.tv/alxafricahub)\n• **Bot Status:** Online ✅\n• **Last Updated:** Recently",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)
    
    else:
        # Invalid section
        embed = discord.Embed(
            title="❌ Invalid Help Section",
            description=f"The section `{section}` doesn't exist.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📋 Available Sections",
            value="`music` • `logging` • `utility` • `info` • `support`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Usage",
            value="Use `!help` for the main menu or `!help <section>` for specific help.",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=embed)

# Additional utility commands that complement the help system

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: **{latency}ms**",
        color=discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def serverinfo(ctx):
    """Display server information"""
    guild = ctx.guild
    embed = discord.Embed(
        title=f"📊 {guild.name} Server Info",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name="Region", value=str(guild.region) if hasattr(guild, 'region') else "Unknown", inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(text=f"Server ID: {guild.id}")
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def userinfo(ctx, member: discord.Member = None):
    """Display user information"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name="Username", value=str(member), inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime('%Y-%m-%d %H:%M'), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime('%Y-%m-%d %H:%M'), inline=True)
    embed.add_field(name="Roles", value=len(member.roles) - 1, inline=True)  # -1 to exclude @everyone
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    else:
        embed.set_thumbnail(url=member.default_avatar.url)
    
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)







bot.run(TOKEN)