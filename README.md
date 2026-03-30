# 🚀 Star Citizen Guild Inventory Bot

A Discord bot for tracking Star Citizen items across your guild or organisation. Members can manage their own inventory via slash commands; users with the manager role can manage everyone's.

---

## Features

| Command | Description |
|---|---|
| `/add-item` | Add items to an inventory |
| `/remove-item` | Remove items from an inventory |
| `/get-item` | See who owns an item, how many, and where |
| `/inventory` | View a user's full inventory |

All commands use Discord's native slash-command UI with autocomplete on item names.

---

## Permissions

| Role | Can do |
|---|---|
| **Everyone** | Manage their **own** inventory, use `/get-item` publicly |
| **SC-Manager** (configurable) | Manage **any** user's inventory, view any `/inventory` |
| **Server Owner** | Same as SC-Manager |

---

## Quick Start

### 1 — Prerequisites

- Python 3.10+
- A Discord application & bot token → [Discord Developer Portal](https://discord.com/developers/applications)

### 2 — Clone & install

```bash
git clone <your-repo>
cd sc-bot
pip install -r requirements.txt
```

### 3 — Configure

```bash
cp .env.example .env
# Open .env and fill in your DISCORD_TOKEN
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Bot token from the Developer Portal |
| `MANAGER_ROLE` | ❌ | `SC-Manager` | Discord role name with elevated permissions |
| `DB_PATH` | ❌ | `inventory.db` | Path to the SQLite database file |

### 4 — Invite the bot

In the Developer Portal under **OAuth2 → URL Generator**, select:
- Scopes: `bot`, `applications.commands`
- Bot permissions: `Send Messages`, `Embed Links`, `Read Message History`

Use the generated URL to invite the bot to your server.

### 5 — Create the manager role (optional)

In your Discord server, create a role named **SC-Manager** (or whatever you set in `MANAGER_ROLE`) and assign it to trusted officers/admins.

### 6 — Run

```bash
python bot.py
```

On first launch the bot will:
1. Create `inventory.db`
2. Sync all slash commands to Discord (may take up to 1 hour to propagate globally, instant for guild commands)

---

## Command Reference

### `/add-item`

```
/add-item item_name:<str> [quantity:<int>] [location:<str>] [user:<@member>]
```

| Parameter | Required | Notes |
|---|---|---|
| `item_name` | ✅ | Autocompleted from existing items |
| `quantity` | ❌ | Default `1` |
| `location` | ❌ | e.g. `Lorville`, `Ship - Constellation Andromeda` |
| `user` | ❌ | **Manager only** — defaults to yourself |

If the same `(item, location)` pair already exists for the user, the quantity is **added** to the existing row.

---

### `/remove-item`

```
/remove-item item_name:<str> [quantity:<int>] [location:<str>] [user:<@member>]
```

Removes `quantity` units. If no location is specified, units are deducted across all locations (highest-quantity location first). The command rejects requests that exceed the available stock.

---

### `/get-item`

```
/get-item item_name:<str>
```

Public command (visible to the whole channel). Shows each owner with their quantity and location, plus an org-wide total.

---

### `/inventory`

```
/inventory [user:<@member>]
```

Shows the full inventory list for a user (ephemeral). Non-managers can only view their own.

---

## Database Schema

```sql
CREATE TABLE inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT    NOT NULL,
    user_id     TEXT    NOT NULL,
    item_name   TEXT    NOT NULL COLLATE NOCASE,
    quantity    INTEGER NOT NULL DEFAULT 1,
    location    TEXT,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

The database is a local SQLite file — no external services required. Back it up by copying `inventory.db`.

---

## Running as a Service (Linux)

```ini
# /etc/systemd/system/sc-bot.service
[Unit]
Description=Star Citizen Inventory Bot
After=network.target

[Service]
WorkingDirectory=/opt/sc-bot
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
EnvironmentFile=/opt/sc-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now sc-bot
```
