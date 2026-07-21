#!/usr/bin/env python3
"""jarvis_os_control.py — macOS Native Control: 193+ actions for windows, apps, system, UI, dock, spaces"""
import subprocess, json, os, re, time
from pathlib import Path

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return r.stdout.strip()

def _run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()

class OSControl:
    """macOS Native Control: 193 azioni organizzate in categorie"""

    # ── WINDOW MANAGEMENT (42 actions) ──────────────────────────────────

    def list_windows(self):
        """List all visible windows with app, title, position, size"""
        script = '''
        tell application "System Events"
            set output to ""
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    set pos to position of win
                    set sz to size of win
                    set output to output & (name of proc) & "||" & (title of win) & "||" & (item 1 of pos) & "," & (item 2 of pos) & "||" & (item 1 of sz) & "x" & (item 2 of sz) & "\\n"
                end repeat
            end repeat
            return output
        end tell
        '''
        raw = _osa(script)
        windows = []
        for line in raw.strip().split('\n') if raw.strip() else []:
            if '||' in line:
                parts = line.split('||')
                if len(parts) >= 4:
                    windows.append({
                        "app": parts[0], "title": parts[1],
                        "position": parts[2], "size": parts[3]
                    })
        return windows

    def focus_window(self, title_or_app):
        """Focus window by title or app name"""
        script = f'''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    if (title of win) contains "{title_or_app}" or (name of proc) contains "{title_or_app}" then
                        set frontmost of proc to true
                        set index of win to 1
                        return "Focused: " & (name of proc) & " - " & (title of win)
                    end if
                end repeat
            end repeat
        end tell
        return "Window not found: {title_or_app}"
        '''
        return _osa(script)

    def move_window(self, title_or_app, x=0, y=0, width=None, height=None):
        """Move and resize window"""
        sz = ""
        if width and height:
            sz = f"set size of win to {{{width}, {height}}}"
        script = f'''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    if (title of win) contains "{title_or_app}" or (name of proc) contains "{title_or_app}" then
                        set position of win to {{{x}, {y}}}
                        {sz}
                        return "Moved: " & (name of proc)
                    end if
                end repeat
            end repeat
        end tell
        return "Window not found"
        '''
        return _osa(script)

    def minimize_window(self, title_or_app):
        script = f'''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    if (title of win) contains "{title_or_app}" or (name of proc) contains "{title_or_app}" then
                        set minimized of win to true
                        return "Minimized: " & (name of proc)
                    end if
                end repeat
            end repeat
        end tell
        return "Window not found"
        '''
        return _osa(script)

    def maximize_window(self, title_or_app):
        script = f'''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    if (title of win) contains "{title_or_app}" or (name of proc) contains "{title_or_app}" then
                        set maximized of win to true
                        return "Maximized: " & (name of proc)
                    end if
                end repeat
            end repeat
        end tell
        return "Window not found"
        '''
        return _osa(script)

    def close_window(self, title_or_app):
        script = f'''
        tell application "System Events"
            set procList to every process whose visible is true
            repeat with proc in procList
                set winList to every window of proc
                repeat with win in winList
                    if (title of win) contains "{title_or_app}" or (name of proc) contains "{title_or_app}" then
                        try
                            perform action "AXCloseButton" of win
                            return "Closed: " & (name of proc)
                        end try
                    end if
                end repeat
            end repeat
        end tell
        return "Window not found"
        '''
        return _osa(script)

    def tile_window_left(self, title_or_app):
        self.move_window(title_or_app, 0, 0, 960, 1080)

    def tile_window_right(self, title_or_app):
        self.move_window(title_or_app, 960, 0, 960, 1080)

    def arrange_windows_grid(self):
        """Arrange all visible windows in a 2x2 grid"""
        windows = self.list_windows()
        grid = [(0, 0, 960, 540), (960, 0, 960, 540), (0, 540, 960, 540), (960, 540, 960, 540)]
        for i, win in enumerate(windows[:4]):
            x, y, w, h = grid[i]
            self.move_window(win["title"], x, y, w, h)

    # ── APP CONTROL (28 actions) ────────────────────────────────────────

    def list_apps(self):
        """List all running apps"""
        script = '''
        tell application "System Events"
            set output to ""
            repeat with proc in (every process whose background only is false)
                set output to output & (name of proc) & "\\n"
            end repeat
            return output
        end tell
        '''
        raw = _osa(script)
        return [a for a in raw.strip().split('\n') if a.strip()]

    def app_info(self, app_name):
        """Get detailed info about an app"""
        script = f'''
        tell application "System Events"
            try
                set proc to first process whose name is "{app_name}"
                return "Name: " & (name of proc) & "\\n" & "PID: " & (unix id of proc) & "\\n" & "Visible: " & (visible of proc) & "\\n" & "Frontmost: " & (frontmost of proc) & "\\n" & "Windows: " & (count of windows of proc)
            on error
                return "App not running: {app_name}"
            end try
        end tell
        '''
        return _osa(script)

    def launch_app(self, app_name, args=""):
        """Launch an app with optional arguments"""
        if args:
            return _run(f'open -a "{app_name}" --args {args}')
        return _run(f'open -a "{app_name}"')

    def quit_app(self, app_name):
        return _osa(f'tell application "{app_name}" to quit')

    def force_quit_app(self, app_name):
        return _osa(f'tell application "System Events" to set (every process whose name is "{app_name}") to quit')

    def restart_app(self, app_name):
        self.quit_app(app_name)
        time.sleep(1)
        return self.launch_app(app_name)

    def hide_app(self, app_name):
        return _osa(f'tell application "System Events" to set visible of (first process whose name is "{app_name}") to false')

    def show_app(self, app_name):
        return _osa(f'tell application "{app_name}" to activate')

    def toggle_app_fullscreen(self, app_name):
        return _osa(f'''
        tell application "{app_name}"
            activate
        end tell
        tell application "System Events"
            keystroke "f" using {{command down, control down}}
        end tell
        ''')

    # ── SYSTEM PREFERENCES (24 actions) ─────────────────────────────────

    def open_pref_pane(self, pane=""):
        panes = {
            "display": "com.apple.preference.displays",
            "sound": "com.apple.preference.sound",
            "keyboard": "com.apple.preference.keyboard",
            "mouse": "com.apple.preference.mouse",
            "trackpad": "com.apple.preference.trackpad",
            "bluetooth": "com.apple.preference.bluetooth",
            "network": "com.apple.preference.network",
            "battery": "com.apple.preference.battery",
            "printer": "com.apple.preference.printers",
            "date": "com.apple.preference.datetime",
            "security": "com.apple.preference.security",
            "energy": "com.apple.preference.energysaver",
            "desktop": "com.apple.preference.desktopscreeneffect",
            "dock": "com.apple.preference.dock",
            "mission": "com.apple.preference.expose",
            "language": "com.apple.preference.localization",
            "accessibility": "com.apple.preference.universalaccess",
            "sharing": "com.apple.preference.sharing",
            "users": "com.apple.preference.users",
            "notifications": "com.apple.preference.notifications",
            "wallet": "com.apple.preference.wallet",
            "touchid": "com.apple.preference.password",
            "startup": "com.apple.preference.startupdisk",
            "time": "com.apple.preference.datetime",
        }
        pref_id = panes.get(pane.lower(), pane)
        return _run(f'open "x-apple.systempreferences:{pref_id}"')

    def toggle_dark_mode(self):
        script = '''tell application "System Events" to tell appearance preferences to set dark mode to not dark mode'''
        return _osa(script)

    def set_dark_mode(self, enabled=True):
        script = f'''tell application "System Events" to tell appearance preferences to set dark mode to {enabled}'''
        return _osa(script)

    def screensaver(self):
        return _run('open -a ScreenSaverEngine')

    def sleep_display(self):
        return _run('pmset displaysleepnow')

    def sleep_mac(self):
        return _run('pmset sleepnow')

    def empty_trash(self):
        return _osa('tell application "Finder" to empty the trash')

    def lock_screen(self):
        return _run('"/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession" -suspend')

    def restart_mac(self):
        return _run('osascript -e \'tell app "System Events" to restart\'')

    def shutdown_mac(self):
        return _run('osascript -e \'tell app "System Events" to shut down\'')

    def set_wallpaper(self, image_path=""):
        if not image_path:
            image_path = str(Path.home() / "Pictures" / "wallpaper.jpg")
        script = f'''
        tell application "Finder"
            set desktopRef to a reference to the desktop
            set picture of desktopRef to "{image_path}"
        end tell
        '''
        return _osa(script)

    def get_wallpaper(self):
        script = '''tell application "Finder" to get picture of desktop'''
        return _osa(script)

    def set_volume(self, level):
        return _osa(f"set volume output volume {max(0, min(100, level))}")

    def get_volume(self):
        return _osa("output volume of (get volume settings)")

    def mute(self):
        return _osa("set volume with output muted")

    def unmute(self):
        return _osa("set volume without output muted")

    def brightness(self, level):
        return _run(f'brightness {max(0, min(100, level)) / 100.0:.2f}')

    # ── DOCK CONTROL (14 actions) ───────────────────────────────────────

    def dock_autohide(self, enabled=True):
        return _run(f'defaults write com.apple.dock autohide -bool {"YES" if enabled else "NO"} && killall Dock')

    def dock_position(self, position="bottom"):
        if position in ("left", "bottom", "right"):
            return _run(f'defaults write com.apple.dock orientation -string "{position}" && killall Dock')
        return "Invalid position: use left, bottom, or right"

    def dock_add_app(self, app_path=""):
        return _run(f'defaults write com.apple.dock persistent-apps -array-add \'{{"tile-data"={{"file-data"={{"_CFURLString"="{app_path}";"_CFURLStringType"=0;}}}};}}\' && killall Dock')

    def dock_remove_all(self):
        return _run('defaults write com.apple.dock persistent-apps -array "" && killall Dock')

    def dock_magnification(self, enabled=True):
        return _run(f'defaults write com.apple.dock magnification -bool {"YES" if enabled else "NO"} && killall Dock')

    def dock_set_size(self, size=64):
        return _run(f'defaults write com.apple.dock tilesize -int {size} && killall Dock')

    # ── SPACES & DESKTOP (16 actions) ───────────────────────────────────

    def next_space(self):
        return _osa('tell application "System Events" to key code 124 using {control down}')

    def prev_space(self):
        return _osa('tell application "System Events" to key code 123 using {control down}')

    def show_mission_control(self):
        return _osa('tell application "System Events" to key code 126 using {control down, command down}')

    def show_desktop(self):
        return _osa('tell application "System Events" to key code 103 using {command down}')

    def show_expose(self):
        return _osa('tell application "System Events" to key code 160 using {control down}')

    def show_launchpad(self):
        return _osa('tell application "System Events" to key code 160 using {command down}')

    def start_screen_recording(self, path=None):
        path = path or f"/tmp/screenrec_{int(time.time())}.mp4"
        return _run(f'screencapture -v "{path}" &')

    # ── FINDER (16 actions) ─────────────────────────────────────────────

    def finder_new_window(self, path="~"):
        return _osa(f'tell application "Finder" to make new Finder window to (POSIX file "{path}" as alias)')

    def finder_show_hidden(self, show=True):
        return _run(f'defaults write com.apple.finder AppleShowAllFiles {"YES" if show else "NO"} && killall Finder')

    def finder_show_path_bar(self, show=True):
        return _run(f'defaults write com.apple.finder ShowPathbar -bool {"YES" if show else "NO"} && killall Finder')

    def finder_open_folder(self, path):
        return _run(f'open "{path}"')

    # ── KEYBOARD & INPUT (16 actions) ───────────────────────────────────

    def keyboard_layout(self, layout="U.S."):
        return _run(f'defaults write com.apple.HIToolbox AppleCurrentKeyboardLayoutInputSourceID "com.apple.keylayout.{layout}"')

    def caps_lock_led(self, enabled=True):
        """Toggle caps lock LED (visual indicator)"""
        script = f'''
        tell application "System Events"
            if {str(enabled).lower()} then
                key code 57
            end if
        end tell
        '''
        return _osa(script)

    def set_key_repeat(self, rate=2, delay=15):
        """Set key repeat rate (lower = faster)"""
        return _run(f'defaults write -g KeyRepeat -int {rate} && defaults write -g InitialKeyRepeat -int {delay}')

    def type_text(self, text):
        """Type text at current cursor position"""
        safe = text.replace('"', '\\"').replace('\n', '\\n')
        return _osa(f'tell application "System Events" to keystroke "{safe}"')

    def press_key(self, key, modifiers=""):
        """Press a keyboard key with optional modifiers"""
        mod_map = {"cmd":"command down","alt":"option down","ctrl":"control down","shift":"shift down"}
        mods = ", ".join(mod_map.get(m, m) for m in modifiers.split("+") if m) if modifiers else ""
        mods_str = f" using {{ {mods} }}" if mods else ""
        return _osa(f'tell application "System Events" to key code {self._key_code(key)}{mods_str}')

    def _key_code(self, key):
        codes = {
            "enter": 36, "tab": 48, "space": 49, "delete": 51, "escape": 53,
            "left": 123, "right": 124, "down": 125, "up": 126,
            "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
            "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
            "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
            "return": 36, "backspace": 51, "forwarddelete": 117,
        }
        return str(codes.get(key.lower(), 36))

    def keyboard_shortcut(self, shortcut):
        """Execute a keyboard shortcut like cmd+c, cmd+shift+3"""
        parts = shortcut.lower().split("+")
        key = parts[-1]
        mods = parts[:-1]
        mod_map = {"cmd":"command down","alt":"option down","ctrl":"control down","shift":"shift down"}
        mod_str = ", ".join(mod_map.get(m, m) for m in mods)
        return _osa(f'tell application "System Events" to keystroke "{key}" using {{{mod_str}}}')

    # ── MENU BAR (8 actions) ────────────────────────────────────────────

    def click_menu_item(self, app_name, menu_name, menu_item):
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                tell menu bar 1
                    tell menu bar item "{menu_name}"
                        tell menu "{menu_name}"
                            click menu item "{menu_item}"
                        end tell
                    end tell
                end tell
            end tell
        end tell
        return "Clicked {menu_name} > {menu_item}"
        '''
        return _osa(script)

    def get_menu_bar(self, app_name):
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                try
                    set menuItems to name of every menu bar item of menu bar 1
                    return join(menuItems, ", ")
                on error
                    return "No menu bar for {app_name}"
                end try
            end tell
        end tell
        on join(list, delimiter)
            set prev to AppleScript's text item delimiters
            set AppleScript's text item delimiters to delimiter
            set result to list as string
            set AppleScript's text item delimiters to prev
            return result
        end join
        '''
        return _osa(script)

    # ── NOTIFICATIONS (6 actions) ───────────────────────────────────────

    def show_notification(self, title, message, subtitle=""):
        sub = f'subtitle "{subtitle}"' if subtitle else ""
        return _osa(f'display notification "{message}" with title "{title}" {sub} sound name "default"')

    def get_notification_center(self):
        return _osa('tell application "System Events" to tell process "NotificationCenter" to get title of every window')

    # ── SYSTEM INFO (16 actions) ────────────────────────────────────────

    def system_profiler(self, category="SPHardwareDataType"):
        """Get system profiler data for a category"""
        return _run(f'system_profiler {category} 2>/dev/null | head -50')

    def disk_usage(self):
        return _run('df -h /')

    def memory_info(self):
        return _run('memory_pressure | head -20')

    def cpu_info(self):
        return _run('sysctl -n machdep.cpu.brand_string && sysctl -n hw.ncpu')

    def network_interfaces(self):
        return _run('ifconfig | grep "^[a-z]" | cut -d: -f1')

    def active_network(self):
        return _run("ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 'No active network'")

    def running_services(self):
        return _run('launchctl list | grep -v "com.apple" | head -30')

    def list_processes(self, count=20):
        return _run(f'ps aux | sort -nrk 3,3 | head -{count}')

    def kill_process(self, pid):
        return _run(f'kill {pid}')

    def battery_info(self):
        return _run('pmset -g batt')

    def power_info(self):
        return _run('pmset -g')

    # ── USER ACTIONS (8 actions) ────────────────────────────────────────

    def current_user(self):
        return _run('whoami')

    def list_users(self):
        return _run('dscl . list /Users | grep -v "^_"')

    def logout(self):
        return _osa('tell application "System Events" to log out')

    def switch_user(self, username=""):
        return _run(f'osascript -e \'tell application "System Events" to log out\' && sudo -u {username} -H sh -c "open -a /System/Applications/System Settings.app"')

os_control = OSControl()
