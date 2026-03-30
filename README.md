# 🚀 Star Citizen Inventory Tracker Bot

A Discord bot for tracking Star Citizen items across your guild or organisation. Members can manage their own inventory via slash commands; users with the manager role can manage everyone's.

---

## Features

| Command | Description |
|---|---|
| `/add-item` | Add items to an inventory |
| `/remove-item` | Remove items from an inventory |
| `/get-item` | See who owns an item, how many, and where |
| `/inventory` | View a user's full inventory |
| `/add-ship` | Add a ship to your hangar |
| `/remove-ship` | Remove a ship from your hangar |
| `/add-resource` | Add mined resources (minerals, gems) to your stock |
| `/remove-resource` | Remove resources from your stock |
| `/get-resource` | Look up who owns a resource across the guild |
| `/set-channel` | Restrict bot commands to a specific channel (managers only) |

All commands use Discord's native slash-command UI with autocomplete. Results can be **public** (visible to everyone) or **ephemeral** (visible only to you), depending on the command.

---

## Permissions

| Action | Everyone | Managers | Server Owner |
|---|---|---|---|
| **Manage own inventory/hangar/stock** | ✅ | ✅ | ✅ |
| **Manage other users' inventory/hangar/stock** | ❌ | ✅ | ✅ |
| **View own inventory/stock** | ✅ | ✅ | ✅ |
| **View other users' inventory/stock** | ❌ | ✅ | ✅ |
| **Search items/ships/resources** (guild-wide) | ✅ | ✅ | ✅ |
| **Change bot channel restriction** | ❌ | ✅ | ✅ |

**Roles:**
- **Everyone:** All guild members
- **Managers:** Users with the role specified in `MANAGER_ROLE` (default: `SC-Manager`)
- **Server Owner:** The Discord server owner (has automatic manager permissions)

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

### `/add-item` — Add items to inventory

```
/add-item item_name:<str> [quantity:<int>] [location:<str>] [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `item_name` | ✅ | string | Autocompleted from existing items in your guild |
| `quantity` | ❌ | integer | How many to add (default: `1`) |
| `location` | ❌ | string | Where the item is stored (e.g. `Lorville`, `Ship - Constellation Andromeda`) |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Behavior:** If the same `(item, location)` pair already exists for the user, the quantity is **added** to the existing row.

**Permissions:** You can only modify your own inventory unless you have the manager role, or you're the server owner.

---

### `/remove-item` — Remove items from inventory

```
/remove-item item_name:<str> [quantity:<int>] [location:<str>] [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `item_name` | ✅ | string | Autocompleted from existing items |
| `quantity` | ❌ | integer | How many to remove (default: `1`) |
| `location` | ❌ | string | Only remove from a specific location (optional; if omitted, removes from any location) |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Behavior:** If quantity exceeds what exists, the command fails with an error message.

**Permissions:** You can only modify your own inventory unless you have the manager role, or you're the server owner.

---

### `/get-item` — Look up item ownership

```
/get-item item_name:<str>
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `item_name` | ✅ | string | Autocompleted from guild items |

**Returns:** A list of all guild members who own the item, their quantities, and where each copy is stored.

**Visibility:** Anyone can use this command; results are **public** (not ephemeral).

---

### `/inventory` — View a user's full inventory

```
/inventory [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `user` | ❌ | @member | User to inspect (default: yourself) |

**Returns:** A complete list of all items owned by the user. If the inventory exceeds Discord's embed limits, results span multiple pages.

**Permissions:** You can only view your own inventory unless you have the manager role, or you're the server owner. Results are **ephemeral** (visible only to you).

---

### `/add-ship` — Add ships to hangar

```
/add-ship ship_name:<str> [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `ship_name` | ✅ | string | Autocompleted from the official Star Citizen ship roster |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Behavior:** Adds a ship to a user's hangar. Ships are stored as items with location `Hangar`.

**Permissions:** You can only modify your own hangar unless you have the manager role, or you're the server owner.

---

### `/remove-ship` — Remove ships from hangar

```
/remove-ship ship_name:<str> [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `ship_name` | ✅ | string | Autocompleted from the official Star Citizen ship roster |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Behavior:** Removes one instance of a ship from the user's hangar.

**Permissions:** You can only modify your own hangar unless you have the manager role, or you're the server owner.

---

### `/add-resource` — Add mined resources or gems

```
/add-resource resource_name:<str> quantity:<float> [quality:<int>] [location:<str>] [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `resource_name` | ✅ | string | Autocompleted from supported minerals and gems |
| `quantity` | ✅ | float | Amount in SCU (for minerals) or Units (for gems); decimals allowed |
| `quality` | ❌ | integer | Ore quality `0–1000` — **SCU resources only** (optional; ignored for gems) |
| `location` | ❌ | string | Where the resource is stored (optional) |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Supported Types:**
- **SCU Resources:** Minerals (AlUm, Bexalite, Borase, Corundum, etc.) — measured in **SCU**
- **Unit Resources:** Gems and other items — measured in **Units**

**Behavior:** If the same `(resource, quality, location)` entry exists, the quantity is **added**. Quality only applies to minerals and ranges from `0–1000`.

**Permissions:** You can only modify your own stock unless you have the manager role, or you're the server owner.

---

### `/remove-resource` — Remove mined resources or gems

```
/remove-resource resource_name:<str> quantity:<float> [quality:<int>] [location:<str>] [user:<@member>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `resource_name` | ✅ | string | Autocompleted from supported resources |
| `quantity` | ✅ | float | Amount to remove in SCU or Units |
| `quality` | ❌ | integer | Only remove from batches of this quality — **SCU only** (optional) |
| `location` | ❌ | string | Only remove from this location (optional) |
| `user` | ❌ | @member | Target user — **managers only** (default: yourself) |

**Behavior:** Removes the specified quantity from matching batches. If quality or location filters are given, only batches matching those criteria are removed.

**Permissions:** You can only modify your own stock unless you have the manager role, or you're the server owner.

---

### `/get-resource` — Look up resource ownership

```
/get-resource resource_name:<str>
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `resource_name` | ✅ | string | Autocompleted from guild resources |

**Returns:** All guild members who own the resource, their quantities, quality (if applicable), and locations.

**Visibility:** Anyone can use this command; results are **public** (not ephemeral).

---

### `/set-channel` — Restrict bot to a channel

```
/set-channel [channel:<#channel>]
```

| Parameter | Required | Type | Notes |
|---|---|---|---|
| `channel` | ❌ | #channel | Channel where bot commands are allowed; omit to remove restriction |

**Behavior:** If a channel is specified, all bot commands can **only** be used in that channel. If no channel is specified, the restriction is **removed** and commands work anywhere.

**Behavior:** **Managers only** (or server owner). This is a server-wide setting.

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
