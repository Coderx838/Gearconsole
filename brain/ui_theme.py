"""
=============================================================================
GEAR CONSOLE: HIGH-TECH TERMINAL UI & ANIMATION ENGINE
=============================================================================
Provides modern, colorful, animated console interface for Gear Console v1.0.3:
  1. Neon Gradient ASCII Banner & Boot Sequence
  2. Live Telemetry Panels & Status Badges
  3. Interactive Rounded Control Menu
  4. Real-time Cockpit Layouts for ALL Modes (1-5, S, B, C)
=============================================================================
"""

import sys
import os
import time
from typing import Optional, Dict, Any, List

# Ensure Windows terminal standard output handles UTF-8 cleanly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.layout import Layout
from rich import box

console = Console(force_terminal=True, highlight=False)

APP_NAME = "GEAR CONSOLE"
APP_VERSION = "1.0.3"
APP_TAGLINE = "Autonomous AI RC Vehicle Intelligence System"

LOGO_LINES = [
    r"  ____  _____     _     ____     ____  _____  _   _  ____  _____  _      _____ ",
    r" / ___|| ____|   / \   |  _ \   / ___|/ _ \ \| \ | |/ ___|| _ \ || |    | ____|",
    r"| |  _ |  _|    / _ \  | |_) | | |   | | | | |  \| |\___ \| | | || |    |  _|  ",
    r"| |_| || |___  / ___ \ |  _ <  | |___| |_| | | |\  | ___) | |_| || |___ | |___ ",
    r" \____||_____|/_/   \_\|_| \_\  \____|\___/ /|_| \_||____/|____/ |_____||_____|",
]

GRADIENT_COLORS = [
    "cyan",
    "bright_cyan",
    "dodger_blue1",
    "medium_purple1",
    "bright_magenta",
]


def print_banner(animated: bool = False):
    """Prints neon gradient logo with high-tech badge styling."""
    console.print()
    for i, line in enumerate(LOGO_LINES):
        color = GRADIENT_COLORS[i % len(GRADIENT_COLORS)]
        console.print(f"[bold {color}]{line}[/bold {color}]")
        if animated:
            time.sleep(0.03)

    console.print(f"  [bold white on purple] >> {APP_NAME} [/bold white on purple] [bold black on cyan] v{APP_VERSION} [/bold black on cyan] [italic cyan]--- {APP_TAGLINE}[/italic cyan]")
    console.print()


def boot_sequence():
    """Plays quick high-tech startup animation."""
    print_banner(animated=True)
    steps = [
        ("Initializing WinRT BLE 140ms Subsystem", "cyan"),
        ("Loading Multi-Room 2D Floorplan Engine", "bright_cyan"),
        ("Connecting Gemini 3.5 Multimodal VLM Brain", "bright_magenta"),
        ("Arming 20Hz Emergency Auto-Brake Reflex Guard", "bright_green"),
    ]
    for msg, col in steps:
        console.print(f"  [bold {col}]>>[/bold {col}] [white]{msg}...[/white] [bold green][ONLINE][/bold green]")
        time.sleep(0.05)
    console.print()


def render_menu(cam_source: str, is_connected: bool = True, mac: str = "") -> Panel:
    """Renders the master control menu in a modern cyber panel."""
    status_badge = "[bold green](*) CONNECTED[/bold green]" if is_connected else "[bold yellow](x) STANDBY (SIM)[/bold yellow]"
    stream_badge = f"[bold cyan]{cam_source}[/bold cyan]"

    table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
    table.add_column("Key", style="bold magenta", width=8, justify="center")
    table.add_column("Mode", style="bold white", width=26)
    table.add_column("Description", style="dim cyan")

    table.add_row("[1]", "[bold white]MANUAL DRIVING[/bold white]", "WASD Keyboard Full Physics Control + Headlights & Smoke")
    table.add_row("[2]", "[bold white]VOICE NAVIGATION[/bold white]", "Microphone Natural Speech Recognition (STT & TTS)")
    table.add_row("[3]", "[bold white]VISUAL TARGET TRACK[/bold white]", "OpenCV Computer Vision 'Follow-Me' PID Tracking")
    table.add_row("[4]", "[bold white]AUTONOMOUS EXPLORER[/bold white]", "Room Roaming with Real-time 2D Occupancy Mapping")
    table.add_row("[5]", "[bold cyan]EMBODIED LLM BRAIN[/bold cyan]", "Multimodal Gemini VLM Conscious Agent + 2D Localization")
    table.add_row("[S]", "[bold green]AI ROOM SCANNER[/bold green]", "Walkthrough Video 3D/2D Floorplan Reconstruction")
    table.add_row("[B]", "[bold #00c4ff]SCAN / SELECT BLE CAR[/bold #00c4ff]", "Auto-Discover & Pair Nearby Bluetooth Cars")
    table.add_row("[C]", "[bold yellow]CONFIGURE CAMERA[/bold yellow]", f"Switch Stream Source (Active: {stream_badge})")
    table.add_row("[Q]", "[bold red]QUIT CONSOLE[/bold red]", "Disconnect BLE and Safely Exit")

    header_text = f"Hardware: [bold white]{mac}[/bold white] | Status: {status_badge} | Stream: {stream_badge}"
    panel = Panel(
        table,
        title=f"[bold cyan]>> {APP_NAME} v{APP_VERSION} -- MASTER CONTROL CONSOLE <<[/bold cyan]",
        subtitle=f"[dim]{header_text}[/dim]",
        border_style="purple",
        box=box.ROUNDED,
        padding=(1, 2)
    )
    return panel


def render_cockpit_panel(mode_name: str, room: str, pos_x: float, pos_y: float, heading: float, dist: float, state: str = "READY") -> Panel:
    """Renders active flight cockpit telemetry card."""
    table = Table(box=box.ROUNDED, expand=True, border_style="cyan")
    table.add_column("Current Room", style="bold cyan", justify="center")
    table.add_column("Coordinates (X, Y)", style="bold green", justify="center")
    table.add_column("Compass Heading", style="bold yellow", justify="center")
    table.add_column("Distance Traveled", style="bold magenta", justify="center")
    table.add_column("System State", style="bold white", justify="center")

    state_col = "bright_green" if state in ["READY", "CRUISING", "CONNECTED"] else "yellow" if state in ["PLANNING", "EXECUTING", "LISTENING"] else "red"
    table.add_row(
        f"[bold white]{room}[/bold white]",
        f"({pos_x:+.2f}m, {pos_y:+.2f}m)",
        f"{heading:.0f} deg",
        f"{dist:.2f}m",
        f"[{state_col}](*) {state}[/{state_col}]"
    )

    return Panel(
        table,
        title=f"[bold cyan]>> COCKPIT TELEMETRY -- {mode_name.upper()} <<[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED
    )


def render_voice_event(speech_text: str, intent: Dict[str, Any], reply_text: str) -> Panel:
    """Renders sleek voice command processing card."""
    table = Table(box=box.SIMPLE, show_header=False, expand=True)
    table.add_column("Field", style="bold cyan", width=18)
    table.add_column("Value", style="bold white")

    table.add_row("User Spoke:", f"[bold yellow]\"{speech_text}\"[/bold yellow]")
    table.add_row("Extracted Intent:", f"[magenta]{intent.get('action', 'unknown').upper()}[/magenta] (Duration: {intent.get('duration', 1.0):.1f}s, Steer: {intent.get('steer')})")
    table.add_row("Voice Audio Reply:", f"[bold green]\"{reply_text}\"[/bold green]")

    return Panel(
        table,
        title="[bold #7000ff]>> VOICE COMMAND PROCESSED <<[/bold #7000ff]",
        border_style="#7000ff",
        box=box.ROUNDED
    )


def render_tracking_card(target_found: bool, offset_x: float, area_ratio: float, action: str) -> Panel:
    """Renders visual target tracking status card."""
    status_str = "[bold green](*) TARGET LOCKED[/bold green]" if target_found else "[bold yellow](?) SEARCHING FOR TARGET[/bold yellow]"
    action_str = f"[bold cyan]{action.upper()}[/bold cyan]" if target_found else "[dim]STANDBY[/dim]"

    table = Table(box=box.ROUNDED, expand=True, border_style="green")
    table.add_column("Status", justify="center")
    table.add_column("Target X-Offset", justify="center")
    table.add_column("Target Size Ratio", justify="center")
    table.add_column("Motor Response", justify="center")

    table.add_row(
        status_str,
        f"{offset_x:+.2f}",
        f"{area_ratio * 100:.1f}%",
        action_str
    )

    return Panel(
        table,
        title="[bold green]>> OPENCV TARGET TRACKING COCKPIT <<[/bold green]",
        border_style="green",
        box=box.ROUNDED
    )


def render_explorer_card(room: str, pos_x: float, pos_y: float, state: str, obstacle_info: str) -> Panel:
    """Renders autonomous room explorer status card."""
    table = Table(box=box.ROUNDED, expand=True, border_style="yellow")
    table.add_column("Room", style="bold white", justify="center")
    table.add_column("Coordinates", style="bold green", justify="center")
    table.add_column("Exploration Action", style="bold cyan", justify="center")
    table.add_column("Sonar Reflex Status", style="bold yellow", justify="center")

    table.add_row(
        room,
        f"({pos_x:+.2f}m, {pos_y:+.2f}m)",
        state,
        obstacle_info
    )

    return Panel(
        table,
        title="[bold yellow]>> AUTONOMOUS EXPLORER TELEMETRY <<[/bold yellow]",
        border_style="yellow",
        box=box.ROUNDED
    )


def render_scan_results(rooms_data: List[Dict[str, Any]]) -> Panel:
    """Renders floorplan scanner output table."""
    table = Table(title="[bold cyan]Reconstructed Multi-Room Layout[/bold cyan]", box=box.ROUNDED, expand=True)
    table.add_column("Room Name", style="bold cyan")
    table.add_column("Dimensions (W x L)", style="bold white")
    table.add_column("Landmarks & Furniture", style="bold green")

    for r in rooms_data:
        name = r.get("name", "Unknown")
        w = r.get("x_max", 0) - r.get("x_min", 0)
        h = r.get("y_max", 0) - r.get("y_min", 0)
        landmarks = ", ".join([lm.get("name", "") for lm in r.get("landmarks", [])]) or "None"
        table.add_row(name, f"{w:.1f}m x {h:.1f}m", landmarks)

    return Panel(
        table,
        title="[bold green]>> AI VIDEO WALKTHROUGH MAP RESULTS <<[/bold green]",
        border_style="green",
        box=box.ROUNDED
    )
