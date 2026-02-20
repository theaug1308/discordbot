import os
import json
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
CONFIG_FILE = "config.json"


def load_config() -> dict:
    """Load config from disk. Returns default structure if file is missing."""
    default = {"versions": {}, "whitelist": [], "admin_ids": []}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        save_config(default)
        return default


def save_config(data: dict) -> None:
    """Persist config to disk."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

config = load_config()


def is_admin(user_id: int) -> bool:
    """Check whether a user is in the admin list."""
    return user_id in config["admin_ids"]


def is_whitelisted(user_id: int) -> bool:
    """Check whether a user is whitelisted (admins are always allowed)."""
    return user_id in config["whitelist"] or is_admin(user_id)


# ---------------------------------------------------------------------------
# Version select dropdown
# ---------------------------------------------------------------------------
class VersionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=name)
            for name in config["versions"]
        ]
        super().__init__(placeholder="Select a version...", options=options)

    async def callback(self, interaction: discord.Interaction):
        version = self.values[0]
        link = config["versions"][version]
        await interaction.response.send_message(
            f"⬇️ **{version}**\nDownload here: {link}",
            ephemeral=True,
        )


class VersionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(VersionSelect())


# ---------------------------------------------------------------------------
# /download
# ---------------------------------------------------------------------------
@tree.command(name="download", description="Download a file version")
async def download(interaction: discord.Interaction):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Access denied. You are not whitelisted.", ephemeral=True
        )
        return

    if not config["versions"]:
        await interaction.response.send_message(
            "⚠️ No versions available yet.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📦 Select the version you want to download:",
        view=VersionView(),
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# /whitelist group
# ---------------------------------------------------------------------------
whitelist_group = app_commands.Group(
    name="whitelist", description="Manage the download whitelist"
)


@whitelist_group.command(name="add", description="Add a user to the whitelist")
@app_commands.describe(user="The user to whitelist")
async def whitelist_add(interaction: discord.Interaction, user: discord.User):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can manage the whitelist.", ephemeral=True
        )
        return

    if user.id in config["whitelist"]:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} is already whitelisted.", ephemeral=True
        )
        return

    config["whitelist"].append(user.id)
    save_config(config)
    await interaction.response.send_message(
        f"✅ {user.mention} has been added to the whitelist.", ephemeral=True
    )


@whitelist_group.command(name="remove", description="Remove a user from the whitelist")
@app_commands.describe(user="The user to remove")
async def whitelist_remove(interaction: discord.Interaction, user: discord.User):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can manage the whitelist.", ephemeral=True
        )
        return

    if user.id not in config["whitelist"]:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} is not in the whitelist.", ephemeral=True
        )
        return

    config["whitelist"].remove(user.id)
    save_config(config)
    await interaction.response.send_message(
        f"✅ {user.mention} has been removed from the whitelist.", ephemeral=True
    )


@whitelist_group.command(name="list", description="Show all whitelisted users")
async def whitelist_list(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can view the whitelist.", ephemeral=True
        )
        return

    if not config["whitelist"]:
        await interaction.response.send_message(
            "📋 The whitelist is empty.", ephemeral=True
        )
        return

    mentions = [f"<@{uid}>" for uid in config["whitelist"]]
    await interaction.response.send_message(
        f"📋 **Whitelisted users:**\n{chr(10).join(mentions)}", ephemeral=True
    )


tree.add_command(whitelist_group)


# ---------------------------------------------------------------------------
# /version group
# ---------------------------------------------------------------------------
version_group = app_commands.Group(
    name="version", description="Manage downloadable versions"
)


@version_group.command(name="add", description="Add or update a download version")
@app_commands.describe(name="Version name (e.g. Delta 707)", url="Direct download URL")
async def version_add(interaction: discord.Interaction, name: str, url: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can manage versions.", ephemeral=True
        )
        return

    config["versions"][name] = url
    save_config(config)
    await interaction.response.send_message(
        f"✅ Version **{name}** has been added.\n🔗 {url}", ephemeral=True
    )


@version_group.command(name="remove", description="Remove a download version")
@app_commands.describe(name="Version name to remove")
async def version_remove(interaction: discord.Interaction, name: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can manage versions.", ephemeral=True
        )
        return

    if name not in config["versions"]:
        await interaction.response.send_message(
            f"ℹ️ Version **{name}** does not exist.", ephemeral=True
        )
        return

    del config["versions"][name]
    save_config(config)
    await interaction.response.send_message(
        f"✅ Version **{name}** has been removed.", ephemeral=True
    )


@version_group.command(name="list", description="Show all available versions")
async def version_list(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message(
            "🚫 Only admins can view version details.", ephemeral=True
        )
        return

    if not config["versions"]:
        await interaction.response.send_message(
            "📋 No versions configured yet.", ephemeral=True
        )
        return

    lines = [f"• **{n}** — {u}" for n, u in config["versions"].items()]
    await interaction.response.send_message(
        f"📋 **Available versions:**\n{chr(10).join(lines)}", ephemeral=True
    )


tree.add_command(version_group)


# ---------------------------------------------------------------------------
# /admin group
# ---------------------------------------------------------------------------
admin_group = app_commands.Group(name="admin", description="Manage bot admins")


@admin_group.command(name="add", description="Add a bot admin")
@app_commands.describe(user="The user to make admin")
async def admin_add(interaction: discord.Interaction, user: discord.User):
    # Only server owner or existing admins can add new admins
    if (
        interaction.guild is None
        or interaction.user.id != interaction.guild.owner_id
        and not is_admin(interaction.user.id)
    ):
        await interaction.response.send_message(
            "🚫 Only the server owner or existing admins can add admins.",
            ephemeral=True,
        )
        return

    if user.id in config["admin_ids"]:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} is already an admin.", ephemeral=True
        )
        return

    config["admin_ids"].append(user.id)
    save_config(config)
    await interaction.response.send_message(
        f"✅ {user.mention} is now a bot admin.", ephemeral=True
    )


@admin_group.command(name="remove", description="Remove a bot admin")
@app_commands.describe(user="The admin to remove")
async def admin_remove(interaction: discord.Interaction, user: discord.User):
    if (
        interaction.guild is None
        or interaction.user.id != interaction.guild.owner_id
        and not is_admin(interaction.user.id)
    ):
        await interaction.response.send_message(
            "🚫 Only the server owner or existing admins can remove admins.",
            ephemeral=True,
        )
        return

    if user.id not in config["admin_ids"]:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} is not an admin.", ephemeral=True
        )
        return

    config["admin_ids"].remove(user.id)
    save_config(config)
    await interaction.response.send_message(
        f"✅ {user.mention} has been removed from admins.", ephemeral=True
    )


tree.add_command(admin_group)


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    # Sync to each guild individually (instant) instead of global (takes ~1 hour)
    for guild in bot.guilds:
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            print(f"   Synced commands to: {guild.name}")
        except Exception as e:
            print(f"   Failed to sync to {guild.name}: {e}")
    print(f"✅ Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"   Versions : {len(config['versions'])}")
    print(f"   Whitelist: {len(config['whitelist'])} users")
    print(f"   Admins   : {len(config['admin_ids'])} users")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    if not token:
        # Fallback: try loading from .env file manually
        try:
            from dotenv import load_dotenv

            load_dotenv()
            token = os.environ.get("TOKEN")
        except ImportError:
            pass

    if not token:
        print("❌ No TOKEN found. Set it as an environment variable or in a .env file.")
        exit(1)

    bot.run(token)
