# Ticket Button View
class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔹 Support", style=discord.ButtonStyle.success, custom_id="create_ticket")
    async def ticket_button(self, interaction: discord.Interaction, button: Button):
        global TICKET_COUNTER
        TICKET_COUNTER += 1
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=SUPPORT_TICKET_CATEGORY_ID) if SUPPORT_TICKET_CATEGORY_ID else None

        ticket_name = f"Support Ticket-{interaction.user.name}-{TICKET_COUNTER}-"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if STAFF_ROLE_ID:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {interaction.user.name}"
        )
        
        embed = discord.Embed(
            title="🎫 New Support Ticket Created",
            description=f"**Opened by:** {interaction.user.mention}\n\nPlease describe your issue and wait for staff to assist you.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Ticket #{TICKET_COUNTER}")
        
        control_view = TicketControlView()
        await channel.send(f"{interaction.user.mention}", embed=embed, view=control_view)
        await interaction.response.send_message(f"✅ Support Ticket created! {channel.mention}", ephemeral=True)

    @discord.ui.button(label="💳 Purchase", style=discord.ButtonStyle.primary, custom_id="create_purchase_ticket")
    async def purchase_ticket_button(self, interaction: discord.Interaction, button: Button):
        global TICKET_COUNTER
        TICKET_COUNTER += 1

        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=PURCHASE_TICKET_CATEGORY_ID) if PURCHASE_TICKET_CATEGORY_ID else None

        ticket_name = f"Purchase Ticket-{interaction.user.name}-{TICKET_COUNTER}-"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        if STAFF_ROLE_ID:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {interaction.user.name}"
        )

        embed = discord.Embed(
            title="💳 New Purchase Ticket Created",
            description=f"**Opened by:** {interaction.user.mention}\n\nPlease describe the Bug and wait for staff to assist you.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Ticket #{TICKET_COUNTER}")

        control_view = TicketControlView()
        await channel.send(f"{interaction.user.mention}", embed=embed, view=control_view)
        await interaction.response.send_message(f"✅ Purchase Ticket created! {channel.mention}", ephemeral=True)

    @discord.ui.button(label="🐞 Bug", style=discord.ButtonStyle.danger, custom_id="create_bug_ticket")
    async def bug_ticket_button(self, interaction: discord.Interaction, button: Button):
         global TICKET_COUNTER
         TICKET_COUNTER += 1

         guild = interaction.guild
         category = discord.utils.get(guild.categories, id=BUG_TICKET_CATEGORY_ID) if BUG_TICKET_CATEGORY_ID else None

         ticket_name = f"Bug Ticket-{interaction.user.name}-{TICKET_COUNTER}-"

         overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

         if STAFF_ROLE_ID:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

         channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {interaction.user.name}"
        )

         embed = discord.Embed(
            title="🐞 Bug New Bug Ticket Created",
            description=f"**Opened by:** {interaction.user.mention}\n\nPlease describe the Bug and wait for staff to assist you.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
         embed.set_footer(text=f"Ticket #{TICKET_COUNTER}")

         control_view = TicketControlView()
         await channel.send(f"{interaction.user.mention}", embed=embed, view=control_view)
         await interaction.response.send_message(f"✅ Bug Ticket created! {channel.mention}", ephemeral=True)



# Command to send ticket panel
@bot.tree.command(name="ticket-panel", description="Send the ticket panel with button")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Need help? Click the button below to create a help ticket.\n\n**📌 Interact with the topic ticket based on what you need:**\n",
        color=discord.Color.blue()
    )

    embed.set_image(url="https://r2.fivemanage.com/2Fmxtyz3enFCAcfC5wghD/evolutionbanner.png")
    embed.set_thumbnail(url="https://r2.fivemanage.com/2Fmxtyz3enFCAcfC5wghD/evolutionlogotransparantbg.png")


    embed.add_field(name="📋 The Button Ticket", value="🔹 Support → If you need general help with the server (rules, features, or how something works).\n\n  💳 Purchase → If you are interested in buying a pack, benefit, or service within the server.\n\n  🐞 Bug → If you found an error, glitch, or bug in the server and want to report it so we can fix it.", inline=False)
    embed.set_footer(text="Our staff will respond as soon as possible")
    
    view = TicketButton()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Ticket panel sent!", ephemeral=True)