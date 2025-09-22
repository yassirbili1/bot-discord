import discord
from discord.ext import commands
from datetime import timedelta
import asyncio
import os
import yt_dlp
import aiohttp
from pystyle import Colors, Colorate
import random
import shutil
import subprocess
from datetime import datetime
import imageio_ffmpeg as ffmpeg


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
tree = bot.tree  # Slash command handler
intents.moderation = True  # Required for audit logs


#store invite data
invite_cache = {}


TOKEN = os.getenv('TOKEN')
if not TOKEN:
    print("TOKEN not found!")
else:
    print(f"Token loaded: {TOKEN[:10]}...")  # Shows first 10 chars only



LOG_CHANNEL_ID = 1418593690011828415 # Replace with your log channel ID

# Intents are required for accessing certain information
intents = discord.Intents.default()
intents.message_content = True  # Enable if you need to read message content


# Store voice clients and queues
voice_clients = {}
music_queues = {}
current_playing = {}


FFMPEG_PATH = ffmpeg.get_ffmpeg_exe()


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


##########################################################################
# give ban/unban/kick/unkick/timeout
##########################################################################

# Ban command
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"{member} has been banned. Reason: {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user: discord.User):
    try:
        await ctx.guild.unban(user)
        await ctx.send(f"{user} has been unbanned.")
    except Exception as e:
        await ctx.send(f"Failed to unban {user}: {e}")



# Kick command
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"{member} has been kicked. Reason: {reason}")


# "Unkick" (send invite)
@bot.command()
async def unkick(ctx, member: discord.User):
    invite = await ctx.channel.create_invite(max_uses=1, unique=True)
    try:
        await member.send(f"You were kicked, but here's an invite to return: {invite.url}")
        await ctx.send(f"Invite sent to {member}.")
    except discord.Forbidden:
        await ctx.send("Couldn't DM the user. They may have DMs disabled.")


# Timeout command
@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, seconds: int, *, reason=None):
    """Timeout a member for a certain number of seconds"""
    try:
        duration = timedelta(seconds=seconds)
        await member.timeout_for(duration, reason=reason)
        await ctx.send(f"✅ {member.mention} has been timed out for {seconds} seconds. Reason: {reason or 'No reason provided'}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout this member.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


# Remove timeout
@bot.command()
@commands.has_permissions(moderate_members=True)
async def remove_timeout(ctx, member: discord.Member):
    try:
        await member.timeout_for(None)
        await ctx.send(f"Timeout removed from {member}.")
    except discord.Forbidden:
        await ctx.send("I don't have permission to remove timeout from this member.")


# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing arguments. Please provide all required information.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Couldn't find the user. Check the name and try again.")
    else:
        raise error  # Let the error propagate for debugging
    

#########################################
# SEND MESSAGE MEMBERS TO DM
#########################################

@bot.command()
@commands.has_permissions(administrator=True)
async def dm_all(ctx, *, message):
    """DM all members in the server"""
    success_count = 0
    fail_count = 0
    for member in ctx.guild.members:
        if member.bot:
            continue  # Skip bots
        try:
            await member.send(message)
            success_count += 1
            await asyncio.sleep(1)  # Sleep to avoid rate limits
        except Exception as e:
            fail_count += 1
            print(f"Failed to DM {member}: {e}")
    await ctx.send(f"DM sent to {success_count} members. Failed to DM {fail_count} members.")

###########################################
# send dm to member
###########################################

@bot.command()
@commands.has_permissions(administrator=True)
async def dm_member(ctx, member: discord.Member, *, message):
    """DM a specific member"""
    try:
        await member.send(message)
        await ctx.send(f"DM sent to {member}.")
    except Exception as e:
        await ctx.send(f"Failed to DM {member}: {e}")







bot.run(TOKEN)