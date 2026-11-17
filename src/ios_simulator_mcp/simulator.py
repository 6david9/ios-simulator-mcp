"""
iOS Simulator Controller

Provides low-level control of iOS Simulator via xcrun simctl and idb.
"""

import subprocess
import json
import base64
import tempfile
import os
import time
import re
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image
import io


class SimulatorController:
    """Controls an iOS Simulator instance."""

    def __init__(self, udid: Optional[str] = None):
        self.udid = udid

    def _run_simctl(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run an xcrun simctl command."""
        cmd = ["xcrun", "simctl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _run_idb(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run an idb command with UDID targeting."""
        cmd = ["idb"] + args

        # Commands that don't need UDID
        commands_without_udid = ["list-targets", "connect", "boot", "create", "delete", "delete-all"]

        # Add --udid parameter if we have a UDID and command needs it
        if self.udid and len(args) > 0:
            command_name = args[0]

            if command_name not in commands_without_udid:
                if command_name == "ui" and len(args) > 1:
                    # For UI commands: ['ui', 'tap'] -> ['ui', 'tap', '--udid', 'UDID']
                    cmd = ["idb"] + args[:2] + ["--udid", self.udid] + args[2:]
                else:
                    # For other commands: ['screenshot'] -> ['screenshot', '--udid', 'UDID']
                    cmd = ["idb"] + args[:1] + ["--udid", self.udid] + args[1:]

        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    # -------------------------------------------------------------------------
    # Simulator Management
    # -------------------------------------------------------------------------

    def list_simulators(self) -> List[Dict[str, Any]]:
        """List all available simulators."""
        result = self._run_simctl(["list", "devices", "-j"])
        if result.returncode != 0:
            return []

        try:
            data = json.loads(result.stdout)
            devices = []
            for runtime, device_list in data.get("devices", {}).items():
                # Extract iOS version from runtime string
                ios_version = runtime.split(".")[-1] if "iOS" in runtime else runtime
                for device in device_list:
                    device["runtime"] = ios_version
                    devices.append(device)
            return devices
        except json.JSONDecodeError:
            return []

    def list_booted_simulators(self) -> List[Dict[str, Any]]:
        """List only booted simulators."""
        all_devices = self.list_simulators()
        return [d for d in all_devices if d.get("state") == "Booted"]

    def get_device_info(self) -> Optional[Dict[str, Any]]:
        """Get info about the current simulator."""
        if not self.udid:
            return None

        all_devices = self.list_simulators()
        for device in all_devices:
            if device.get("udid") == self.udid:
                return device
        return None

    def boot_simulator(self, udid: Optional[str] = None) -> Tuple[bool, str]:
        """Boot a simulator by UDID."""
        target_udid = udid or self.udid
        if not target_udid:
            return False, "No UDID specified"

        result = self._run_simctl(["boot", target_udid])
        if result.returncode == 0:
            self.udid = target_udid
            # Connect idb to the booted simulator
            self._run_idb(["connect", target_udid])
            return True, f"Booted simulator {target_udid}"
        else:
            # Check if already booted
            if "current state: Booted" in result.stderr:
                self.udid = target_udid
                self._run_idb(["connect", target_udid])
                return True, f"Simulator {target_udid} already booted"
            return False, result.stderr

    def list_device_udids(self) -> Dict[str, Any]:
        """Return all and booted simulator summaries with UDIDs."""
        def summarize(device: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "name": device.get("name", "Unknown"),
                "udid": device.get("udid", ""),
                "state": device.get("state", "Unknown"),
                "runtime": device.get("runtime", ""),
            }

        all_devices = [summarize(d) for d in self.list_simulators() if d.get("udid")]
        booted = [d for d in all_devices if d.get("state") == "Booted"]
        return {
            "all": all_devices,
            "booted": booted,
            "booted_count": len(booted),
            "all_count": len(all_devices),
        }

    def ensure_ready(
        self,
        auto_boot: bool = True,
        udid: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Ensure self.udid points at a currently Booted simulator.

        Prefer an explicit udid from the caller. Otherwise reuse a still-Booted
        cached UDID. If the cache is stale, reconnect only when exactly one
        simulator is Booted; when multiple are Booted the caller must pass udid.
        Optionally boot a simulator when none are running.
        """
        booted = self.list_booted_simulators()
        booted_by_udid = {d.get("udid"): d for d in booted if d.get("udid")}

        if udid:
            target = booted_by_udid.get(udid)
            if target:
                self.udid = udid
                self._run_idb(["connect", self.udid])
                return True, f"Using simulator: {target.get('name', udid)}"

            if not auto_boot:
                # Still select the requested device so callers see a clear target.
                all_devices = self.list_simulators()
                named = next((d for d in all_devices if d.get("udid") == udid), None)
                if not named:
                    return False, f"Unknown simulator UDID: {udid}"
                self.udid = None
                return False, (
                    f"Simulator {named.get('name', udid)} ({udid}) is "
                    f"{named.get('state', 'Unknown')}, not Booted"
                )

            success, message = self.boot_simulator(udid)
            if success:
                return True, message
            return False, message

        if self.udid and self.udid in booted_by_udid:
            name = booted_by_udid[self.udid].get("name", self.udid)
            return True, f"Using already booted simulator: {name}"

        if len(booted) == 1:
            previous = self.udid
            target = booted[0]
            self.udid = target["udid"]
            self._run_idb(["connect", self.udid])
            name = target.get("name", self.udid)
            if previous:
                return True, (
                    f"Cached simulator {previous} is no longer Booted; "
                    f"switched to {name}"
                )
            return True, f"Using already booted simulator: {name}"

        if len(booted) > 1:
            self.udid = None
            names = ", ".join(
                f"{d.get('name', 'Unknown')} ({d.get('udid')})" for d in booted
            )
            return False, (
                "Multiple simulators are Booted; pass udid to select one. "
                f"Booted: {names}. Use list_device_udids to inspect."
            )

        # Drop stale cache so callers do not keep targeting a Shutdown device.
        self.udid = None
        if not auto_boot:
            return False, "No simulator connected"

        return self.find_and_boot_simulator()

    def find_and_boot_simulator(self, device_name: Optional[str] = None) -> Tuple[bool, str]:
        """Find a suitable simulator and boot it.

        Priority:
        1. Keep the currently selected simulator if it is still Booted
        2. Use another already booted simulator
        3. Boot simulator matching device_name if provided
        4. Boot latest available iPhone
        """
        # Check for already booted simulators
        booted = self.list_booted_simulators()
        if booted:
            if self.udid:
                for device in booted:
                    if device.get("udid") == self.udid:
                        self._run_idb(["connect", self.udid])
                        return True, (
                            f"Using already booted simulator: "
                            f"{device.get('name', self.udid)}"
                        )
            self.udid = booted[0]["udid"]
            # Ensure idb is connected
            self._run_idb(["connect", self.udid])
            return True, f"Using already booted simulator: {booted[0].get('name', self.udid)}"

        # Find a simulator to boot
        all_devices = self.list_simulators()
        available = [d for d in all_devices if d.get("isAvailable", False)]

        if not available:
            return False, "No available simulators found"

        target_device = None

        # Try to match device_name if provided
        if device_name:
            for device in available:
                if device_name.lower() in device.get("name", "").lower():
                    target_device = device
                    break

        # Otherwise pick latest iPhone
        if not target_device:
            iphones = [d for d in available if "iPhone" in d.get("name", "")]
            if iphones:
                # Sort by name to get latest (iPhone 15 > iPhone 14, etc.)
                iphones.sort(key=lambda x: x.get("name", ""), reverse=True)
                target_device = iphones[0]
            else:
                target_device = available[0]

        # Boot the selected device
        return self.boot_simulator(target_device["udid"])

    def connect(self, udid: str) -> Tuple[bool, str]:
        """Connect to a specific simulator by UDID."""
        self.udid = udid
        result = self._run_idb(["connect", udid])
        if result.returncode == 0:
            return True, f"Connected to {udid}"
        return False, result.stderr

    # -------------------------------------------------------------------------
    # Screenshots and UI Hierarchy
    # -------------------------------------------------------------------------

    def screenshot(self, output_path: Optional[str] = None) -> Tuple[bool, str]:
        """Capture a screenshot and save to file."""
        if not self.udid:
            return False, "No simulator connected"

        if not output_path:
            output_path = tempfile.mktemp(suffix=".png")

        result = self._run_simctl(["io", self.udid, "screenshot", output_path])
        if result.returncode == 0 and os.path.exists(output_path):
            return True, output_path
        return False, result.stderr

    def screenshot_base64(self, max_size_mb: float = 2, quality: int = 85) -> Tuple[bool, str]:
        """Capture screenshot and return as base64 string.

        Compresses to JPEG and ensures size is under max_size_mb.
        """
        if not self.udid:
            return False, "No simulator connected"

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result = self._run_simctl(["io", self.udid, "screenshot", temp_path])
            if result.returncode != 0:
                return False, f"Screenshot failed: {result.stderr}"

            if not os.path.exists(temp_path):
                return False, "Screenshot file not created"

            # Process and compress the image
            with Image.open(temp_path) as img:
                # Convert RGBA to RGB (JPEG doesn't support transparency)
                if img.mode == "RGBA":
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])
                    img = rgb_img
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                max_size_bytes = max_size_mb * 1024 * 1024
                current_quality = quality

                # Compress to JPEG
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=current_quality, optimize=True)

                # Reduce quality if too large
                while output.tell() > max_size_bytes and current_quality > 20:
                    output = io.BytesIO()
                    current_quality -= 10
                    img.save(output, format="JPEG", quality=current_quality, optimize=True)

                # Resize if still too large
                if output.tell() > max_size_bytes:
                    scale_factor = (max_size_bytes / output.tell()) ** 0.5
                    new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    img.save(output, format="JPEG", quality=current_quality, optimize=True)

                screenshot_data = output.getvalue()
                return True, base64.b64encode(screenshot_data).decode("utf-8")

        except Exception as e:
            return False, f"Error processing screenshot: {e}"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def get_ui_hierarchy(self) -> Tuple[bool, Any]:
        """Get the UI element hierarchy via idb describe-all."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_idb(["ui", "describe-all"])
        if result.returncode == 0:
            try:
                return True, json.loads(result.stdout)
            except json.JSONDecodeError:
                return True, result.stdout
        return False, result.stderr

    # -------------------------------------------------------------------------
    # User Interactions
    # -------------------------------------------------------------------------

    def tap(self, x: float, y: float) -> Tuple[bool, str]:
        """Tap at specific coordinates."""
        if not self.udid:
            return False, "No simulator connected"

        x_int = int(round(x))
        y_int = int(round(y))
        result = self._run_idb(["ui", "tap", str(x_int), str(y_int)])
        if result.returncode == 0:
            return True, f"Tapped at ({x_int}, {y_int})"
        return False, result.stderr

    def long_press(self, x: float, y: float, duration: float = 1.0) -> Tuple[bool, str]:
        """Long press at specific coordinates."""
        if not self.udid:
            return False, "No simulator connected"

        x_int = int(round(x))
        y_int = int(round(y))
        # idb doesn't have native long press, simulate with tap + hold
        result = self._run_idb(["ui", "tap", str(x_int), str(y_int), "--duration", str(duration)])
        if result.returncode == 0:
            return True, f"Long pressed at ({x_int}, {y_int}) for {duration}s"
        return False, result.stderr

    def swipe(self, x_start: float, y_start: float, x_end: float, y_end: float, duration: float = 0.5) -> Tuple[bool, str]:
        """Swipe from one point to another."""
        if not self.udid:
            return False, "No simulator connected"

        x1 = int(round(x_start))
        y1 = int(round(y_start))
        x2 = int(round(x_end))
        y2 = int(round(y_end))

        result = self._run_idb(["ui", "swipe", str(x1), str(y1), str(x2), str(y2), "--duration", str(duration)])
        if result.returncode == 0:
            return True, f"Swiped from ({x1}, {y1}) to ({x2}, {y2})"
        return False, result.stderr

    def type_text(self, text: str) -> Tuple[bool, str]:
        """Type text into the currently focused field."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_idb(["ui", "text", text])
        if result.returncode == 0:
            return True, f"Typed: {text}"
        return False, result.stderr

    def tap_and_type(self, x: float, y: float, text: str) -> Tuple[bool, str]:
        """Tap on a field and type text."""
        tap_success, tap_msg = self.tap(x, y)
        if not tap_success:
            return False, f"Tap failed: {tap_msg}"

        time.sleep(0.3)  # Brief delay to ensure field is focused

        return self.type_text(text)

    def press_button(self, button: str) -> Tuple[bool, str]:
        """Press a hardware button.

        Supported buttons: home, lock, siri, volume_up, volume_down
        """
        if not self.udid:
            return False, "No simulator connected"

        button_map = {
            "home": ["ui", "button", "HOME"],
            "lock": ["ui", "button", "LOCK"],
            "siri": ["ui", "button", "SIRI"],
            "volume_up": ["ui", "button", "VOLUME_UP"],
            "volume_down": ["ui", "button", "VOLUME_DOWN"],
            "apple_pay": ["ui", "button", "APPLE_PAY"],
        }

        if button.lower() not in button_map:
            return False, f"Unknown button: {button}. Supported: {list(button_map.keys())}"

        result = self._run_idb(button_map[button.lower()])
        if result.returncode == 0:
            return True, f"Pressed {button} button"
        return False, result.stderr

    def shake(self) -> Tuple[bool, str]:
        """Trigger shake gesture."""
        if not self.udid:
            return False, "No simulator connected"

        # Use simctl for shake
        result = self._run_simctl(["notify_post", self.udid, "com.apple.UIKit.shake"])
        if result.returncode == 0:
            return True, "Shake gesture triggered"
        return False, result.stderr

    # -------------------------------------------------------------------------
    # App Management
    # -------------------------------------------------------------------------

    def launch_app(self, bundle_id: str) -> Tuple[bool, str]:
        """Launch an app by bundle ID."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_idb(["launch", bundle_id])
        if result.returncode == 0:
            return True, f"Launched {bundle_id}"
        return False, result.stderr

    def terminate_app(self, bundle_id: str) -> Tuple[bool, str]:
        """Terminate a running app."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_idb(["terminate", bundle_id])
        if result.returncode == 0:
            return True, f"Terminated {bundle_id}"
        return False, result.stderr

    def install_app(self, app_path: str) -> Tuple[bool, str]:
        """Install an app from .app bundle path."""
        if not self.udid:
            return False, "No simulator connected"

        if not os.path.exists(app_path):
            return False, f"App not found at: {app_path}"

        result = self._run_idb(["install", app_path])
        if result.returncode == 0:
            return True, f"Installed {app_path}"
        return False, result.stderr

    def uninstall_app(self, bundle_id: str) -> Tuple[bool, str]:
        """Uninstall an app by bundle ID."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_idb(["uninstall", bundle_id])
        if result.returncode == 0:
            return True, f"Uninstalled {bundle_id}"
        return False, result.stderr

    def open_url(self, url: str) -> Tuple[bool, str]:
        """Open a URL (useful for deep links)."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_simctl(["openurl", self.udid, url])
        if result.returncode == 0:
            return True, f"Opened URL: {url}"
        return False, result.stderr

    # -------------------------------------------------------------------------
    # Location
    # -------------------------------------------------------------------------

    def set_location(self, latitude: float, longitude: float) -> Tuple[bool, str]:
        """Set the simulator's GPS location."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_simctl(["location", self.udid, "set", str(latitude) + "," + str(longitude)])
        if result.returncode == 0:
            return True, f"Location set to ({latitude}, {longitude})"
        return False, result.stderr

    def clear_location(self) -> Tuple[bool, str]:
        """Clear the simulated location."""
        if not self.udid:
            return False, "No simulator connected"

        result = self._run_simctl(["location", self.udid, "clear"])
        if result.returncode == 0:
            return True, "Location cleared"
        return False, result.stderr

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def wait(self, seconds: float = 1.0) -> Tuple[bool, str]:
        """Wait for specified seconds."""
        time.sleep(seconds)
        return True, f"Waited {seconds} seconds"
