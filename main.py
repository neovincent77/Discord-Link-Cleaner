# This bot requires the 'message_content' intent.

import json
import discord
from discord import app_commands
from discord.ext import commands
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import os
import sys

#--------------------------------------------------------------------
# Setup
#--------------------------------------------------------------------


def get_app_folder() -> str:
    """
    Determine the application folder path.
    
    Returns:
        str: Path to the application directory (executable dir if frozen, script dir otherwise)
    """
    if getattr(sys, 'frozen', False):
        # When compiled with PyInstaller, return the directory containing the executable
        return os.path.dirname(sys.executable)
    
    # For development/script mode, find the directory containing main.py
    # Start by checking if we can find main.py relative to this file's location
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if main.py is in the parent directory of this file (Src directory)
    parent_dir = os.path.dirname(current_file_dir)
    main_py_path = os.path.join(parent_dir, 'main.py')
    if os.path.exists(main_py_path):
        return parent_dir
    
    # If not found, search from current working directory up the tree
    current_dir = os.path.abspath(os.getcwd())
    search_dir = current_dir
    
    while True:
        main_py_path = os.path.join(search_dir, 'main.py')
        if os.path.exists(main_py_path):
            return search_dir
        
        # Move up one directory
        parent_dir = os.path.dirname(search_dir)
        if parent_dir == search_dir:  # Reached root directory
            break
        search_dir = parent_dir
    
    # Final fallback: return the directory containing this file (helpers directory)
    # and go up one level to get the Src directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def ensure_file_exists(filepath: str, default_content) -> None:
    """
    Create a file with default content if it doesn't exist.
    
    Args:
        filepath: Path to the file to create
        default_content: Default content to write to the file
    """
    if not os.path.isfile(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, indent=4)
        print(f"Created missing file: {filepath}")

def ensure_json_valid(filepath: str, default_content: dict) -> None:
    """
    Validate and clean a JSON configuration file.
    
    This function ensures the JSON file is valid and contains only expected keys.
    If the file is corrupted or contains extra keys, it will be cleaned up.
    
    Args:
        filepath: Path to the JSON file to validate
        default_content: Default configuration structure to validate against
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                # Reset to defaults if file is corrupted
                with open(filepath, 'w', encoding='utf-8') as fw:
                    json.dump(default_content, fw, indent=4)
                print(f"Invalid JSON in {filepath}. Resetting to default.")
                return

        modified = False
        cleaned_data = {}

        # Copy over valid keys from default_config
        for key, default_value in default_content.items():
            if key in data:
                if isinstance(default_value, list) and isinstance(data[key], list):
                    merged = list(dict.fromkeys(data[key] + default_value))
                    cleaned_data[key] = merged

                    if merged != data[key]:
                        modified = True
                        print(f"Updated '{key}' in {filepath}")
                else:
                    cleaned_data[key] = data[key]
            else:
                cleaned_data[key] = default_value
                modified = True
                print(f"Added missing key '{key}' to {filepath}")

        # Check for and remove extra keys
        extra_keys = set(data.keys()) - set(default_content.keys())
        if extra_keys:
            modified = True
            print(f"Removing extra keys from {filepath}: {extra_keys}")

        if modified:
            # Create a backup before making changes
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{filepath}.backup_{timestamp}.json"
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                json.dump(data, backup_file, indent=4)
            print(f"Backed up original config file to {backup_path}")

            # Write cleaned data
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=4)
            print(f"Successfully cleaned and updated {filepath}")

    except Exception as e:
        print(f"Error validating JSON file {filepath}: {e}")

APP_FOLDER = get_app_folder()
CONFIG_PATH = os.path.join(APP_FOLDER, 'config.json')
TRACKERS_PATH = os.path.join(APP_FOLDER, 'trackers.json')

default_config = {
    "bot_token": "",
    "mention_reply_author": True,
    "require_links": True,
    "regex_keys": "(?i)\\b((?:https?://|www\\.)[^\\s<>\"']+|(?:[a-z0-9-]+\\.)+[a-z]{2,}(?:/[^\\s<>\"']*)?)\\b"
}

default_trackers = {
    "Google": ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "gclid", "gclsrc", "dclid", "wbraid", "gbraid", "gad_source"],
    "Meta": ["fbclid", "fb_action_ids", "fb_action_types", "fb_source", "fb_ref", "fb_ad_id", "fb_adset_id", "fb_campaign_id", "igsh", "stkn"],
    "TikTok": ["ttclid", "tt_content_id", "tt_medium", "tt_campaign_id", "tt_ad_id", "tt_adset_id"],
    "Microsoft": ["msclkid", "li_fat_id", "li_source", "li_medium", "li_campaign"],
    "Twitter": ["twclid", "ref_src", "s", "t", "tw_campaign", "tw_source"],
    "Reddit": ["rdt_cid", "rdt_source", "rdt_medium", "rdt_campaign"],
    "Snapchat": ["sc_cid", "sc_source", "sc_medium", "sc_campaign"],
    "Pinterest": ["epik", "pin_campaign", "pin_source"],
    "Amazon": ["tag", "ascsubtag", "asc_source", "creative", "creativeASIN", "linkCode", "th"],
    "Mailchimp": ["mc_cid", "mc_eid"],
    "HubSpot": ["hsa_acc", "hsa_cam", "hsa_grp", "hsa_ad", "hsa_src", "hsa_net", "hsa_ver"],
    "Adobe": ["s_cid", "ef_id"],
    "Salesforce": ["pi_campaign_id", "pi_source", "pi_ad_id"],
    "Shopify": ["shopify", "shopify_app", "shopify_email", "shopify_utm"],
    "Email": ["mkt_tok", "_hsenc", "_hsmi", "trk", "trkCampaign", "campaign", "source"],
    "Affiliate": ["aff_id", "affiliate_id", "ref", "ref_id", "referrer", "partner", "partner_id", "click_id", "clickid", "cid", "subid", "sub_id"],
    "Analytics": ["_ga", "_gl", "_gac", "_gid", "yclid", "rb_clickid", "vero_id", "vero_conv", "oly_anon_id", "oly_enc_id", "appSharePlatform"]
}

ensure_file_exists(CONFIG_PATH, default_config)
ensure_json_valid(CONFIG_PATH, default_config)
ensure_file_exists(TRACKERS_PATH, default_trackers)
ensure_json_valid(TRACKERS_PATH, default_trackers)

# Load initial config
with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
    config = json.load(f)

with open(TRACKERS_PATH, 'r', encoding="utf-8") as f:
    trackers = json.load(f)
    
bot_token = os.getenv("DISCORD_TOKEN", "").strip() or config.get("bot_token", default_config["bot_token"]).strip()
mention_reply_author = config.get("mention_reply_author", default_config["mention_reply_author"])
require_links = config.get("require_links", default_config["require_links"])

PARAM_INDEX = {param.lower(): company for company, params in trackers.items() for param in params}

try:
    REGEX = re.compile(
        config.get("regex_keys", default_config["regex_keys"])
    )
except re.error as e:
    raise RuntimeError(f"Invalid regex in config.json: {e}")


#--------------------------------------------------------------------
# Funcs
#--------------------------------------------------------------------

def has_link(message: str) -> bool:
    return bool(REGEX.search(message))

def has_trackers(url):
    parsed = urlparse(url)
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in PARAM_INDEX:
            return True
    return False

def build_param_index(tracker_map):
    index = {}
    for company, params in tracker_map.items():
        for param in params:
            index[param] = company
    return index

def clean_url(url):
    parsed = urlparse(url)
    kept = []
    removed = {}

    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        owner = PARAM_INDEX.get(key.lower())
        if owner:
            removed.setdefault(owner, []).append(key)
        else:
            kept.append((key, value))

    cleaned_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(kept),
        parsed.fragment
    ))

    if removed:
        message = f"Removed trackers from {', '.join(removed.keys())}"
    else:
        message = "No trackers found"

    return {
        "clean_url": cleaned_url,
        "removed_trackers": removed,
        "message": message
    }

def format_companies(companies):
    """Return a nicely formatted string with commas and 'and' before the last item."""
    companies = list(companies)  # ensure it's a list
    if len(companies) == 0:
        return ""
    elif len(companies) == 1:
        return companies[0]
    else:
        return ", ".join(companies[:-1]) + f", and {companies[-1]}"

def load_config():
    """Load configuration from JSON file."""
    global config, mention_reply_author, require_links, REGEX
    with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
        config = json.load(f)
    
    mention_reply_author = config.get("mention_reply_author", default_config["mention_reply_author"])
    require_links = config.get("require_links", default_config["require_links"])
    
    try:
        REGEX = re.compile(config.get("regex_keys", default_config["regex_keys"]))
    except re.error as e:
        raise RuntimeError(f"Invalid regex in config.json: {e}")

def save_config():
    """Save current configuration to JSON file."""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def load_trackers():
    """Load trackers from JSON file."""
    global trackers, PARAM_INDEX
    with open(TRACKERS_PATH, 'r', encoding="utf-8") as f:
        trackers = json.load(f)
    PARAM_INDEX = {param.lower(): company for company, params in trackers.items() for param in params}
    print("STKN TEST:", PARAM_INDEX.get("stkn"))

def save_trackers():
    """Save current trackers to JSON file."""
    with open(TRACKERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(trackers, f, indent=4)
#--------------------------------------------------------------------
# Main Program
#--------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    if not (has_link(message.content) and require_links):
        return  

    urls = re.findall(REGEX, message.content)
    if not urls:
        return

    detected_companies = set()
    sanitized_map = {}  

    for url in urls:
        result = clean_url(url)
        if result["removed_trackers"]:
            detected_companies.update(result["removed_trackers"].keys())
            sanitized_map[url] = result["clean_url"]

    if detected_companies:
        try:
            reply = await message.reply(">>>")
            await message.delete()
            sanitized_message = message.content
            for original, cleaned in sanitized_map.items():
                sanitized_message = sanitized_message.replace(original, cleaned)

            # Use mention_reply_author setting
            author_mention = f"{message.author.mention} " if mention_reply_author else ""
            notice = (
                f"{author_mention}Your message has been reposted without trackers from "
                f"{format_companies(detected_companies)}:"
            )

            await reply.edit(content=f"{notice}\n{sanitized_message}")
        
        except discord.Forbidden:
            print("Bot lacks permission to delete messages.")
        except Exception as e:
            print(f"Error handling message: {e}")

#--------------------------------------------------------------------
# Admin Commands
#--------------------------------------------------------------------

def is_admin(interaction: discord.Interaction) -> bool:
    """Check if user has administrator permissions."""
    return interaction.user.guild_permissions.administrator

@bot.tree.command(name="settings", description="View current bot settings")
async def settings(interaction: discord.Interaction):
    """View current bot settings."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    load_config()
    embed = discord.Embed(
        title="Bot Settings",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Mention Reply Author",
        value="✅ Enabled" if mention_reply_author else "❌ Disabled",
        inline=False
    )
    embed.add_field(
        name="Require Links",
        value="✅ Enabled" if require_links else "❌ Disabled",
        inline=False
    )
    embed.add_field(
        name="Regex Pattern",
        value=f"`{config.get('regex_keys', 'N/A')[:100]}...`" if len(config.get('regex_keys', '')) > 100 else f"`{config.get('regex_keys', 'N/A')}`",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_mention", description="Enable or disable mentioning the author when reposting messages")
@app_commands.describe(enabled="Whether to mention the author when reposting")
async def set_mention(interaction: discord.Interaction, enabled: bool):
    """Set whether to mention the author when reposting messages."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    global mention_reply_author
    config["mention_reply_author"] = enabled
    save_config()
    load_config()
    
    await interaction.response.send_message(
        f"✅ Mention reply author has been {'enabled' if enabled else 'disabled'}.",
        ephemeral=True
    )

@bot.tree.command(name="set_require_links", description="Enable or disable requiring links in messages before processing")
@app_commands.describe(enabled="Whether to only process messages that contain links")
async def set_require_links(interaction: discord.Interaction, enabled: bool):
    """Set whether to require links in messages before processing."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    global require_links
    config["require_links"] = enabled
    save_config()
    load_config()
    
    await interaction.response.send_message(
        f"✅ Require links has been {'enabled' if enabled else 'disabled'}.",
        ephemeral=True
    )

@bot.tree.command(name="set_regex", description="Set the regex pattern used to detect URLs")
@app_commands.describe(pattern="The regex pattern to use for URL detection")
async def set_regex(interaction: discord.Interaction, pattern: str):
    """Set the regex pattern used to detect URLs."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    # Validate regex pattern
    try:
        test_regex = re.compile(pattern)
    except re.error as e:
        await interaction.response.send_message(
            f"❌ Invalid regex pattern: {e}\n\nPlease provide a valid regex pattern.",
            ephemeral=True
        )
        return
    
    global REGEX
    config["regex_keys"] = pattern
    save_config()
    load_config()
    
    await interaction.response.send_message(
        f"✅ Regex pattern has been updated.\n\nNew pattern: `{pattern}`",
        ephemeral=True
    )

@bot.tree.command(name="reload_config", description="Reload configuration from file")
async def reload_config(interaction: discord.Interaction):
    """Reload configuration from config.json file."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        load_config()
        await interaction.response.send_message("✅ Configuration reloaded successfully.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error reloading configuration: {e}", ephemeral=True)

#--------------------------------------------------------------------
# Tracker Management Commands
#--------------------------------------------------------------------

trackers_group = app_commands.Group(name="trackers", description="Manage tracking parameters")

@trackers_group.command(name="list", description="List all trackers organized by provider")
async def trackers_list(interaction: discord.Interaction):
    """List all trackers organized by provider."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    load_trackers()
    
    if not trackers:
        await interaction.response.send_message("❌ No trackers configured.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Tracking Parameters",
        description="All configured tracking parameters by provider",
        color=discord.Color.blue()
    )
    
    # Discord embeds have a limit of 6000 characters total
    # Split into multiple embeds if needed
    total_length = 0
    fields_added = 0
    
    for provider, params in sorted(trackers.items()):
        if not params:
            continue
        
        params_str = ", ".join(params)
        field_value = f"`{params_str}`"
        
        # Check if adding this field would exceed limits
        # Discord field value limit is 1024 characters, embed total is 6000
        if len(field_value) > 1024:
            # Truncate if too long
            field_value = field_value[:1020] + "..."
        
        if total_length + len(field_value) + len(provider) > 5500 or fields_added >= 25:
            # Add a note that there are more providers
            embed.add_field(
                name="...",
                value=f"*Showing first {fields_added} providers. Use `/trackers list` to see all.*",
                inline=False
            )
            break
        
        embed.add_field(
            name=provider,
            value=field_value,
            inline=False
        )
        total_length += len(field_value) + len(provider)
        fields_added += 1
    
    embed.set_footer(text=f"Total providers: {len(trackers)}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@trackers_group.command(name="add", description="Add a tracker parameter to a provider")
@app_commands.describe(provider="The provider name (e.g., Google, Meta)")
@app_commands.describe(tracker="The tracker parameter name to add")
async def trackers_add(interaction: discord.Interaction, provider: str, tracker: str):
    """Add a tracker parameter to a provider."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    load_trackers()
    
    # Normalize provider name (capitalize first letter)
    provider_normalized = provider.strip()
    if provider_normalized:
        provider_normalized = provider_normalized[0].upper() + provider_normalized[1:].lower()
    
    tracker_normalized = tracker.strip()
    
    if not tracker_normalized:
        await interaction.response.send_message("❌ Tracker parameter name cannot be empty.", ephemeral=True)
        return
    
    # Check if tracker already exists for any provider
    tracker_lower = tracker_normalized.lower()
    existing_provider = None
    for prov, params in trackers.items():
        if tracker_lower in [p.lower() for p in params]:
            existing_provider = prov
            break
    
    if existing_provider:
        if existing_provider == provider_normalized:
            await interaction.response.send_message(
                f"❌ Tracker `{tracker_normalized}` already exists for provider `{provider_normalized}`.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Tracker `{tracker_normalized}` already exists for provider `{existing_provider}`. "
                f"Remove it first if you want to add it to `{provider_normalized}`.",
                ephemeral=True
            )
        return
    
    # Add tracker to provider
    if provider_normalized not in trackers:
        trackers[provider_normalized] = []
    
    trackers[provider_normalized].append(tracker_normalized)
    save_trackers()
    load_trackers()  # Reload to update PARAM_INDEX
    
    await interaction.response.send_message(
        f"✅ Added tracker `{tracker_normalized}` to provider `{provider_normalized}`.",
        ephemeral=True
    )

@trackers_group.command(name="remove", description="Remove a tracker parameter from a provider")
@app_commands.describe(provider="The provider name (e.g., Google, Meta)")
@app_commands.describe(tracker="The tracker parameter name to remove")
async def trackers_remove(interaction: discord.Interaction, provider: str, tracker: str):
    """Remove a tracker parameter from a provider."""
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    load_trackers()
    
    # Normalize provider name (capitalize first letter)
    provider_normalized = provider.strip()
    if provider_normalized:
        provider_normalized = provider_normalized[0].upper() + provider_normalized[1:].lower()
    
    tracker_normalized = tracker.strip()
    
    if provider_normalized not in trackers:
        await interaction.response.send_message(
            f"❌ Provider `{provider_normalized}` not found.",
            ephemeral=True
        )
        return
    
    # Find and remove tracker (case-insensitive)
    tracker_lower = tracker_normalized.lower()
    found = False
    for i, param in enumerate(trackers[provider_normalized]):
        if param.lower() == tracker_lower:
            removed_tracker = trackers[provider_normalized].pop(i)
            found = True
            break
    
    if not found:
        await interaction.response.send_message(
            f"❌ Tracker `{tracker_normalized}` not found for provider `{provider_normalized}`.",
            ephemeral=True
        )
        return
    
    # Remove provider if it has no trackers left
    if not trackers[provider_normalized]:
        del trackers[provider_normalized]
        save_trackers()
        load_trackers()
        await interaction.response.send_message(
            f"✅ Removed tracker `{tracker_normalized}` from provider `{provider_normalized}`. "
            f"Provider `{provider_normalized}` has been removed as it has no trackers left.",
            ephemeral=True
        )
    else:
        save_trackers()
        load_trackers()  # Reload to update PARAM_INDEX
        await interaction.response.send_message(
            f"✅ Removed tracker `{tracker_normalized}` from provider `{provider_normalized}`.",
            ephemeral=True
        )

bot.tree.add_command(trackers_group)

bot.run(bot_token)
