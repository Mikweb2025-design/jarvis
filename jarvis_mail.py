#!/usr/bin/env python3
"""jarvis_mail.py — posta via database SQLite di Mail.app (fix Gmail + tutte le mailbox)"""
import sqlite3, os, glob
from pathlib import Path

def _mail_db():
    mail_dirs = glob.glob(os.path.expanduser("~/Library/Mail/V*/MailData"))
    for d in mail_dirs:
        db = os.path.join(d, "Envelope Index")
        if os.path.exists(db):
            return db
    return None

def _query(sql):
    db_path = _mail_db()
    if not db_path:
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        return None

def get_unread_count():
    """Conta email non lette in tutte le mailbox (esclusi Trash e Spam)"""
    rows = _query("""
        SELECT SUM(sub.cnt) FROM (
            SELECT m.mailbox, COUNT(*) as cnt
            FROM messages m
            JOIN mailboxes mb ON m.mailbox = mb.rowid
            WHERE m.read = 0
              AND mb.url NOT LIKE '%Trash%'
              AND mb.url NOT LIKE '%Spam%'
              AND mb.url NOT LIKE '%Papierkorb%'
            GROUP BY m.mailbox
        ) sub
    """)
    if rows is None:
        return "⚠ Database Mail non trovato"
    count = rows[0][0] or 0
    account_count = _query("""
        SELECT COUNT(DISTINCT substr(mb.url, 1, instr(substr(mb.url, 8), '/')+7))
        FROM messages m
        JOIN mailboxes mb ON m.mailbox = mb.rowid
        WHERE m.read = 0
          AND mb.url NOT LIKE '%Trash%'
          AND mb.url NOT LIKE '%Spam%'
          AND mb.url NOT LIKE '%Papierkorb%'
    """)
    accounts = account_count[0][0] if account_count else 0
    if count == 0:
        return "📬 Nessuna email non letta"
    acc_s = f" su {accounts} account" if accounts > 1 else ""
    return f"📬 Hai {count} email non lette{acc_s}"

def get_recent_emails(limit=10):
    """Legge le email non lette recenti da tutte le mailbox escluse Trash/Spam
    Returns: lista di dict o stringa di errore"""
    rows = _query(f"""
        SELECT DISTINCT a.address, sub.subject, m.date_received, mb.url
        FROM messages m
        JOIN mailboxes mb ON m.mailbox = mb.rowid
        LEFT JOIN recipients r ON r.message = m.ROWID AND r.type = 0
        LEFT JOIN addresses a ON r.address = a.ROWID
        LEFT JOIN subjects sub ON m.subject = sub.ROWID
        WHERE m.read = 0
          AND mb.url NOT LIKE '%Trash%'
          AND mb.url NOT LIKE '%Spam%'
          AND mb.url NOT LIKE '%Papierkorb%'
        ORDER BY m.date_received DESC
        LIMIT {limit}
    """)
    if rows is None:
        return "⚠ Database Mail non trovato"
    if not rows:
        return "📬 Nessuna email non letta"
    items = []
    for row in rows:
        sender = row[0] or "Sconosciuto"
        subject = row[1] or "(nessun oggetto)"
        date = row[2] or ""
        mailbox = row[3] or ""
        label = ""
        if "/Alle%20Nachrichten" in mailbox or "/Alle Nachrichten" in mailbox:
            label = " [Tutte]"
        elif "/INBOX" in mailbox:
            label = ""
        items.append({"sender": sender, "subject": subject, "date": str(date)[:19], "label": label})
    return items[:limit]

def parse_unread_count(text):
    """Estrae il numero numerico di email non lette dal testo"""
    import re
    m = re.search(r'(\d+)', text)
    return int(m.group(1)) if m else 0

def _format_time_natural(date_str):
    """Converte timestamp in pronuncia naturale italiana (es. '14:30' -> 'alle 14 e 30')"""
    import re
    if not date_str: return ""
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', str(date_str))
    if not m: return date_str
    h, mi = int(m.group(4)), int(m.group(5))
    day, month = int(m.group(3)), int(m.group(2))
    mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
            "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    mese_str = mesi[month] if 1 <= month <= 12 else str(month)
    ora_str = f"{h}" if mi == 0 else f"{h} e {mi}"
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    from datetime import datetime
    try:
        dt = datetime(int(m.group(1)), month, day)
        giorno = giorni[dt.weekday()]
    except:
        giorno = ""
    return f"{giorno} {day} {mese_str} alle {ora_str}"

def format_emails_for_speech(emails):
    """Formatta le email per lettura vocale naturale"""
    if isinstance(emails, str):
        return emails
    if not emails:
        return "Nessuna email da leggere"
    parts = []
    emails_list = emails if isinstance(emails, list) else []
    for i, e in enumerate(emails_list, 1):
        if isinstance(e, dict):
            sender = e.get('sender', 'mittente sconosciuto')
            subject = e.get('subject', 'nessun oggetto')
            date = _format_time_natural(e.get('date', ''))
            parts.append(f"Email numero {i}. Da {sender}. Oggetto: {subject}. Ricevuta {date}.")
        elif isinstance(e, str):
            parts.append(f"Email numero {i}: {e}")
    if not parts:
        return str(emails)
    intro = f"Trova {len(parts)} email non lette. " if len(parts) > 1 else "Una email non letta. "
    return intro + " ".join(parts)

def search_emails(query, limit=10):
    q = query.replace("'", "''")
    rows = _query(f"""
        SELECT DISTINCT a.address, sub.subject, m.date_received, mb.url
        FROM messages m
        JOIN mailboxes mb ON m.mailbox = mb.rowid
        LEFT JOIN recipients r ON r.message = m.ROWID AND r.type = 0
        LEFT JOIN addresses a ON r.address = a.ROWID
        LEFT JOIN subjects sub ON m.subject = sub.ROWID
        WHERE (sub.subject LIKE '%{q}%' OR a.address LIKE '%{q}%')
          AND mb.url NOT LIKE '%Trash%'
          AND mb.url NOT LIKE '%Spam%'
          AND mb.url NOT LIKE '%Papierkorb%'
        ORDER BY m.date_received DESC
        LIMIT {limit}
    """)
    if rows is None:
        return "⚠ Database Mail non trovato"
    if not rows:
        return f"📧 Nessuna email per: '{query}'"
    items = []
    for row in rows:
        sender = row[0] or "Sconosciuto"
        subject = row[1] or "(nessun oggetto)"
        date = row[2] or ""
        items.append({"sender": sender, "subject": subject, "date": str(date)[:19]})
    return "\n".join(f"📧 Da: {e['sender']}\n   Oggetto: {e['subject']}\n   Data: {e['date']}" for e in items[:limit])
