"""
=============================================================================
GEAR CONSOLE v1.0.3: AUTONOMOUS AI RC VEHICLE INTELLIGENCE SYSTEM
=============================================================================
High-Reliability Architecture for Micro-Vehicles:
  1. Neon Terminal UI & Animated Dashboard (Rich)
  2. Low-Level Fast Reflex Subsystem (20Hz Obstacle Emergency Auto-Brake)
  3. Dual-Layer Localization (Optical Green Cross Tracking + Dead-Reckoning)
  4. Non-Blocking Multimodal Gemini VLM Cognition
  5. Multi-Room AI Walkthrough Floorplan Mapping
  6. Fault-Tolerant Auto-Reconnection (BLE Disconnect Recovery)
=============================================================================
"""

import sys
import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any

from driver import (
    BLECarDriver, DEFAULT_MAC, PROFILE_SUPERCAR,
    load_mac_address, save_mac_address, scan_for_ble_cars
)
from vision import VisionEngine, GreenCrossTracker, AIRoomScanner, CV2_AVAILABLE
from brain import LLMBrain, VoiceEngine
from spatial import SpatialOdometry, RoomMapper
from brain.ui_theme import (
    console, print_banner, boot_sequence, render_menu, render_cockpit_panel,
    render_voice_event, render_tracking_card, render_explorer_card, render_scan_results,
    APP_NAME, APP_VERSION
)

from rich.panel import Panel
from rich.table import Table
from rich import box

if CV2_AVAILABLE:
    import cv2

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

class DimmedConsoleHandler(logging.Handler):
    """Formats background info/debug logs with dimmed grey styling so UI stays clean."""
    def emit(self, record):
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                console.print(f"  [bold red][ERROR][/bold red] [dim red]{record.getMessage()}[/dim red]")
            elif record.levelno >= logging.WARNING:
                console.print(f"  [yellow][WARN][/yellow] [dim yellow]{record.getMessage()}[/dim yellow]")
            else:
                console.print(f"  [dim grey50][INFO] {record.getMessage()}[/dim grey50]")
        except Exception:
            pass

# Configure root logger with dimmed handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(DimmedConsoleHandler())

logger = logging.getLogger("GearConsole")


class GearConsoleEngine:
    def __init__(self, mac_address: str = DEFAULT_MAC, camera_source: any = 0, gemini_api_key: Optional[str] = None):
        self.mac_address = mac_address
        self.camera_source = int(camera_source) if str(camera_source).isdigit() else camera_source
        self.gemini_api_key = gemini_api_key

        # Subsystems
        self.driver = BLECarDriver(mac_address=mac_address, flag_bit=PROFILE_SUPERCAR)
        self.odometry = SpatialOdometry()
        self.room_mapper = RoomMapper()
        self.green_tracker = GreenCrossTracker()
        self.vision = VisionEngine(camera_source=self.camera_source)
        self.voice = VoiceEngine(callback=self._handle_voice_intent)
        self.brain = LLMBrain(api_key=gemini_api_key)

        # Hook auto-disconnection callback
        self.driver.on_disconnect_callback = self._on_car_disconnected_event

        # State & Safety
        self._action_queue = asyncio.Queue()
        self._mode_running = False
        self.ai_state = "STANDBY"
        self.emergency_brake_active = False
        self.is_reconnecting = False
        self.should_exit = False

    def _on_car_disconnected_event(self):
        """Triggered automatically when physical car power button is turned off or link is lost."""
        if not self.is_reconnecting and not self.should_exit:
            asyncio.create_task(self.handle_disconnection_and_reconnect())

    async def handle_disconnection_and_reconnect(self, max_attempts: int = 5) -> bool:
        """
        Handles unexpected power-off / disconnection:
        Notifies user via voice, tries reconnecting for 5 attempts, and auto-exits if not found.
        """
        self.is_reconnecting = True
        self.driver.stop()

        alert = Panel(
            f"[bold yellow]Car [{self.mac_address}] disconnected / powered off.[/bold yellow]\n"
            f"[cyan]Attempting automatic reconnection (Max {max_attempts} retries)...[/cyan]\n"
            f"[dim white]Please ensure car battery is charged and power switch is ON.[/dim white]",
            title="[bold red](!) HARDWARE LINK LOST (!)[/bold red]",
            border_style="red",
            box=box.DOUBLE
        )
        console.print(alert)
        self.voice.speak("Car disconnected. Attempting to reconnect. Please turn car power on.")

        reconnected = await self.driver.reconnect(max_attempts=max_attempts, delay_seconds=3.0)

        if reconnected:
            success_panel = Panel(
                f"[bold green]Re-synchronized with BLE Car [{self.mac_address}][/bold green]\n"
                f"[dim]140ms GATT streaming loop restored.[/dim]",
                title="[bold green](*) LINK RESTORED (*)[/bold green]",
                border_style="green",
                box=box.ROUNDED
            )
            console.print(success_panel)
            self.voice.speak("Car reconnected and ready.")
            self.is_reconnecting = False
            return True
        else:
            fail_panel = Panel(
                f"[bold yellow]Could not reconnect to car [{self.mac_address}] after {max_attempts} attempts.[/bold yellow]\n"
                f"[dim]Returning to Master Menu. Select [B] to scan for devices or test in simulation mode.[/dim]",
                title="[bold yellow](!) LINK TIMED OUT (!)[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED
            )
            console.print(fail_panel)
            self.voice.speak("Reconnection timed out. Returning to main menu.")
            self._mode_running = False
            self.is_reconnecting = False
            return False

    def _handle_voice_intent(self, intent: dict):
        """Processes voice commands when in Voice Mode."""
        action = intent.get("action")
        raw_speech = intent.get("raw", "")
        reply = ""

        if action == "stop":
            reply = "Stopping car."
            self.voice.speak(reply)
            self.driver.stop()
            self._empty_queue()
        elif action == "lights":
            val = intent.get("value", True)
            self.driver.set_lights(val)
            reply = f"Headlights {'on' if val else 'off'}."
            self.voice.speak(reply)
        elif action == "toggle_lights":
            state = self.driver.toggle_lights()
            reply = f"Headlights {'on' if state else 'off'}."
            self.voice.speak(reply)
        elif action == "spray":
            val = intent.get("value", True)
            self.driver.set_spray(val)
            reply = f"Exhaust spray {'on' if val else 'off'}."
            self.voice.speak(reply)
        elif action in ["forward", "backward", "left", "right"]:
            dur = intent.get("duration", 1.0)
            steer = intent.get("steer")
            reply = f"Moving {action} for {dur:.1f}s."
            self.voice.speak(reply)
            self._action_queue.put_nowait({"action": action, "duration": dur, "steer": steer})
        elif action == "unknown":
            reply = "Command not recognized. Standing by."

        console.print(render_voice_event(speech_text=raw_speech, intent=intent, reply_text=reply))

    def _empty_queue(self):
        while not self._action_queue.empty():
            try:
                self._action_queue.get_nowait()
            except Exception:
                break

    # =========================================================================
    # FAST REAL-TIME REFLEX SUBSYSTEM (Low-level safety guard)
    # =========================================================================
    def check_safety_reflexes(self, sensory: Dict[str, Any]) -> bool:
        """
        Fast 20Hz reflex check. If an obstacle is right in front of the car,
        triggers immediate auto-brake without waiting for LLM thinking time.
        """
        if sensory.get("obstacle_center"):
            if not self.emergency_brake_active:
                logger.warning("[SAFETY REFLEX] Immediate Obstacle Ahead! Auto-Braking.")
                self.driver.stop()
                self.emergency_brake_active = True
                self.ai_state = "EMERGENCY_BRAKE"
            return True
        else:
            self.emergency_brake_active = False
            return False

    # =========================================================================
    # MODE 1: MANUAL KEYBOARD CONTROL
    # =========================================================================
    async def run_manual_mode(self):
        p = Panel(
            "[bold white]Controls:[/bold white]\n"
            "  [bold cyan][W / UP][/bold cyan] Forward      [bold cyan][S / DOWN][/bold cyan] Reverse\n"
            "  [bold cyan][A / LEFT][/bold cyan] Steer Left   [bold cyan][D / RIGHT][/bold cyan] Steer Right\n"
            "  [bold yellow][L][/bold yellow] Headlights       [bold yellow][K][/bold yellow] Exhaust Spray\n"
            "  [bold green][R][/bold green] Reset Origin     [bold red][SPACE][/bold red] Emergency Brake\n"
            "  [bold magenta][ESC][/bold magenta] Return to Master Menu",
            title="[bold cyan]>> MODE 1: MANUAL KEYBOARD DRIVING <<[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(p)

        self.voice.speak("Manual keyboard mode active.")
        self._mode_running = True
        pressed_keys = set()
        last_move_time = time.time()
        active_action = None

        def on_press(key):
            nonlocal active_action, last_move_time
            if key in pressed_keys:
                return  # Ignore duplicate OS key-repeat events while key is held down

            pressed_keys.add(key)
            active_action = self._update_keyboard_state(pressed_keys)
            last_move_time = time.time()

            if key == keyboard.KeyCode.from_char('l'):
                state = self.driver.toggle_lights()
                console.print(f"  [yellow]Headlights:[/yellow] {'[green]ON[/green]' if state else '[red]OFF[/red]'}")
            elif key == keyboard.KeyCode.from_char('k'):
                state = self.driver.toggle_spray()
                console.print(f"  [cyan]Exhaust Spray:[/cyan] {'[green]ON[/green]' if state else '[red]OFF[/red]'}")
            elif key == keyboard.KeyCode.from_char('r'):
                self.odometry.reset_origin()
                console.print("  [bold green][SPATIAL TELEMETRY RESET TO (0.0m, 0.0m, 0 deg)][/bold green]")
            elif key == keyboard.Key.space:
                self.driver.stop()
                console.print("  [bold red][EMERGENCY BRAKE ENGAGED][/bold red]")

        def on_release(key):
            nonlocal active_action, last_move_time
            if active_action:
                dt = time.time() - last_move_time
                act, steer = active_action
                self.odometry.update_from_action(act, dt, steer)

            if key in pressed_keys:
                pressed_keys.remove(key)
            if key == keyboard.Key.esc:
                self._mode_running = False
                return False
            active_action = self._update_keyboard_state(pressed_keys)
            last_move_time = time.time()

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        while self._mode_running and not self.should_exit:
            if self.is_reconnecting:
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0.1)

        listener.stop()
        self.driver.stop()
        console.print(f"\n[dim]Exited Manual Mode. Final POS: ({self.odometry.x:+.2f}m, {self.odometry.y:+.2f}m)[/dim]")

    def _update_keyboard_state(self, keys):
        fwd = keyboard.Key.up in keys or keyboard.KeyCode.from_char('w') in keys
        bwd = keyboard.Key.down in keys or keyboard.KeyCode.from_char('s') in keys
        left = keyboard.Key.left in keys or keyboard.KeyCode.from_char('a') in keys
        right = keyboard.Key.right in keys or keyboard.KeyCode.from_char('d') in keys

        if fwd:
            steer = "left" if left else "right" if right else None
            self.driver.move_forward(steer)
            return ("forward", steer)
        elif bwd:
            steer = "left" if left else "right" if right else None
            self.driver.move_backward(steer)
            return ("backward", steer)
        elif left:
            self.driver.steer_left_only()
            return ("left", None)
        elif right:
            self.driver.steer_right_only()
            return ("right", None)
        else:
            self.driver.stop()
            return None

    # =========================================================================
    # MODE 2: VOICE NAVIGATION
    # =========================================================================
    async def run_voice_mode(self):
        p = Panel(
            "[bold white]Speak commands clearly into your microphone in ANY language:[/bold white]\n"
            "  - '[cyan]Move forward for 2 seconds[/cyan]' / '[cyan]Gadi aage le jao[/cyan]'\n"
            "  - '[cyan]Turn left[/cyan]' / '[cyan]Turn right[/cyan]'\n"
            "  - '[cyan]Turn on headlights[/cyan]' / '[cyan]Batti jalao[/cyan]'\n"
            "  - '[cyan]Stop[/cyan]' / '[cyan]Ruk jao[/cyan]'\n"
            "  [dim]Press Ctrl+C to return to menu.[/dim]",
            title="[bold cyan]>> MODE 2: VOICE COGNITIVE NAVIGATION <<[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(p)

        self.voice.speak("Voice navigation active. Listening for commands.")
        self.voice.start_listening()
        self._mode_running = True

        try:
            while self._mode_running and not self.should_exit:
                if self.is_reconnecting:
                    await asyncio.sleep(0.5)
                    continue
                if not self._action_queue.empty():
                    act = await self._action_queue.get()
                    cmd = act["action"]
                    dur = act.get("duration", 1.0)
                    steer = act.get("steer")
                    await self.driver.pulse(cmd, dur, steer)
                    self.odometry.update_from_action(cmd, dur, steer)
                await asyncio.sleep(0.05)
        finally:
            self.voice.stop_listening()
            self.driver.stop()

    # =========================================================================
    # MODE 3: VISUAL TARGET TRACKING ("Follow-Me")
    # =========================================================================
    async def run_track_mode(self):
        console.print(Panel(
            "[bold white]OpenCV target tracking active.[/bold white]\n"
            "Point camera at a target or marker. Car will follow automatically.\n"
            "[dim]Press [Q] or [ESC] on camera window to return.[/dim]",
            title="[bold green]>> MODE 3: VISUAL TARGET TRACKING <<[/bold green]",
            border_style="green",
            box=box.ROUNDED
        ))

        if not self.vision.start():
            console.print("[bold red]Failed to initialize camera.[/bold red]")
            return

        self.voice.speak("Visual tracking active. Searching for target.")
        self._mode_running = True

        while self._mode_running and not self.should_exit:
            if self.is_reconnecting:
                await asyncio.sleep(0.5)
                continue

            frame = self.vision.read_frame()
            if frame is not None and CV2_AVAILABLE:
                self.vision.process_frame(frame)
                annotated = self.vision.get_annotated_frame(frame)

                car_track = self.green_tracker.process_frame(frame)
                if car_track.get("car_found"):
                    self.odometry.x = car_track["x_meters"]
                    self.odometry.y = car_track["y_meters"]
                    self.odometry.theta = car_track["heading_degrees"]
                    annotated = self.green_tracker.draw_hud(annotated)

                if annotated is not None:
                    cv2.putText(annotated, f"{APP_NAME} | TARGET TRACK", (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                    cv2.imshow("Gear Console HUD", annotated)
                    if (cv2.waitKey(1) & 0xFF) in [27, ord('q')]:
                        break

            analysis = self.vision.last_analysis
            action_desc = "stop"
            if analysis.get("target_detected"):
                cx = analysis.get("target_center_x", 0.0)
                area = analysis.get("target_area_ratio", 0.0)
                if area > 0.18:
                    self.driver.stop()
                    action_desc = "target reached (hold)"
                elif cx < -0.25:
                    self.driver.move_forward(steer="left")
                    self.odometry.update_from_action("forward", 0.12, "left")
                    action_desc = "tracking left"
                    await asyncio.sleep(0.12)
                elif cx > 0.25:
                    self.driver.move_forward(steer="right")
                    self.odometry.update_from_action("forward", 0.12, "right")
                    action_desc = "tracking right"
                    await asyncio.sleep(0.12)
                else:
                    self.driver.move_forward()
                    self.odometry.update_from_action("forward", 0.12, None)
                    action_desc = "pursuing forward"
                    await asyncio.sleep(0.12)
            else:
                self.driver.stop()
                action_desc = "searching"
            await asyncio.sleep(0.05)

        self.driver.stop()
        self.vision.stop()

    # =========================================================================
    # MODE 4: AUTONOMOUS ROOM EXPLORER
    # =========================================================================
    async def run_explore_mode(self):
        curr_room = self.room_mapper.get_current_room(self.odometry.x, self.odometry.y)
        console.print(render_explorer_card(
            room=curr_room,
            pos_x=self.odometry.x,
            pos_y=self.odometry.y,
            state="CRUISING",
            obstacle_info="PATH CLEAR"
        ))

        if not self.vision.start():
            console.print("[bold red]Failed to initialize camera.[/bold red]")
            return

        self.voice.speak("Autonomous exploration active.")
        self._mode_running = True

        while self._mode_running and not self.should_exit:
            if self.is_reconnecting:
                await asyncio.sleep(0.5)
                continue

            frame = self.vision.read_frame()
            if frame is not None and CV2_AVAILABLE:
                self.vision.process_frame(frame)
                annotated = self.vision.get_annotated_frame(frame)

                car_track = self.green_tracker.process_frame(frame)
                if car_track.get("car_found"):
                    self.odometry.x = car_track["x_meters"]
                    self.odometry.y = car_track["y_meters"]
                    self.odometry.theta = car_track["heading_degrees"]
                    annotated = self.green_tracker.draw_hud(annotated)

                if annotated is not None:
                    curr_room = self.room_mapper.get_current_room(self.odometry.x, self.odometry.y)
                    cv2.putText(annotated, f"ROOM: {curr_room} | AUTONOMOUS EXPLORER", (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                    cv2.imshow("Gear Console HUD", annotated)
                    if (cv2.waitKey(1) & 0xFF) in [27, ord('q')]:
                        break

            analysis = self.vision.last_analysis
            if analysis.get("obstacle_center"):
                self.driver.move_backward()
                self.odometry.update_from_action("backward", 0.5, None)
                await asyncio.sleep(0.5)
                self.driver.steer_left_only()
                self.odometry.update_from_action("left", 0.6, None)
                await asyncio.sleep(0.6)
                self.driver.stop()
            elif analysis.get("obstacle_left"):
                self.driver.move_forward(steer="right")
                self.odometry.update_from_action("forward", 0.2, "right")
                await asyncio.sleep(0.2)
            elif analysis.get("obstacle_right"):
                self.driver.move_forward(steer="left")
                self.odometry.update_from_action("forward", 0.2, "left")
                await asyncio.sleep(0.2)
            else:
                self.driver.move_forward()
                self.odometry.update_from_action("forward", 0.2, None)
                await asyncio.sleep(0.2)

            await asyncio.sleep(0.05)

        self.driver.stop()
        self.vision.stop()

    # =========================================================================
    # MODE 5: HIGH-RELIABILITY EMBODIED LLM COGNITIVE BRAIN
    # =========================================================================
    async def run_llm_mode(self):
        cockpit = render_cockpit_panel(
            mode_name="EMBODIED LLM BRAIN",
            room=self.room_mapper.get_current_room(self.odometry.x, self.odometry.y),
            pos_x=self.odometry.x,
            pos_y=self.odometry.y,
            heading=self.odometry.theta,
            dist=self.odometry.total_distance_traveled,
            state="READY"
        )
        console.print(cockpit)

        if not self.brain.api_key:
            console.print("\n[bold yellow][!] No Gemini API Key found. Paste your key:[/bold yellow]")
            entered_key = await asyncio.to_thread(input, ">> Gemini API Key: ")
            entered_key = entered_key.strip()
            if entered_key:
                self.brain.set_api_key(entered_key)

        info_panel = Panel(
            "[bold white]Active Consciousness Subsystems:[/bold white]\n"
            "  [bold green][+][/bold green] Real-time 2D Localization (Green Cross + Kinematics)\n"
            "  [bold green][+][/bold green] Multi-Room Scanned Floorplan Navigation\n"
            "  [bold green][+][/bold green] 20Hz Emergency Auto-Brake Reflex Guard\n"
            "  [bold green][+][/bold green] Multilingual Voice Dialogue (Hindi, English, Hinglish, etc.)\n\n"
            "[bold cyan]Input:[/bold cyan] Speak into your mic OR type your mission goal below.\n"
            "[dim]Type 'menu' or 'exit' to return to master menu.[/dim]",
            title=f"[bold cyan]>> {APP_NAME} v{APP_VERSION} -- MULTIMODAL VLM COGNITION <<[/bold cyan]",
            border_style="#7000ff",
            box=box.ROUNDED
        )
        console.print(info_panel)

        if not self.vision.start():
            console.print("[bold red]Failed to initialize camera stream.[/bold red]")
            return

        voice_goal_queue = asyncio.Queue()

        def _mode5_voice_handler(intent):
            raw = intent.get("raw", "").strip()
            if raw and len(raw) > 1:
                logger.info(f"[GEAR CONSOLE SPOKEN GOAL] \"{raw}\"")
                voice_goal_queue.put_nowait(raw)

        prev_voice_callback = self.voice.callback
        self.voice.callback = _mode5_voice_handler
        self.voice.start_listening()

        self.voice.speak(f"{APP_NAME} online. I have taken physical control of the car body.")
        self._mode_running = True
        self.ai_state = "READY"

        async def _execute_embodied_goal(goal_text: str):
            self.ai_state = "PLANNING"
            curr_room = self.room_mapper.get_current_room(self.odometry.x, self.odometry.y)

            # Render updated cockpit status
            console.print(render_cockpit_panel(
                mode_name="EMBODIED LLM BRAIN",
                room=curr_room,
                pos_x=self.odometry.x,
                pos_y=self.odometry.y,
                heading=self.odometry.theta,
                dist=self.odometry.total_distance_traveled,
                state="PLANNING"
            ))

            console.print(f"\n[bold cyan]>> Active Mission Goal:[/bold cyan] [bold white]'{goal_text}'[/bold white]")
            console.print(f"[dim]{self.room_mapper.get_ascii_floorplan(self.odometry.x, self.odometry.y)}[/dim]")

            # 1. Capture snapshot & telemetry
            frame = self.vision.read_frame()
            if frame is not None:
                self.vision.process_frame(frame)
                car_track = self.green_tracker.process_frame(frame)
                if car_track.get("car_found"):
                    self.odometry.x = car_track["x_meters"]
                    self.odometry.y = car_track["y_meters"]
                    self.odometry.theta = car_track["heading_degrees"]

            img_b64 = self.vision.capture_base64_jpeg()
            sensory = self.vision.last_analysis
            spatial_tel = self.odometry.get_telemetry()
            spatial_map = self.odometry.get_ascii_spatial_map(grid_size=9)
            floorplan_tel = self.room_mapper.get_navigation_telemetry(self.odometry.x, self.odometry.y)
            floorplan_map = self.room_mapper.get_ascii_floorplan(self.odometry.x, self.odometry.y)

            # 2. Plan with Gemini VLM in background worker
            with console.status(f"[bold cyan]Gemini VLM reasoning as car body...[/bold cyan]", spinner="dots"):
                plan = await asyncio.to_thread(
                    self.brain.plan_next_move,
                    user_goal=goal_text,
                    sensory_state=sensory,
                    spatial_telemetry=spatial_tel,
                    spatial_map_ascii=spatial_map,
                    floorplan_telemetry=floorplan_tel,
                    floorplan_ascii=floorplan_map,
                    image_base64=img_b64
                )

            # 3. Format Thought & Reply
            thought = plan.get("thought", "")
            speech = plan.get("speech", "")
            actions = plan.get("actions", [])

            thought_panel = Panel(
                f"[bold cyan]Internal Reasoning:[/bold cyan]\n[white]{thought}[/white]\n\n"
                f"[bold green]Spoken Voice Reply:[/bold green]\n[bold yellow]\"{speech}\"[/bold yellow]\n\n"
                f"[bold magenta]Planned Motor Actions:[/bold magenta] [dim]{actions}[/dim]",
                title="[bold #7000ff]>> AI COGNITIVE DECISION <<[/bold #7000ff]",
                border_style="#7000ff",
                box=box.ROUNDED
            )
            console.print(thought_panel)

            if speech:
                self.voice.speak(speech)

            # 4. Safe sequential motor execution with 20Hz reflex check
            self.ai_state = "EXECUTING"
            for act in actions:
                if self.is_reconnecting or self.should_exit:
                    break

                cmd = act.get("action")
                dur = act.get("duration", 0.8)
                steer = act.get("steer")

                if cmd == "forward":
                    self.driver.move_forward(steer)
                    t_start = time.time()
                    while (time.time() - t_start) < dur:
                        if self.is_reconnecting or self.should_exit:
                            break
                        rf_frame = self.vision.read_frame()
                        if rf_frame is not None:
                            self.vision.process_frame(rf_frame)
                            if self.check_safety_reflexes(self.vision.last_analysis):
                                break
                        await asyncio.sleep(0.05)
                    self.driver.stop()
                    self.odometry.update_from_action("forward", dur, steer)

                elif cmd == "backward":
                    self.driver.move_backward(steer)
                    await asyncio.sleep(dur)
                    self.driver.stop()
                    self.odometry.update_from_action("backward", dur, steer)

                elif cmd == "left":
                    self.driver.steer_left_only()
                    await asyncio.sleep(dur)
                    self.driver.stop()
                    self.odometry.update_from_action("left", dur, None)

                elif cmd == "right":
                    self.driver.steer_right_only()
                    await asyncio.sleep(dur)
                    self.driver.stop()
                    self.odometry.update_from_action("right", dur, None)

                elif cmd == "stop":
                    self.driver.stop()

                elif cmd == "lights":
                    self.driver.set_lights(act.get("state", True))

                elif cmd == "spray":
                    self.driver.set_spray(act.get("state", True))

                await asyncio.sleep(0.1)

            self.ai_state = "READY"

        # Terminal background input loop
        async def _terminal_input_loop():
            while self._mode_running and not self.should_exit:
                try:
                    text = await asyncio.to_thread(input, "Enter Goal (or speak): ")
                    text = text.strip()
                    if text.lower() in ["exit", "quit", "menu", "q"]:
                        self._mode_running = False
                        break
                    if text:
                        await voice_goal_queue.put(text)
                except Exception:
                    break

        input_task = asyncio.create_task(_terminal_input_loop())

        while self._mode_running and not self.should_exit:
            if self.is_reconnecting:
                await asyncio.sleep(0.5)
                continue

            frame = self.vision.read_frame()
            if frame is not None and CV2_AVAILABLE:
                self.vision.process_frame(frame)
                annotated = self.vision.get_annotated_frame(frame)

                # Optical Green Cross Car Tracking
                car_track = self.green_tracker.process_frame(frame)
                if car_track.get("car_found"):
                    self.odometry.x = car_track["x_meters"]
                    self.odometry.y = car_track["y_meters"]
                    self.odometry.theta = car_track["heading_degrees"]
                    annotated = self.green_tracker.draw_hud(annotated)

                if annotated is not None:
                    curr_room = self.room_mapper.get_current_room(self.odometry.x, self.odometry.y)
                    # Sleek HUD Banner
                    cv2.rectangle(annotated, (10, 10), (450, 80), (20, 20, 20), -1)
                    cv2.putText(annotated, f"{APP_NAME} | [{self.ai_state}]", (20, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    cv2.putText(annotated, f"ROOM: {curr_room} | POS: ({self.odometry.x:+.2f}m, {self.odometry.y:+.2f}m) HDG: {self.odometry.theta:.0f}deg",
                                (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

                    cv2.imshow("Gear Console HUD", annotated)
                    if (cv2.waitKey(1) & 0xFF) in [27, ord('q')]:
                        self._mode_running = False
                        break

            if not voice_goal_queue.empty():
                goal_item = await voice_goal_queue.get()
                await _execute_embodied_goal(goal_item)

            await asyncio.sleep(0.05)

        input_task.cancel()
        self.voice.stop_listening()
        self.voice.callback = prev_voice_callback
        self.driver.stop()
        self.vision.stop()
        console.print(f"\n[dim]Exited {APP_NAME} Mode 5.[/dim]")

    # =========================================================================
    # MASTER MENU LOOP
    # =========================================================================
    async def run(self):
        boot_sequence()

        # 1. Attempt initial BLE connection (4.0s)
        connected = await self.driver.connect(timeout=4.0)
        if connected:
            console.print(f"[bold green](*) {APP_NAME} synchronized with BLE Car [{self.mac_address}][/bold green]")
            self.voice.speak(f"{APP_NAME} connected and ready.")
        else:
            console.print(f"[bold yellow][!] Car [{self.mac_address}] not detected at launch.[/bold yellow]")
            console.print("[dim]Starting in Standby / Simulation mode. Use option [B] to scan for devices anytime.[/dim]\n")
            self.voice.speak(f"{APP_NAME} ready in standby mode.")

        while not self.should_exit:
            cam_label = "Laptop WebCam (0)" if self.camera_source == 0 else f"Phone/Stream ({self.camera_source})"
            menu_panel = render_menu(cam_source=cam_label, is_connected=self.driver.is_connected, mac=self.mac_address)
            console.print(menu_panel)

            try:
                choice = await asyncio.to_thread(input, "\n>> Select Option (1-5, S, C, or Q): ")
                choice = choice.strip().upper()
            except (EOFError, KeyboardInterrupt):
                break

            if self.should_exit:
                break

            if choice == "1":
                await self.run_manual_mode()
            elif choice == "2":
                await self.run_voice_mode()
            elif choice == "3":
                await self.run_track_mode()
            elif choice == "4":
                await self.run_explore_mode()
            elif choice == "5":
                await self.run_llm_mode()
            elif choice == "S":
                scanner = AIRoomScanner(camera_source=self.camera_source, gemini_api_key=self.gemini_api_key)
                console.print("\n[bold cyan]Starting AI Visual Room Walkthrough Scan...[/bold cyan]")
                map_result = await asyncio.to_thread(scanner.start_interactive_scan)
                if map_result and "rooms" in map_result:
                    self.room_mapper.load_map()
                    console.print(render_scan_results(map_result.get("rooms", [])))
                    console.print("[bold green][SUCCESS] New home map loaded into RoomMapper![/bold green]")
                elif map_result:
                    self.room_mapper.load_map()
                    console.print("[bold green][SUCCESS] New home map loaded into RoomMapper![/bold green]")
            elif choice == "B":
                console.print("\n[bold cyan]Scanning for nearby Bluetooth devices (5s)...[/bold cyan]")
                devices = await scan_for_ble_cars(timeout=5.0)
                if devices:
                    table = Table(title="[bold cyan]Discovered Bluetooth Devices[/bold cyan]", box=box.ROUNDED)
                    table.add_column("Num", style="bold magenta", width=5)
                    table.add_column("Device Name", style="bold white")
                    table.add_column("MAC Address", style="bold green")
                    table.add_column("RSSI", style="dim cyan")
                    for idx, d in enumerate(devices, 1):
                        table.add_row(f"[{idx}]", d["name"], d["mac"], str(d["rssi"]))
                    console.print(table)
                    sel = await asyncio.to_thread(input, "\n>> Select Device Number (or enter custom MAC): ")
                    sel = sel.strip()
                    chosen_mac = None
                    if sel.isdigit() and 1 <= int(sel) <= len(devices):
                        chosen_mac = devices[int(sel) - 1]["mac"]
                    elif ":" in sel and len(sel) == 17:
                        chosen_mac = sel

                    if chosen_mac:
                        console.print(f"[cyan]Testing and connecting to selected device [{chosen_mac}]...[/cyan]")
                        await self.driver.disconnect()
                        self.driver.mac_address = chosen_mac
                        ok = await self.driver.connect(timeout=6.0)
                        if ok:
                            save_mac_address(chosen_mac)
                            self.mac_address = chosen_mac
                            console.print(f"[bold green][SUCCESS] Verified & synchronized with RC Car [{chosen_mac}]![/bold green]")
                            self.voice.speak(f"{APP_NAME} connected to car.")
                        else:
                            console.print(f"\n[bold red][!] INCOMPATIBLE DEVICE: [{chosen_mac}][/bold red]")
                            console.print("[yellow]This device is not an RC Car (Missing GATT characteristic 0xFFF2).[/yellow]")
                            console.print("[dim]Bluetooth speakers, TVs, and earbuds cannot be controlled. Reverting.[/dim]\n")
                            self.driver.mac_address = self.mac_address
                else:
                    console.print("[bold yellow]No BLE devices found nearby. Ensure car power is ON.[/bold yellow]")
            elif choice == "C":
                p = Panel(
                    "[bold cyan][0][/bold cyan] Built-in Laptop Webcam (Index 0)\n"
                    "[bold cyan][1][/bold cyan] External USB Camera (Index 1)\n"
                    "[bold cyan][2][/bold cyan] Mobile Phone IP Camera via WiFi (e.g. http://192.168.31.239:8080/video)",
                    title="[bold yellow]-- CAMERA SOURCE CONFIGURATION --[/bold yellow]",
                    border_style="yellow",
                    box=box.ROUNDED
                )
                console.print(p)
                sub = await asyncio.to_thread(input, ">> Enter choice (0, 1, or URL): ")
                sub = sub.strip()
                if sub in ["0", "1"]:
                    self.camera_source = int(sub)
                elif sub.startswith("http"):
                    sub = sub.rstrip("/")
                    if not any(sub.endswith(ep) for ep in ["/video", "/videofeed", "/mjpeg", "/stream", ".mjpg"]):
                        sub = sub + "/video"
                    self.camera_source = sub
                self.vision.camera_source = self.camera_source
                console.print(f"[bold green][SUCCESS] Camera source set to: {self.camera_source}[/bold green]")
            elif choice in ["Q", "QUIT", "EXIT"]:
                console.print(f"[bold cyan]Exiting {APP_NAME}...[/bold cyan]")
                break
            else:
                console.print(f"[bold red]Invalid selection: '{choice}'. Please choose 1, 2, 3, 4, 5, S, C, or Q.[/bold red]")

        self.driver.stop()
        await self.driver.disconnect()
        console.print(f"[bold magenta]{APP_NAME} disconnected cleanly. Goodbye![/bold magenta]")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}: Autonomous RC Car AI Autopilot")
    parser.add_argument("--mac", type=str, default=DEFAULT_MAC, help="Target Car Bluetooth MAC Address")
    parser.add_argument("--cam", type=str, default="0", help="Camera index or Phone Stream URL")
    parser.add_argument("--key", type=str, default=None, help="Gemini API Key (optional)")
    args = parser.parse_args()

    engine = GearConsoleEngine(mac_address=args.mac, camera_source=args.cam, gemini_api_key=args.key)
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        logger.info("Terminated by user.")
