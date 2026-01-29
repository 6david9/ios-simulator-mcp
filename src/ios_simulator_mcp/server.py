"""
iOS Simulator MCP Server

Exposes iOS Simulator control as MCP tools for Claude Code.
"""

import os
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

from .simulator import SimulatorController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ios-simulator-mcp")

# Global simulator controller
simulator = SimulatorController()


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("ios-simulator-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        return [
            # Simulator Management
            Tool(
                name="list_simulators",
                description="List all available iOS simulators with their state (Booted/Shutdown), UDID, and iOS version",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "only_booted": {
                            "type": "boolean",
                            "description": "If true, only return currently booted simulators",
                            "default": False,
                        }
                    },
                },
            ),
            Tool(
                name="boot_simulator",
                description="Boot a simulator. If no device specified, will use already booted simulator or boot the latest available iPhone",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_name": {
                            "type": "string",
                            "description": "Optional device name to match (e.g., 'iPhone 15 Pro'). If not provided, uses booted simulator or boots latest iPhone",
                        }
                    },
                },
            ),
            Tool(
                name="get_device_info",
                description="Get information about the currently connected simulator (name, UDID, state, iOS version)",
                inputSchema={"type": "object", "properties": {}},
            ),
            # Screenshots and UI
            Tool(
                name="screenshot",
                description="Capture a screenshot of the simulator. Returns the image for visual inspection of the current UI state",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_ui_hierarchy",
                description="Get the UI element hierarchy showing all visible elements with their types, labels, positions (frame: x, y, width, height), and accessibility info. Use this to find element coordinates for tap/swipe actions",
                inputSchema={"type": "object", "properties": {}},
            ),
            # Interactions
            Tool(
                name="tap",
                description="Tap at specific screen coordinates. Use get_ui_hierarchy to find element positions first",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate to tap"},
                        "y": {"type": "number", "description": "Y coordinate to tap"},
                    },
                    "required": ["x", "y"],
                },
            ),
            Tool(
                name="long_press",
                description="Long press at specific coordinates for a duration",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "duration": {
                            "type": "number",
                            "description": "Duration in seconds (default: 1.0)",
                            "default": 1.0,
                        },
                    },
                    "required": ["x", "y"],
                },
            ),
            Tool(
                name="swipe",
                description="Swipe from one point to another. Useful for scrolling (swipe up to scroll down) or dismissing elements",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x_start": {"type": "number", "description": "Starting X coordinate"},
                        "y_start": {"type": "number", "description": "Starting Y coordinate"},
                        "x_end": {"type": "number", "description": "Ending X coordinate"},
                        "y_end": {"type": "number", "description": "Ending Y coordinate"},
                        "duration": {
                            "type": "number",
                            "description": "Swipe duration in seconds (default: 0.5)",
                            "default": 0.5,
                        },
                    },
                    "required": ["x_start", "y_start", "x_end", "y_end"],
                },
            ),
            Tool(
                name="type_text",
                description="Type text into the currently focused text field. Make sure a text field is focused first (tap on it)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="tap_and_type",
                description="Tap on a text field to focus it, then type text. Combines tap + type_text in one action",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate of the text field"},
                        "y": {"type": "number", "description": "Y coordinate of the text field"},
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["x", "y", "text"],
                },
            ),
            Tool(
                name="press_button",
                description="Press a hardware button on the simulator",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "description": "Button to press: home, lock, siri, volume_up, volume_down, apple_pay",
                            "enum": ["home", "lock", "siri", "volume_up", "volume_down", "apple_pay"],
                        },
                    },
                    "required": ["button"],
                },
            ),
            Tool(
                name="shake",
                description="Trigger a shake gesture on the simulator (useful for 'shake to undo' or debug menus)",
                inputSchema={"type": "object", "properties": {}},
            ),
            # App Management
            Tool(
                name="launch_app",
                description="Launch an app by its bundle ID (e.g., 'com.thefreeride.rider.dev' for Rider dev app)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bundle_id": {
                            "type": "string",
                            "description": "Bundle ID of the app to launch",
                        },
                    },
                    "required": ["bundle_id"],
                },
            ),
            Tool(
                name="terminate_app",
                description="Terminate (kill) a running app",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bundle_id": {
                            "type": "string",
                            "description": "Bundle ID of the app to terminate",
                        },
                    },
                    "required": ["bundle_id"],
                },
            ),
            Tool(
                name="install_app",
                description="Install an app from a .app bundle path",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "app_path": {
                            "type": "string",
                            "description": "Path to the .app bundle",
                        },
                    },
                    "required": ["app_path"],
                },
            ),
            Tool(
                name="uninstall_app",
                description="Uninstall an app by bundle ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bundle_id": {
                            "type": "string",
                            "description": "Bundle ID of the app to uninstall",
                        },
                    },
                    "required": ["bundle_id"],
                },
            ),
            Tool(
                name="open_url",
                description="Open a URL in the simulator. Useful for testing deep links (e.g., 'ridecircuit://ride/123')",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to open (can be http://, https://, or custom scheme)",
                        },
                    },
                    "required": ["url"],
                },
            ),
            # Location
            Tool(
                name="set_location",
                description="Set the simulator's GPS location. Essential for testing location-based features like ride pickup/dropoff",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number", "description": "Latitude coordinate"},
                        "longitude": {"type": "number", "description": "Longitude coordinate"},
                    },
                    "required": ["latitude", "longitude"],
                },
            ),
            Tool(
                name="clear_location",
                description="Clear the simulated GPS location, returning to default behavior",
                inputSchema={"type": "object", "properties": {}},
            ),
            # Utility
            Tool(
                name="wait",
                description="Wait for a specified number of seconds. Use when you need to wait for animations, network requests, or state changes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "seconds": {
                            "type": "number",
                            "description": "Seconds to wait (default: 1.0)",
                            "default": 1.0,
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
        """Handle tool calls."""
        global simulator

        try:
            # Simulator Management
            if name == "list_simulators":
                only_booted = arguments.get("only_booted", False)
                if only_booted:
                    devices = simulator.list_booted_simulators()
                else:
                    devices = simulator.list_simulators()

                # Format output nicely
                if not devices:
                    return [TextContent(type="text", text="No simulators found")]

                lines = []
                for d in devices:
                    state = d.get("state", "Unknown")
                    name_str = d.get("name", "Unknown")
                    udid = d.get("udid", "")
                    runtime = d.get("runtime", "")
                    marker = "🟢" if state == "Booted" else "⚪"
                    lines.append(f"{marker} {name_str} ({runtime}) - {state}\n   UDID: {udid}")

                return [TextContent(type="text", text="\n".join(lines))]

            elif name == "boot_simulator":
                device_name = arguments.get("device_name")
                success, message = simulator.find_and_boot_simulator(device_name)
                return [TextContent(type="text", text=message)]

            elif name == "get_device_info":
                if not simulator.udid:
                    # Try to auto-connect to a booted simulator
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator connected. {msg}")]

                info = simulator.get_device_info()
                if info:
                    return [TextContent(type="text", text=json.dumps(info, indent=2))]
                return [TextContent(type="text", text="Could not get device info")]

            # Screenshots and UI
            elif name == "screenshot":
                # Auto-connect if needed
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]

                success, result = simulator.screenshot_base64()
                if success:
                    return [
                        ImageContent(type="image", data=result, mimeType="image/jpeg"),
                        TextContent(type="text", text="Screenshot captured successfully"),
                    ]
                return [TextContent(type="text", text=f"Screenshot failed: {result}")]

            elif name == "get_ui_hierarchy":
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]

                success, result = simulator.get_ui_hierarchy()
                if success:
                    if isinstance(result, dict) or isinstance(result, list):
                        return [TextContent(type="text", text=json.dumps(result, indent=2))]
                    return [TextContent(type="text", text=str(result))]
                return [TextContent(type="text", text=f"Failed to get UI hierarchy: {result}")]

            # Interactions
            elif name == "tap":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.tap(arguments["x"], arguments["y"])
                return [TextContent(type="text", text=message)]

            elif name == "long_press":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                duration = arguments.get("duration", 1.0)
                success, message = simulator.long_press(arguments["x"], arguments["y"], duration)
                return [TextContent(type="text", text=message)]

            elif name == "swipe":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                duration = arguments.get("duration", 0.5)
                success, message = simulator.swipe(
                    arguments["x_start"],
                    arguments["y_start"],
                    arguments["x_end"],
                    arguments["y_end"],
                    duration,
                )
                return [TextContent(type="text", text=message)]

            elif name == "type_text":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.type_text(arguments["text"])
                return [TextContent(type="text", text=message)]

            elif name == "tap_and_type":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.tap_and_type(
                    arguments["x"], arguments["y"], arguments["text"]
                )
                return [TextContent(type="text", text=message)]

            elif name == "press_button":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.press_button(arguments["button"])
                return [TextContent(type="text", text=message)]

            elif name == "shake":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.shake()
                return [TextContent(type="text", text=message)]

            # App Management
            elif name == "launch_app":
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]
                success, message = simulator.launch_app(arguments["bundle_id"])
                return [TextContent(type="text", text=message)]

            elif name == "terminate_app":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.terminate_app(arguments["bundle_id"])
                return [TextContent(type="text", text=message)]

            elif name == "install_app":
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]
                success, message = simulator.install_app(arguments["app_path"])
                return [TextContent(type="text", text=message)]

            elif name == "uninstall_app":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.uninstall_app(arguments["bundle_id"])
                return [TextContent(type="text", text=message)]

            elif name == "open_url":
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]
                success, message = simulator.open_url(arguments["url"])
                return [TextContent(type="text", text=message)]

            # Location
            elif name == "set_location":
                if not simulator.udid:
                    success, msg = simulator.find_and_boot_simulator()
                    if not success:
                        return [TextContent(type="text", text=f"No simulator available: {msg}")]
                success, message = simulator.set_location(
                    arguments["latitude"], arguments["longitude"]
                )
                return [TextContent(type="text", text=message)]

            elif name == "clear_location":
                if not simulator.udid:
                    return [TextContent(type="text", text="No simulator connected. Use boot_simulator first.")]
                success, message = simulator.clear_location()
                return [TextContent(type="text", text=message)]

            # Utility
            elif name == "wait":
                seconds = arguments.get("seconds", 1.0)
                success, message = simulator.wait(seconds)
                return [TextContent(type="text", text=message)]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.exception(f"Error executing tool {name}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def run_server():
    """Run the MCP server."""
    server = create_server()
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main():
    """Entry point."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
