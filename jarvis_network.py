#!/usr/bin/env python3
"""jarvis_network.py — Network Diagnostics v1.0
Ispirato a deepakrakshit/jarvis
Speed test, public IP, DNS, connectivity probes, ping"""
import subprocess, json, socket, urllib.request, time
from pathlib import Path

def _run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip()

def public_ip():
    """Ottiene IP pubblico da più servizi fallback"""
    services = [
        "https://api.ipify.org?format=json",
        "https://api.myip.com",
        "https://httpbin.org/ip",
    ]
    for url in services:
        try:
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read().decode())
            if "ip" in data:
                return data["ip"]
        except Exception:
            continue
    return "Non disponibile"

def ip_geolocation(ip=None):
    """Geolocalizzazione IP approssimativa"""
    target = ip or public_ip()
    try:
        resp = urllib.request.urlopen(f"http://ip-api.com/json/{target}", timeout=5)
        data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            return f"{data.get('city', '?')}, {data.get('regionName', '?')}, {data.get('country', '?')} (ISP: {data.get('isp', '?')})"
        return "Geolocalizzazione non disponibile"
    except Exception:
        return "Geolocalizzazione non disponibile"

def ping_test(host="8.8.8.8", count=3):
    """Test ping verso un host"""
    out = _run(f"ping -c {count} -W 3 {host} 2>/dev/null")
    if not out:
        return f"Ping verso {host}: fallito"
    # Estrai statistiche
    stats = _run(f"ping -c {count} -W 3 {host} 2>&1 | tail -1")
    times = _run(f"ping -c {count} -W 3 {host} 2>&1 | grep 'bytes from' | head -{count}")
    return f"Ping {host}:\n{times}\n{stats}"

def dns_lookup(domain="google.com"):
    """Lookup DNS per un dominio"""
    try:
        result = socket.getaddrinfo(domain, 80)
        ips = list(set(r[4][0] for r in result))
        return f"DNS {domain}: {', '.join(ips)}"
    except Exception as e:
        return f"DNS lookup fallito: {e}"

def port_check(host, port, timeout=3):
    """Verifica se una porta è aperta"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return f"Porta {host}:{port} è {'APERTA' if result == 0 else 'CHIUSA'}"
    except Exception as e:
        return f"Port check fallito: {e}"

def bandwidth_speedtest():
    """Speed test veloce (stima download piccolo file)"""
    import time as _time
    test_urls = [
        "http://speedtest.tele2.net/1MB.zip",
        "https://proof.ovh.net/files/1Mb.dat",
    ]
    for url in test_urls:
        try:
            t0 = _time.time()
            resp = urllib.request.urlopen(url, timeout=15)
            data = resp.read()
            elapsed = _time.time() - t0
            size_mb = len(data) / (1024 * 1024)
            speed_mbps = round((size_mb * 8) / elapsed, 1)
            return f"Velocità download: ~{speed_mbps} Mbps ({size_mb:.1f} MB in {elapsed:.1f}s)"
        except Exception:
            continue
    return "Speed test non disponibile (nessun server raggiungibile)"

def connectivity_summary():
    """Report completo connettività"""
    ip = public_ip()
    geo = ip_geolocation(ip)
    dns = dns_lookup()
    ping = ping_test(count=2)
    return f"""🌐 Connessione Internet
   IP Pubblico: {ip}
   Localizzazione: {geo}
   
{dns}

{ping}"""
