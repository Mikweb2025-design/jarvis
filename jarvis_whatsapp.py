#!/usr/bin/env python3
"""jarvis_whatsapp.py — WhatsApp Desktop automation via AppleScript UI scripting"""
import subprocess, os, time, json, re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CONTACTS_FILE = DATA_DIR / "whatsapp_contacts.json"

# Default contacts
DEFAULT_CONTACTS = {
    "marco": "Marco",
    "dori": "Dori",
    "daniele": "Daniele",
}

def _load_contacts():
    if CONTACTS_FILE.exists():
        try:
            return {**DEFAULT_CONTACTS, **json.loads(CONTACTS_FILE.read_text())}
        except:
            pass
    return dict(DEFAULT_CONTACTS)

def _save_contacts(contacts):
    CONTACTS_FILE.parent.mkdir(exist_ok=True)
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.stderr.strip()

def is_running():
    """Check if WhatsApp Desktop is running"""
    r = subprocess.run(["pgrep", "-x", "WhatsApp"], capture_output=True)
    return r.returncode == 0

def launch():
    """Launch WhatsApp Desktop"""
    subprocess.run(["open", "-a", "WhatsApp"], capture_output=True)
    time.sleep(5)
    return is_running()

def send_message(contact_name, message):
    """Send a WhatsApp message via UI scripting (AppleScript)"""
    contacts = _load_contacts()
    # Find contact by alias or full name
    target = contacts.get(contact_name.lower().strip(), contact_name)

    if not is_running():
        if not launch():
            return f"⚠ WhatsApp non in esecuzione e impossibile avviarlo"

    # AppleScript to find and click on the contact, type message, and send
    script = f'''
    tell application "WhatsApp"
        activate
    end tell
    delay 1.5

    tell application "System Events"
        tell process "WhatsApp"
            -- Click search field (Cmd+Shift+F or Cmd+F depending on version)
            keystroke "f" using {{command down}}
            delay 0.8

            -- Type contact name
            keystroke "{target}"
            delay 1.5

            -- Press Down to select first result, then Enter to open chat
            key code 125
            delay 0.5
            key code 36
            delay 1.0

            -- Now type the message
            keystroke "{message}"
            delay 0.5

            -- Send (Enter)
            key code 36
        end tell
    end tell
    return "Messaggio inviato a {target}"
    '''
    stdout, stderr = _osa(script)
    if stderr and "error" in stderr.lower():
        # Fallback: try different method (new chat)
        fallback = f'''
        tell application "WhatsApp"
            activate
        end tell
        delay 2
        tell application "System Events"
            tell process "WhatsApp"
                -- New chat
                keystroke "n" using {{command down}}
                delay 1
                -- Type contact
                keystroke "{target}"
                delay 2
                -- Select
                key code 125
                delay 0.5
                key code 36
                delay 1.5
                -- Type message
                keystroke "{message}"
                delay 1
                -- Send
                key code 36
            end tell
        end tell
        return "Messaggio inviato a {target} (metodo alternativo)"
        '''
        stdout2, stderr2 = _osa(fallback)
        if stderr2 and "error" in stderr2.lower():
            return f"⚠ Errore WhatsApp: {stderr2[:200]}"
        return stdout2
    return stdout or f"✅ Messaggio inviato a {target}"

def send_file(contact_name, file_path):
    """Send a file via WhatsApp"""
    contacts = _load_contacts()
    target = contacts.get(contact_name.lower().strip(), contact_name)
    abs_path = str(Path(file_path).resolve())

    if not os.path.exists(abs_path):
        return f"⚠ File non trovato: {abs_path}"

    if not is_running():
        if not launch():
            return "⚠ WhatsApp non in esecuzione"

    script = f'''
    tell application "WhatsApp"
        activate
    end tell
    delay 1.5
    tell application "System Events"
        tell process "WhatsApp"
            -- Open chat with contact
            keystroke "f" using {{command down}}
            delay 0.8
            keystroke "{target}"
            delay 1.5
            key code 125
            delay 0.5
            key code 36
            delay 1.5

            -- Click attach button (paperclip)
            keystroke "t" using {{command down}}
            delay 0.5

            -- Type file path in the dialog
            keystroke "{abs_path}"
            delay 0.5
            key code 36
            delay 2

            -- Send
            key code 36
        end tell
    end tell
    return "File inviato a {target}"
    '''
    stdout, stderr = _osa(script)
    if stderr and "error" in stderr.lower():
        return f"⚠ Errore invio file: {stderr[:200]}"
    return stdout or f"✅ File inviato a {target}"

def add_contact(alias, full_name):
    """Add or update a contact alias"""
    contacts = _load_contacts()
    contacts[alias.lower().strip()] = full_name
    _save_contacts(contacts)
    return f"✅ Contatto '{alias}' → '{full_name}' salvato"

def list_contacts():
    """List all saved contacts"""
    contacts = _load_contacts()
    return "\n".join(f"  • {alias}: {name}" for alias, name in contacts.items())

def status():
    """Check WhatsApp status"""
    running = is_running()
    contacts = _load_contacts()
    return {
        "running": running,
        "contacts": len(contacts),
        "contact_list": contacts,
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "send":
        print(send_message(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Test da JARVIS"))
    elif len(sys.argv) >= 2 and sys.argv[1] == "status":
        s = status()
        print(f"Running: {s['running']}")
        print(f"Contacts ({s['contacts']}):")
        for alias, name in s['contact_list'].items():
            print(f"  {alias} → {name}")
    else:
        print("Usage: python3 jarvis_whatsapp.py send <contact> <message>")
        print("       python3 jarvis_whatsapp.py status")
