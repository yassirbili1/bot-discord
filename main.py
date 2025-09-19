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





############################################################################
# VOICE FUNCTIONS
############################################################################




@bot.event
async def on_voice_state_update(member, before, after):
    """Auto-disconnect when bot is alone in voice channel"""
    if member == bot.user:
        return
    
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if voice_client and voice_client.channel:
        # Check if bot is alone in the voice channel
        if len(voice_client.channel.members) == 1:  # Only the bot
            await asyncio.sleep(60)  # Wait 1 minute
            # Double check if still alone
            if voice_client.is_connected() and len(voice_client.channel.members) == 1:
                await voice_client.disconnect()
                if member.guild.id in music_queues:
                    music_queues[member.guild.id].clear()
                print(f"🔇 Left {voice_client.channel.name} (alone in channel)")

# ========================================
# VOICE COMMANDS
# ========================================

@bot.command(name='join', aliases=['connect', 'j'])
async def join_voice(ctx):
    """Join the voice channel you're in"""
    if not ctx.author.voice:
        embed = discord.Embed(
            title="❌ Error", 
            description="You need to be in a voice channel!", 
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    channel = ctx.author.voice.channel
    
    if ctx.voice_client:
        if ctx.voice_client.channel == channel:
            embed = discord.Embed(
                title="ℹ️ Info", 
                description="Already connected to this channel!", 
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    embed = discord.Embed(
        title="🎵 Connected!", 
        description=f"Joined **{channel.name}**", 
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='leave', aliases=['disconnect', 'dc'])
async def leave_voice(ctx):
    """Leave the voice channel"""
    if not ctx.voice_client:
        embed = discord.Embed(
            title="❌ Error", 
            description="I'm not connected to a voice channel!", 
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    # Clear the queue
    if ctx.guild.id in music_queues:
        music_queues[ctx.guild.id].clear()
    
    await ctx.voice_client.disconnect()
    embed = discord.Embed(
        title="👋 Disconnected", 
        description="Left the voice channel!", 
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='play', aliases=['p'])
async def play_music(ctx, *, search):
    """Play music from YouTube"""
    # Join voice channel if not connected
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            embed = discord.Embed(
                title="❌ Error", 
                description="You need to be in a voice channel!", 
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
    
    # Initialize queue if it doesn't exist
    if ctx.guild.id not in music_queues:
        music_queues[ctx.guild.id] = []
    
    # Show loading message
    loading_embed = discord.Embed(
        title="🔄 Loading...", 
        description=f"Searching for: **{search}**", 
        color=discord.Color.yellow()
    )
    message = await ctx.send(embed=loading_embed)
    
    try:
        # Get the song
        player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
        
        # Add to queue
        music_queues[ctx.guild.id].append(player)
        
        # Update embed
        embed = discord.Embed(
            title="✅ Added to Queue", 
            description=f"**{player.title}**", 
            color=discord.Color.green()
        )
        embed.add_field(name="Position in Queue", value=len(music_queues[ctx.guild.id]), inline=True)
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        
        await message.edit(embed=embed)
        
        # Start playing if nothing is currently playing
        if not ctx.voice_client.is_playing():
            await play_next(ctx)
            
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error", 
            description=f"Could not play: {str(e)}", 
            color=discord.Color.red()
        )
        await message.edit(embed=error_embed)

async def play_next(ctx):
    """Play the next song in queue"""
    if ctx.guild.id not in music_queues or not music_queues[ctx.guild.id]:
        return
    
    if ctx.voice_client and not ctx.voice_client.is_playing():
        player = music_queues[ctx.guild.id].pop(0)
        current_playing[ctx.guild.id] = player
        
        def after_playing(error):
            if error:
                print(f'Player error: {error}')
            
            # Play next song
            coro = play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except:
                pass
        
        ctx.voice_client.play(player, after=after_playing)
        
        # Now playing embed
        embed = discord.Embed(
            title="🎵 Now Playing", 
            description=f"**{player.title}**", 
            color=discord.Color.purple()
        )
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        embed.add_field(name="Remaining in Queue", value=len(music_queues[ctx.guild.id]), inline=True)
        
        await ctx.send(embed=embed)

@bot.command(name='skip', aliases=['s', 'next'])
async def skip_song(ctx):
    """Skip the current song"""
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Error", 
            description="Nothing is currently playing!", 
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    ctx.voice_client.stop()
    embed = discord.Embed(
        title="⏭️ Skipped", 
        description="Skipped to next song!", 
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='pause')
async def pause_song(ctx):
    """Pause the current song"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        embed = discord.Embed(
            title="⏸️ Paused", 
            description="Music paused!", 
            color=discord.Color.yellow()
        )
        await ctx.send(embed=embed)

@bot.command(name='resume')
async def resume_song(ctx):
    """Resume the paused song"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        embed = discord.Embed(
            title="▶️ Resumed", 
            description="Music resumed!", 
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

@bot.command(name='stop')
async def stop_music(ctx):
    """Stop music and clear queue"""
    if ctx.voice_client:
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        ctx.voice_client.stop()
        embed = discord.Embed(
            title="⏹️ Stopped", 
            description="Music stopped and queue cleared!", 
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='queue', aliases=['q'])
async def show_queue(ctx):
    """Show the music queue"""
    if ctx.guild.id not in music_queues or not music_queues[ctx.guild.id]:
        embed = discord.Embed(
            title="📜 Queue Empty", 
            description="No songs in queue!", 
            color=discord.Color.blue()
        )
        return await ctx.send(embed=embed)
    
    queue_list = []
    for i, player in enumerate(music_queues[ctx.guild.id][:10], 1):  # Show first 10
        queue_list.append(f"**{i}.** {player.title}")
    
    embed = discord.Embed(
        title="📜 Music Queue", 
        description="\n".join(queue_list), 
        color=discord.Color.purple()
    )
    
    if len(music_queues[ctx.guild.id]) > 10:
        embed.add_field(name="+ More", value=f"{len(music_queues[ctx.guild.id]) - 10} more songs...", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='nowplaying', aliases=['np'])
async def now_playing(ctx):
    """Show currently playing song"""
    if ctx.guild.id not in current_playing:
        embed = discord.Embed(
            title="❌ Nothing Playing", 
            description="No song is currently playing!", 
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    player = current_playing[ctx.guild.id]
    embed = discord.Embed(
        title="🎵 Now Playing", 
        description=f"**{player.title}**", 
        color=discord.Color.purple()
    )
    if player.thumbnail:
        embed.set_thumbnail(url=player.thumbnail)
    
    await ctx.send(embed=embed)

@bot.command(name='volume', aliases=['vol'])
async def change_volume(ctx, volume: int = None):
    """Change or show the volume (0-100)"""
    if not ctx.voice_client:
        embed = discord.Embed(
            title="❌ Error", 
            description="Not connected to voice channel!", 
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    if volume is None:
        current_vol = int(ctx.voice_client.source.volume * 100) if hasattr(ctx.voice_client.source, 'volume') else 50
        embed = discord.Embed(
            title="🔊 Current Volume", 
            description=f"Volume is at **{current_vol}%**", 
            color=discord.Color.blue()
        )
        return await ctx.send(embed=embed)
    
    if 0 <= volume <= 100:
        if hasattr(ctx.voice_client.source, 'volume'):
            ctx.voice_client.source.volume = volume / 100
            embed = discord.Embed(
                title="🔊 Volume Changed", 
                description=f"Volume set to **{volume}%**", 
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Error", 
            description="Volume must be between 0 and 100!", 
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='clear')
async def clear_queue(ctx):
    """Clear the music queue"""
    if ctx.guild.id in music_queues:
        music_queues[ctx.guild.id].clear()
        embed = discord.Embed(
            title="🗑️ Queue Cleared", 
            description="Music queue has been cleared!", 
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

# ========================================
# HELP COMMAND
# ========================================
@bot.command(name='musichelp', aliases=['mhelp'])
async def music_help(ctx):
    """Show music commands"""
    embed = discord.Embed(
        title="🎵 Music Bot Commands", 
        color=discord.Color.purple()
    )
    
    commands_list = [
        "**!join** - Join your voice channel",
        "**!leave** - Leave voice channel",
        "**!play <song>** - Play a song from YouTube",
        "**!pause** - Pause current song",
        "**!resume** - Resume paused song",
        "**!skip** - Skip current song",
        "**!stop** - Stop music and clear queue",
        "**!queue** - Show music queue",
        "**!nowplaying** - Show current song",
        "**!volume <0-100>** - Change volume",
        "**!clear** - Clear queue"
    ]
    
    embed.description = "\n".join(commands_list)
    embed.set_footer(text="Use !play <song name or URL> to start!")
    
    await ctx.send(embed=embed)

# ========================================
# ERROR HANDLING
# ========================================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument", 
            description="Please provide the required arguments!", 
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        print(f"Error: {error}")






bot.run(TOKEN)