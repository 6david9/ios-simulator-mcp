# iOS Simulator MCP

An MCP (Model Context Protocol) server that provides Claude Code with tools to interact with the iOS Simulator. Take screenshots, inspect UI hierarchy, tap, swipe, type, set GPS location, and more.

## Quick Start

```bash
# 1. Install prerequisites
xcode-select --install
brew tap facebook/fb
brew install idb-companion uv pipx
pipx ensurepath
pipx install fb-idb --python python3.11

# 2. Clone and install the MCP
git clone <repo-url> ~/ios-simulator-mcp
cd ~/ios-simulator-mcp
uv sync

# 3. Add to ~/.claude/settings.json
# {
#   "mcpServers": {
#     "ios-simulator": {
#       "command": "uv",
#       "args": ["run", "--directory", "~/ios-simulator-mcp", "ios-simulator-mcp"]
#     }
#   }
# }

# 4. Restart Claude Code
```

## Architecture

This MCP uses two underlying tools:

| Tool | Source | Used For |
|------|--------|----------|
| `xcrun simctl` | Built into Xcode | Simulator management, screenshots, location, URLs |
| `idb` | Facebook IDB | UI interactions (tap, swipe, type), UI hierarchy, app management |

## Prerequisites

### 1. Xcode Command Line Tools

```bash
xcode-select --install
```

### 2. Facebook IDB (iOS Development Bridge)

IDB is required for UI interactions (tap, swipe, type, UI hierarchy). It has **two components** that must both be installed:

#### a) idb-companion (the backend service)

```bash
brew tap facebook/fb
brew install idb-companion
```

#### b) idb CLI (the command-line interface)

The `idb` command comes from the `fb-idb` Python package. Install it globally with pipx:

```bash
# Install pipx if you don't have it
brew install pipx
pipx ensurepath

# Install fb-idb globally (use Python 3.11 for compatibility)
pipx install fb-idb --python python3.11
```

> **Note**: The `fb-idb` package has compatibility issues with Python 3.14. Use Python 3.11 or 3.12.

#### Verify IDB installation

```bash
# Check idb-companion
which idb_companion
# Should output: /opt/homebrew/bin/idb_companion

# Check idb CLI
which idb
# Should output: ~/.local/bin/idb

# Test connectivity
idb list-targets
# Should list all available simulators
```

### 3. uv (Python package manager)

```bash
brew install uv
```

## Installation

Clone or download this repository, then install dependencies:

```bash
cd /path/to/ios-simulator-mcp
uv sync
```

## Claude Code Configuration

Add to your Claude Code MCP settings. You can add this to either:
- `~/.claude/settings.json` (global - recommended)
- `.mcp.json` in your project root (project-specific)

```json
{
  "mcpServers": {
    "ios-simulator": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ios-simulator-mcp", "ios-simulator-mcp"]
    }
  }
}
```

Replace `/path/to/ios-simulator-mcp` with the actual path where you installed this project.

Then restart Claude Code or run `/mcp` to reload MCP servers.

## Available Tools

### Simulator Management

| Tool | Description |
|------|-------------|
| `list_simulators` | List all available simulators with state and UDID |
| `boot_simulator` | Boot a simulator (auto-selects if none specified) |
| `get_device_info` | Get info about connected simulator |

### Screenshots & UI Inspection

| Tool | Description |
|------|-------------|
| `screenshot` | Capture screenshot (returns image for visual inspection) |
| `get_ui_hierarchy` | Get UI element tree with positions and labels |

### User Interactions

| Tool | Description |
|------|-------------|
| `tap` | Tap at x,y coordinates |
| `long_press` | Long press at coordinates |
| `swipe` | Swipe from one point to another |
| `type_text` | Type text into focused field |
| `tap_and_type` | Tap on field then type |
| `press_button` | Press hardware button (home, lock, siri, volume) |
| `shake` | Trigger shake gesture |

### App Management

| Tool | Description |
|------|-------------|
| `launch_app` | Launch app by bundle ID |
| `terminate_app` | Kill running app |
| `install_app` | Install .app bundle |
| `uninstall_app` | Uninstall app by bundle ID |
| `open_url` | Open URL (great for deep links) |

### Location

| Tool | Description |
|------|-------------|
| `set_location` | Set GPS coordinates |
| `clear_location` | Clear simulated location |

### Utility

| Tool | Description |
|------|-------------|
| `wait` | Wait for specified seconds |

## Usage Examples

Once configured, Claude Code can use these tools:

### Visual verification after implementing a feature

```
Claude: Let me check how the new balance screen looks.
[Uses screenshot tool]
Claude: I can see the balance card is displaying correctly with the $50.00
amount. However, the "Add Funds" button appears to be cut off on the right edge.
Let me fix the padding...
```

### Testing a flow

```
Claude: I'll test the login flow.
[Uses launch_app with bundle_id "com.thefreeride.rider.dev"]
[Uses screenshot to see current state]
[Uses get_ui_hierarchy to find the email field coordinates]
[Uses tap_and_type to enter email]
[Uses tap to press login button]
[Uses wait for 2 seconds]
[Uses screenshot to verify login succeeded]
```

### Testing location-based features

```
Claude: Let me test the pickup location feature in San Francisco.
[Uses set_location with lat=37.7749, lng=-122.4194]
[Uses screenshot to verify map updated]
```

## Troubleshooting

### MCP tools not appearing in Claude Code

1. Check that the MCP is configured in `~/.claude/settings.json` or `.mcp.json`
2. Restart Claude Code or run `/mcp` to reload servers
3. Check for errors in the MCP server startup

### "idb: command not found"

This is the most common issue. The `fb-idb` Python package must be installed globally, not just in the MCP's virtual environment:

```bash
# Install pipx if needed
brew install pipx
pipx ensurepath

# Install fb-idb globally with Python 3.11 (3.14 has compatibility issues)
pipx install fb-idb --python python3.11

# Verify
which idb  # Should show ~/.local/bin/idb
```

### "No simulator connected"

The MCP will auto-connect to a booted simulator. If none is booted, use:
```
boot_simulator with device_name="iPhone 15 Pro"
```

Or boot one manually:
```bash
xcrun simctl boot "iPhone 16"
```

### IDB connection issues

Restart the idb companion:
```bash
idb kill
idb_companion --udid <simulator-udid>
```

Or connect manually:
```bash
idb connect <simulator-udid>
```

### UI hierarchy returns empty

Make sure the simulator has an app open. The accessibility tree may be empty on the home screen or system dialogs.

### Screenshots fail

Ensure the simulator is fully booted and visible. Test with:
```bash
xcrun simctl io booted screenshot /tmp/test.png
```

### Python version issues with fb-idb

If you see errors like `RuntimeError: There is no current event loop`, you're likely using Python 3.14 which has asyncio changes incompatible with fb-idb. Reinstall with an older Python:

```bash
pipx uninstall fb-idb
pipx install fb-idb --python python3.11
```

## Development

```bash
cd /path/to/ios-simulator-mcp
uv sync
uv run ios-simulator-mcp  # runs the server directly (for testing)
```

## How It Works

When Claude Code calls a tool:

1. **Simulator management** (`list_simulators`, `boot_simulator`) uses `xcrun simctl`
2. **Screenshots** use `xcrun simctl io <udid> screenshot`
3. **UI interactions** (`tap`, `swipe`, `type_text`) use `idb ui` commands
4. **UI hierarchy** uses `idb ui describe-all` to get the accessibility tree
5. **App management** (`launch_app`, `terminate_app`) uses `idb` commands
6. **Location** uses `xcrun simctl location`

The MCP automatically connects to an already-booted simulator, or boots the latest iPhone if none is running.

## Limitations

- **macOS only** - iOS Simulator only runs on macOS
- **Simulator only** - Does not support physical iOS devices (idb does, but this MCP is configured for simulators)
- **UI hierarchy on app screens** - The accessibility tree may be empty or limited on the home screen, system dialogs, or apps without accessibility labels
- **Coordinate-based interactions** - Taps and swipes use absolute coordinates; you'll need to use `get_ui_hierarchy` to find element positions
- **No gesture recording** - Complex multi-touch gestures are not supported
- **Screenshot size** - Screenshots are compressed to JPEG and capped at ~2MB for efficient transmission

## License

MIT
