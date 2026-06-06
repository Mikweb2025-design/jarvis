#!/usr/bin/env python3
"""jarvis_calendar.py — Apple Calendar via SQLite diretto (v7.0 — veloce, locale-safe)"""
import sqlite3, os, subprocess
from datetime import datetime, timedelta

_MAC_EPOCH = datetime(2001, 1, 1, 0, 0, 0).timestamp()

def _db():
    path = os.path.expanduser("~/Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb")
    if not os.path.exists(path):
        return None
    for attempt in range(3):
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            return conn
        except Exception as e:
            if attempt < 2:
                import time as _t
                _t.sleep(0.5)
            else:
                return None

def _today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() - _MAC_EPOCH
    end = datetime(now.year, now.month, now.day, 23, 59, 59).timestamp() - _MAC_EPOCH
    return start, end

def _apple_script_events(days=0):
    """Fallback: ottiene eventi via AppleScript (affidabile, permission-safe)."""
    script = '''
    set output to ""
    tell application "Calendar"
        set calEvents to every event of every calendar whose start date is greater than or equal to (current date)
        repeat with cal in calEvents
            repeat with ev in cal
                set summary to summary of ev
                set startDate to start date of ev
                set endDate to end date of ev
                set calName to title of container of ev
                set isAllDay to allday event of ev
                if isAllDay then
                    set output to output & summary & "|TUTTO_IL_GIORNO|" & calName & "\\n"
                else
                    set output to output & summary & "|" & (time string of startDate) & "-" & (time string of endDate) & "|" & calName & "\\n"
                end if
            end repeat
        end repeat
    end tell
    return output
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        lines = []
        for line in r.stdout.strip().split("\n"):
            parts = line.split("|", 2)
            if len(parts) < 2:
                continue
            title, when, cal = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
            if when == "TUTTO_IL_GIORNO":
                lines.append(f"📅 {title} — tutto il giorno [{cal}]")
            else:
                lines.append(f"📅 {title} — {when} [{cal}]")
        if days == 0:
            return "\n".join(lines) if lines else "📅 Nessun evento oggi"
        return "\n".join(lines) if lines else f"📅 Nessun evento nei prossimi giorni"
    except:
        return None

def get_today_events():
    conn = _db()
    if conn:
        try:
            cur = conn.cursor()
            start, end = _today_range()
            cur.execute("""
                SELECT ci.summary, ci.start_date, ci.end_date, ci.all_day, c.title
                FROM CalendarItem ci
                JOIN Calendar c ON ci.calendar_id = c.ROWID
                WHERE ci.start_date >= ? AND ci.start_date < ?
                  AND ci.hidden = 0 AND ci.status != 2
                  AND c.title NOT LIKE '%Geburtstag%'
                  AND c.title NOT LIKE '%birthday%'
                  AND c.title NOT LIKE '%Feiertag%'
                  AND c.title NOT LIKE '%Siri%'
                ORDER BY ci.start_date ASC
            """, (start, end))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return "📅 Nessun evento oggi"
            lines = []
            for r in rows:
                title = r[0] or "(nessun titolo)"
                start_dt = datetime.fromtimestamp(r[1] + _MAC_EPOCH)
                cal = r[4] or ""
                if r[3]:
                    lines.append(f"📅 {title} — tutto il giorno [{cal}]")
                else:
                    end_dt = datetime.fromtimestamp(r[2] + _MAC_EPOCH)
                    lines.append(f"📅 {title} — {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')} [{cal}]")
            return "\n".join(lines)
        except:
            try: conn.close()
            except: pass
    fallback = _apple_script_events(days=0)
    if fallback:
        return fallback
    return "⚠ Database Calendario non accessibile"

def get_upcoming_events(days=7):
    conn = _db()
    if conn:
        try:
            cur = conn.cursor()
            now = datetime.now()
            start = datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() - _MAC_EPOCH
            end = start + (days * 86400)
            cur.execute("""
                SELECT ci.summary, ci.start_date, ci.end_date, ci.all_day, c.title
                FROM CalendarItem ci
                JOIN Calendar c ON ci.calendar_id = c.ROWID
                WHERE ci.start_date >= ? AND ci.start_date < ?
                  AND ci.hidden = 0 AND ci.status != 2
                  AND c.title NOT LIKE '%Geburtstag%'
                  AND c.title NOT LIKE '%birthday%'
                  AND c.title NOT LIKE '%Feiertag%'
                  AND c.title NOT LIKE '%Siri%'
                ORDER BY ci.start_date ASC
                LIMIT 30
            """, (start, end))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return f"📅 Nessun evento nei prossimi {days} giorni"
            lines = []
            prev_day = None
            for r in rows:
                title = r[0] or "(nessun titolo)"
                start_dt = datetime.fromtimestamp(r[1] + _MAC_EPOCH)
                cal = r[4] or ""
                day_label = start_dt.strftime("%A %d/%m") if prev_day != start_dt.day else ""
                prev_day = start_dt.day
                prefix = f"\n── {day_label} ──\n" if day_label else ""
                if r[3]:
                    lines.append(f"{prefix}📅 {title} — tutto il giorno [{cal}]")
                else:
                    end_dt = datetime.fromtimestamp(r[2] + _MAC_EPOCH)
                    lines.append(f"{prefix}📅 {title} — {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')} [{cal}]")
            return "\n".join(lines)
        except:
            try: conn.close()
            except: pass
    fallback = _apple_script_events(days=days)
    if fallback:
        return fallback
    return f"⚠ Database Calendario non accessibile"

def get_calendars():
    conn = _db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT title FROM Calendar ORDER BY title")
            rows = [r[0] for r in cur.fetchall()]
            conn.close()
            if rows:
                return f"📅 Calendari: {', '.join(rows)}"
        except:
            try: conn.close()
            except: pass
    try:
        r = subprocess.run(["osascript", "-e",
            'tell application "Calendar" to get title of every calendar'],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            cals = [c.strip() for c in r.stdout.strip().split(",") if c.strip()]
            return f"📅 Calendari: {', '.join(cals)}" if cals else "Nessun calendario trovato"
    except:
        pass
    return "⚠ Database Calendario non accessibile"

def create_event(title, start_date_str="", duration_minutes=60, calendar_name="", notes=""):
    """Crea evento usando AppleScript con date locale-safe"""
    from datetime import timedelta
    if start_date_str:
        try:
            sd = datetime.fromisoformat(start_date_str)
        except:
            sd = datetime.now() + timedelta(hours=1)
    else:
        sd = datetime.now() + timedelta(hours=1)
    cal_clause = f'calendar "{calendar_name}"' if calendar_name else "default calendar"
    notes_clause = f', description:"{notes}"' if notes else ""
    script = f'''
    with timeout of 10 seconds
        set baseDate to (current date)
        set hours of baseDate to {sd.hour}
        set minutes of baseDate to {sd.minute}
        set seconds of baseDate to 0
        set endDate to baseDate + ({duration_minutes} * minutes)
        tell application "Calendar"
            tell {cal_clause}
                make new event at end with properties {{summary:"{title}", start date:baseDate, end date:endDate{notes_clause}}}
            end tell
        end tell
    end timeout
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=12)
        if r.returncode != 0:
            return f"⚠ Errore creazione evento: {r.stderr.strip()}"
        return f"✅ Evento creato: '{title}' il {sd.strftime('%d/%m alle %H:%M')}"
    except subprocess.TimeoutExpired:
        return f"⚠ Timeout creazione evento '{title}'"
    except Exception as e:
        return f"⚠ Errore: {e}"

def open_calendar_app():
    subprocess.run(["open", "-a", "Calendar"], capture_output=True)
    return "✅ Calendario aperto"
