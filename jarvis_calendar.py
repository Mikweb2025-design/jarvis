#!/usr/bin/env python3
"""jarvis_calendar.py — Apple Calendar via SQLite diretto (v7.0 — veloce, locale-safe)"""
import sqlite3, os, subprocess
from datetime import datetime, timedelta

_MAC_EPOCH = datetime(2001, 1, 1, 0, 0, 0).timestamp()

def _db():
    path = os.path.expanduser("~/Library/Group Containers/group.com.apple.calendar/Calendar.sqlitedb")
    if not os.path.exists(path):
        return None
    # Prova connessione diretta (timeout breve)
    for _ in range(2):
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            conn.execute("SELECT 1")
            return conn
        except Exception:
            import time as _t; _t.sleep(0.3)
    # Fallback: copia via shutil.copyfile (evita lock di dataaccessd/Calendar.app)
    import tempfile, shutil, time as _t
    for _ in range(2):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlitedb", delete=False)
        tmp.close()
        try:
            shutil.copyfile(path, tmp.name)
            conn = sqlite3.connect(tmp.name, timeout=3)
            conn.execute("SELECT 1")
            return conn
        except Exception:
            _t.sleep(0.3)
            try: os.unlink(tmp.name)
            except: pass
    return None

def _today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() - _MAC_EPOCH
    end = datetime(now.year, now.month, now.day, 23, 59, 59).timestamp() - _MAC_EPOCH
    return start, end

def _apple_script_events(days=0):
    """Fallback: ottiene eventi via AppleScript. Non avvia Calendar se non è già aperto."""
    running = subprocess.run(["pgrep", "-x", "Calendar"], capture_output=True, timeout=5)
    if running.returncode != 0:
        return None
    script = '''
    with timeout of 15 seconds
        tell application "Calendar"
            set calEvents to every event of every calendar whose start date is greater than or equal to (current date)
            set output to ""
            repeat with cal in calEvents
                repeat with ev in cal
                    set summary to summary of ev
                    set startDate to start date of ev
                    set endDate to end date of ev
                    set calName to title of container of ev
                    set isAllDay to allday event of ev
                    if isAllDay then
                        set output to output & summary & "|TUTTO_IL_GIORNO|" & calName & return
                    else
                        set output to output & summary & "|" & (time string of startDate) & "-" & (time string of endDate) & "|" & calName & return
                    end if
                end repeat
            end repeat
            return output
        end tell
    end timeout
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
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

def _query_rows(sql, params):
    """Prova copia del DB + sqlite3, poi subprocess sqlite3 CLI."""
    conn = _db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.close()
            return rows
        except:
            try: conn.close()
            except: pass
    return None

def _format_rows(rows, days=0):
    if rows is None:
        return None
    if not rows:
        return "📅 Nessun evento oggi" if days == 0 else f"📅 Nessun evento nei prossimi {days} giorni"
    lines = []
    prev_day = None
    for r in rows:
        title = r[0] or "(nessun titolo)"
        start_dt = datetime.fromtimestamp(r[1] + _MAC_EPOCH)
        end_dt = datetime.fromtimestamp(r[2] + _MAC_EPOCH) if r[2] else None
        cal = r[4] or ""
        if days > 0:
            day_label = start_dt.strftime("%A %d/%m") if prev_day != start_dt.day else ""
            prev_day = start_dt.day
            prefix = f"\n── {day_label} ──\n" if day_label else ""
        else:
            prefix = ""
        if r[3]:
            lines.append(f"{prefix}📅 {title} — tutto il giorno [{cal}]")
        else:
            end_str = end_dt.strftime('%H:%M') if end_dt else "?"
            lines.append(f"{prefix}📅 {title} — {start_dt.strftime('%H:%M')}-{end_str} [{cal}]")
    return "\n".join(lines)

def get_today_events():
    start, end = _today_range()
    sql = """
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
    """
    rows = _query_rows(sql, (start, end))
    if rows is not None:
        return _format_rows(rows, days=0)
    fallback = _apple_script_events(days=0)
    if fallback:
        return fallback
    return "⚠ Database Calendario non accessibile"

def get_upcoming_events(days=7):
    now = datetime.now()
    start = datetime(now.year, now.month, now.day, 0, 0, 0).timestamp() - _MAC_EPOCH
    end = start + (days * 86400)
    sql = """
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
    """
    rows = _query_rows(sql, (start, end))
    if rows is not None:
        return _format_rows(rows, days=days)
    fallback = _apple_script_events(days=days)
    if fallback:
        return fallback
    return f"⚠ Database Calendario non accessibile"

def get_calendars():
    rows = _query_rows("SELECT title FROM Calendar ORDER BY title", ())
    if rows is not None and rows:
        titles = [r[0] for r in rows if r[0]]
        return f"📅 Calendari: {', '.join(titles)}" if titles else "Nessun calendario trovato"
    running = subprocess.run(["pgrep", "-x", "Calendar"], capture_output=True, timeout=5)
    if running.returncode == 0:
        try:
            r = subprocess.run(["osascript", "-e",
                'with timeout of 15 seconds\ntell application "Calendar" to get title of every calendar\nend timeout'],
                capture_output=True, text=True, timeout=20)
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
    with timeout of 15 seconds
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
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
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
