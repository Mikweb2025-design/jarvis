#!/usr/bin/env python3
"""jarvis_calendar.py — Apple Calendar via SQLite diretto (v7.0 — veloce, locale-safe)"""
import sqlite3, os, subprocess
from datetime import datetime, timedelta

_MAC_EPOCH = datetime(2001, 1, 1, 0, 0, 0).timestamp()

def _db():
    path = os.path.expanduser("~/Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb")
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        return conn
    except:
        return None

def _today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() - _MAC_EPOCH
    end = datetime(now.year, now.month, now.day, 23, 59, 59).timestamp() - _MAC_EPOCH
    return start, end

def get_today_events():
    conn = _db()
    if not conn:
        return "⚠ Database Calendario non accessibile"
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
        if r[3]:  # all_day
            lines.append(f"📅 {title} — tutto il giorno [{cal}]")
        else:
            end_dt = datetime.fromtimestamp(r[2] + _MAC_EPOCH)
            lines.append(f"📅 {title} — {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')} [{cal}]")
    return "\n".join(lines)

def get_upcoming_events(days=7):
    conn = _db()
    if not conn:
        return "⚠ Database Calendario non accessibile"
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

def get_calendars():
    conn = _db()
    if not conn:
        return "⚠ Database Calendario non accessibile"
    cur = conn.cursor()
    cur.execute("SELECT title FROM Calendar ORDER BY title")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return f"📅 Calendari: {', '.join(rows)}" if rows else "Nessun calendario trovato"

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
