"""
Star Citizen Guild Inventory Bot
─────────────────────────────────
Commands
  /add-item        – Add items to an inventory
  /remove-item     – Remove items from an inventory
  /get-item        – Look up who owns an item and where
  /inventory       – View a user's full inventory
  /set-channel     – Restrict the bot to a specific channel (managers only)
  /add-ship        – Add a ship to a user's hangar (autocomplete from full ship list)
  /remove-ship     – Remove a ship from a user's hangar
  /add-resource    – Add a mined resource or gem to a user's stock
  /remove-resource – Remove a resource from a user's stock
  /get-resource    – Look up who owns a resource across the guild
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from typing import Optional
import database as db
from ships import search_ships
from resources import search_resources, is_scu_resource, get_unit_label, is_known_resource

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MANAGER_ROLE_NAME = os.getenv("MANAGER_ROLE", "SC-Manager")   # role that can edit anyone

# ── bot setup ──────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# ── permission helper ──────────────────────────────────────────────────────────

def is_manager(member: discord.Member) -> bool:
    """Return True if the member has the manager role or is the guild owner."""
    if member.guild.owner_id == member.id:
        return True
    return any(r.name == MANAGER_ROLE_NAME for r in member.roles)


# ── channel guard ─────────────────────────────────────────────────────────────

async def check_channel(interaction: discord.Interaction) -> bool:
    """
    Return True if the command is allowed in this channel.
    If a restriction is set and the channel doesn't match, send an ephemeral
    error and return False so the command handler exits early.
    """
    allowed_id = db.get_allowed_channel(str(interaction.guild_id))
    if allowed_id is None:
        return True                        # no restriction configured
    if str(interaction.channel_id) == allowed_id:
        return True
    channel = interaction.guild.get_channel(int(allowed_id))
    mention = channel.mention if channel else f"<#{allowed_id}>"
    await interaction.response.send_message(
        f"⚠️ This bot can only be used in {mention}.",
        ephemeral=True,
    )
    return False


# ── autocomplete helpers ───────────────────────────────────────────────────────

async def item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    guild_id = str(interaction.guild_id)
    names = db.search_items(guild_id, current)
    return [app_commands.Choice(name=n, value=n) for n in names]


# ── /add-item ──────────────────────────────────────────────────────────────────

@tree.command(
    name="add-item",
    description="Add an item to a user's inventory.",
)
@app_commands.describe(
    item_name="Name of the Star Citizen item",
    quantity="How many to add (default: 1)",
    location="Where the item is stored (optional)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(item_name=item_autocomplete)
async def add_item(
    interaction: discord.Interaction,
    item_name: str,
    quantity: Optional[int] = 1,
    location: Optional[str] = None,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    # Permission check
    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's inventory.",
            ephemeral=True,
        )
        return

    if quantity is None or quantity < 1:
        await interaction.followup.send("❌ Quantity must be at least 1.", ephemeral=True)
        return

    row = db.upsert_item(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        item_name=item_name,
        quantity=quantity,
        location=location,
    )

    embed = discord.Embed(
        title="✅ Item Added",
        color=discord.Color.from_rgb(0, 180, 255),
    )
    embed.add_field(name="Item", value=row["item_name"], inline=True)
    embed.add_field(name="Qty Added", value=str(quantity), inline=True)
    embed.add_field(name="New Total", value=str(row["quantity"]), inline=True)
    if row["location"]:
        embed.add_field(name="Location", value=row["location"], inline=True)
    embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /remove-item ───────────────────────────────────────────────────────────────

@tree.command(
    name="remove-item",
    description="Remove an item from a user's inventory.",
)
@app_commands.describe(
    item_name="Name of the item to remove",
    quantity="How many to remove (default: 1)",
    location="Remove from a specific location only (optional)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(item_name=item_autocomplete)
async def remove_item(
    interaction: discord.Interaction,
    item_name: str,
    quantity: Optional[int] = 1,
    location: Optional[str] = None,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's inventory.",
            ephemeral=True,
        )
        return

    if quantity is None or quantity < 1:
        await interaction.followup.send("❌ Quantity must be at least 1.", ephemeral=True)
        return

    success, message = db.remove_item(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        item_name=item_name,
        quantity=quantity,
        location=location,
    )

    color = discord.Color.green() if success else discord.Color.red()
    embed = discord.Embed(
        title="🗑️ Remove Item" if success else "❌ Remove Failed",
        description=message,
        color=color,
    )
    if success:
        embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /get-item ──────────────────────────────────────────────────────────────────

@tree.command(
    name="get-item",
    description="Look up who owns an item, how many, and where.",
)
@app_commands.describe(item_name="Item name to search across the whole guild")
@app_commands.autocomplete(item_name=item_autocomplete)
async def get_item(
    interaction: discord.Interaction,
    item_name: str,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer()

    rows = db.get_item_info(
        guild_id=str(interaction.guild_id),
        item_name=item_name,
    )

    if not rows:
        embed = discord.Embed(
            title=f"🔍 {item_name}",
            description="Nobody in this org owns that item.",
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"🔍 {item_name}",
        color=discord.Color.from_rgb(0, 180, 255),
    )

    total = sum(r["quantity"] for r in rows)
    embed.description = f"**{total}** total across the org"

    for row in rows:
        member = interaction.guild.get_member(int(row["user_id"]))
        owner_name = member.display_name if member else f"<@{row['user_id']}>"
        loc_str = f"📍 {row['location']}" if row["location"] else "📍 *No location set*"
        embed.add_field(
            name=f"{owner_name}  ×{row['quantity']}",
            value=loc_str,
            inline=False,
        )

    await interaction.followup.send(embed=embed)


# ── /inventory ─────────────────────────────────────────────────────────────────

@tree.command(
    name="inventory",
    description="View a user's full inventory.",
)
@app_commands.describe(user="User to inspect (default: yourself)")
async def inventory(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    # Non-managers can only view their own inventory
    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to view another user's inventory.",
            ephemeral=True,
        )
        return

    rows = db.get_user_inventory(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
    )

    if not rows:
        embed = discord.Embed(
            title=f"📦 {target.display_name}'s Inventory",
            description="Inventory is empty.",
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # Build pages of up to 20 items each
    embed = discord.Embed(
        title=f"📦 {target.display_name}'s Inventory",
        color=discord.Color.from_rgb(0, 180, 255),
    )

    lines = []
    for row in rows:
        loc = f" — 📍 {row['location']}" if row["location"] else ""
        lines.append(f"• **{row['item_name']}** ×{row['quantity']}{loc}")

    # Discord embed description max = 4096 chars; chunk if needed
    chunks = []
    current = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > 3800:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("\n".join(current))

    embed.description = chunks[0]
    embed.set_footer(text=f"{len(rows)} item type(s) · {sum(r['quantity'] for r in rows)} total")

    await interaction.followup.send(embed=embed, ephemeral=True)

    # Send overflow pages
    for chunk in chunks[1:]:
        extra = discord.Embed(description=chunk, color=discord.Color.from_rgb(0, 180, 255))
        await interaction.followup.send(embed=extra, ephemeral=True)


# ── /add-ship & /remove-ship ───────────────────────────────────────────────────

async def ship_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=s, value=s) for s in search_ships(current)]


@tree.command(
    name="add-ship",
    description="Add a ship to a user's hangar.",
)
@app_commands.describe(
    ship_name="Ship name (autocomplete from the official roster)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(ship_name=ship_autocomplete)
async def add_ship(
    interaction: discord.Interaction,
    ship_name: str,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's hangar.",
            ephemeral=True,
        )
        return

    row = db.upsert_item(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        item_name=ship_name,
        quantity=1,
        location="Hangar",
    )

    embed = discord.Embed(
        title="🚀 Ship Added",
        color=discord.Color.from_rgb(0, 180, 255),
    )
    embed.add_field(name="Ship", value=row["item_name"], inline=False)
    embed.add_field(name="In Hangar", value=str(row["quantity"]), inline=True)
    embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(
    name="remove-ship",
    description="Remove a ship from a user's hangar.",
)
@app_commands.describe(
    ship_name="Ship to remove (autocomplete from the official roster)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(ship_name=ship_autocomplete)
async def remove_ship(
    interaction: discord.Interaction,
    ship_name: str,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's hangar.",
            ephemeral=True,
        )
        return

    success, message = db.remove_item(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        item_name=ship_name,
        quantity=1,
        location=None,
    )

    color = discord.Color.green() if success else discord.Color.red()
    embed = discord.Embed(
        title="🗑️ Ship Removed" if success else "❌ Remove Failed",
        description=message,
        color=color,
    )
    if success:
        embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /add-resource, /remove-resource, /get-resource ────────────────────────────

async def resource_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=r, value=r) for r in search_resources(current)]


@tree.command(
    name="add-resource",
    description="Add a mined resource (SCU) or gem (Units) to a user's stock.",
)
@app_commands.describe(
    resource_name="Resource name — SCU minerals or gem stones (autocomplete)",
    quantity="Amount in SCU or Units (decimals allowed for SCU)",
    quality="Ore quality 0–1000 — SCU resources only (optional)",
    location="Where the resource is stored (optional)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(resource_name=resource_autocomplete)
async def add_resource(
    interaction: discord.Interaction,
    resource_name: str,
    quantity: float,
    quality: Optional[int] = None,
    location: Optional[str] = None,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's stock.",
            ephemeral=True,
        )
        return

    if not is_known_resource(resource_name):
        await interaction.followup.send(
            f"❌ **{resource_name}** is not a recognised resource. Use autocomplete to pick one.",
            ephemeral=True,
        )
        return

    if quantity <= 0:
        await interaction.followup.send("❌ Quantity must be greater than 0.", ephemeral=True)
        return

    unit = get_unit_label(resource_name)

    if quality is not None:
        if unit != "SCU":
            await interaction.followup.send(
                "⚠️ Quality only applies to SCU resources (minerals). It has been ignored.",
                ephemeral=True,
            )
            quality = None
        elif not (0 <= quality <= 1000):
            await interaction.followup.send("❌ Quality must be between 0 and 1000.", ephemeral=True)
            return

    row = db.upsert_resource(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        resource_name=resource_name,
        quantity=quantity,
        unit=unit,
        quality=quality,
        location=location,
    )

    qty_display = f"{row['quantity']:.4g}"
    embed = discord.Embed(title="⛏️ Resource Added", color=discord.Color.from_rgb(0, 200, 140))
    embed.add_field(name="Resource", value=row["resource_name"], inline=True)
    embed.add_field(name="Added", value=f"{quantity:.4g} {unit}", inline=True)
    embed.add_field(name="New Total", value=f"{qty_display} {unit}", inline=True)
    if unit == "SCU" and row["quality"] is not None:
        embed.add_field(name="Quality", value=f"{row['quality']} / 1000", inline=True)
    if row["location"]:
        embed.add_field(name="Location", value=row["location"], inline=True)
    embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(
    name="remove-resource",
    description="Remove a resource from a user's stock.",
)
@app_commands.describe(
    resource_name="Resource to remove (autocomplete)",
    quantity="Amount to remove in SCU or Units",
    quality="Only remove from batches of this quality (optional, SCU only)",
    location="Only remove from this location (optional)",
    user="Target user — managers only (default: yourself)",
)
@app_commands.autocomplete(resource_name=resource_autocomplete)
async def remove_resource(
    interaction: discord.Interaction,
    resource_name: str,
    quantity: float,
    quality: Optional[int] = None,
    location: Optional[str] = None,
    user: Optional[discord.Member] = None,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    caller = interaction.user
    target = user or caller

    if target.id != caller.id and not is_manager(caller):
        await interaction.followup.send(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to modify another user's stock.",
            ephemeral=True,
        )
        return

    if quantity <= 0:
        await interaction.followup.send("❌ Quantity must be greater than 0.", ephemeral=True)
        return

    unit = get_unit_label(resource_name)

    success, message = db.remove_resource(
        guild_id=str(interaction.guild_id),
        user_id=str(target.id),
        resource_name=resource_name,
        quantity=quantity,
        unit=unit,
        quality=quality,
        location=location,
    )

    color = discord.Color.green() if success else discord.Color.red()
    embed = discord.Embed(
        title="🗑️ Resource Removed" if success else "❌ Remove Failed",
        description=message,
        color=color,
    )
    if success:
        embed.set_footer(text=f"Owner: {target.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(
    name="get-resource",
    description="Look up who owns a resource across the guild, with quantities and quality.",
)
@app_commands.describe(resource_name="Resource name to search (autocomplete)")
@app_commands.autocomplete(resource_name=resource_autocomplete)
async def get_resource(
    interaction: discord.Interaction,
    resource_name: str,
):
    if not await check_channel(interaction):
        return
    await interaction.response.defer()

    rows = db.get_resource_info(
        guild_id=str(interaction.guild_id),
        resource_name=resource_name,
    )

    if not rows:
        embed = discord.Embed(
            title=f"🔍 {resource_name}",
            description="Nobody in this org owns that resource.",
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=embed)
        return

    unit = rows[0]["unit"]
    total = sum(r["quantity"] for r in rows)

    embed = discord.Embed(
        title=f"🔍 {resource_name}",
        description=f"**{total:.4g} {unit}** total across the org",
        color=discord.Color.from_rgb(0, 200, 140),
    )

    for row in rows:
        member = interaction.guild.get_member(int(row["user_id"]))
        owner_name = member.display_name if member else f"<@{row['user_id']}>"
        qty_str = f"{row['quantity']:.4g} {unit}"
        qual_str = f"  ·  Quality **{row['quality']}**" if row["quality"] is not None else ""
        loc_str = f"\n📍 {row['location']}" if row["location"] else "\n📍 *No location set*"
        embed.add_field(
            name=f"{owner_name}  —  {qty_str}{qual_str}",
            value=loc_str,
            inline=False,
        )

    await interaction.followup.send(embed=embed)


# ── /set-channel ───────────────────────────────────────────────────────────────

@tree.command(
    name="set-channel",
    description="Restrict bot commands to a specific channel (managers only).",
)
@app_commands.describe(
    channel="Channel where bot commands are allowed (leave empty to remove the restriction)",
)
async def set_channel(
    interaction: discord.Interaction,
    channel: Optional[discord.TextChannel] = None,
):
    if not is_manager(interaction.user):
        await interaction.response.send_message(
            f"❌ You need the **{MANAGER_ROLE_NAME}** role to change this setting.",
            ephemeral=True,
        )
        return

    guild_id = str(interaction.guild_id)

    if channel is None:
        db.set_allowed_channel(guild_id, None)
        embed = discord.Embed(
            title="🔓 Channel Restriction Removed",
            description="Bot commands can now be used in **any channel**.",
            color=discord.Color.green(),
        )
    else:
        db.set_allowed_channel(guild_id, str(channel.id))
        embed = discord.Embed(
            title="🔒 Channel Restricted",
            description=f"Bot commands are now limited to {channel.mention}.",
            color=discord.Color.from_rgb(0, 180, 255),
        )
        embed.set_footer(text="Use /set-channel with no argument to remove the restriction.")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── bot events ─────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    db.init_db()
    try:
        synced = await tree.sync()
        print(f"[✓] Logged in as {bot.user} | Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"[!] Sync error: {e}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    print(f"[+] Joined guild: {guild.name} ({guild.id})")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    bot.run(TOKEN)
