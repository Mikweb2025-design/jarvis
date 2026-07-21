#!/usr/bin/env node
/* baileys-bridge.js — WhatsApp via Baileys (no Chrome, WebSocket puro) */
const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const http = require('http');
const path = require('path');
const fs = require('fs');
const qrcode = require('qrcode-terminal');

const JARVIS_WEBHOOK = 'http://127.0.0.1:9999/api/whatsapp/webhook';
const BAIL_SEND_PORT = 2787;
const DATA_DIR = path.join(__dirname, 'data', 'baileys-auth');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

let _sock = null;

function startSendServer() {
  const srv = http.createServer((req, res) => {
    if (req.method !== 'POST' || req.url !== '/api/send') {
      res.writeHead(404); res.end('Not found'); return;
    }
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const { chatId, text } = JSON.parse(body);
        if (!chatId || !text) { res.writeHead(400); res.end(JSON.stringify({ error: 'chatId and text required' })); return; }
        if (!_sock) { res.writeHead(503); res.end(JSON.stringify({ error: 'Socket not ready' })); return; }
        await _sock.sendMessage(chatId, { text });
        console.log(`[Baileys] >> ${chatId}: ${text.slice(0, 80)}`);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (e) {
        console.log('[Baileys] Send error:', e.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
  });
  srv.listen(BAIL_SEND_PORT, '127.0.0.1', () => console.log(`[Baileys] Send server on :${BAIL_SEND_PORT}`));
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(DATA_DIR);

  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });
  _sock = sock;

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      qrcode.generate(qr, { small: true });
      console.log('\n[Baileys] SCANSIONA IL QR SOPRA\n');
    }
    if (connection === 'open') {
      console.log('[Baileys] Connesso come:', sock.user?.name || sock.user?.id);
    }
    if (connection === 'close') {
      const statusCode = (lastDisconnect?.error instanceof Boom) ? lastDisconnect.error.output.statusCode : 0;
      console.log('[Baileys] Disconnesso, codice:', statusCode);
      if (statusCode === DisconnectReason.loggedOut) {
        console.log('[Baileys] Sessione scaduta, cancella data/baileys-auth e riprova');
        process.exit(1);
      }
      setTimeout(start, 3000);
    }
  });

  sock.ev.on('messages.upsert', async ({ messages }) => {
    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      if (!msg.message?.conversation && !msg.message?.extendedTextMessage?.text) continue;

      const text = msg.message.conversation || msg.message.extendedTextMessage.text;
      const chatId = msg.key.remoteJid;
      const sender = msg.key.participant || chatId;
      const isGroup = chatId.endsWith('@g.us');

      console.log(`[Baileys] << ${chatId}: ${text.slice(0, 80)}`);

      const payload = JSON.stringify({
        event: 'message.received',
        data: {
          id: msg.key.id,
          from: sender,
          to: sock.user?.id || '',
          chatId: chatId,
          body: text,
          type: 'chat',
          timestamp: Math.floor(msg.messageTimestamp || Date.now() / 1000),
          fromMe: false,
          isGroup,
        },
      });

      try {
        const req = http.request(JARVIS_WEBHOOK, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) },
        }, res => {
          let body = '';
          res.on('data', c => body += c);
          res.on('end', () => {
            if (res.statusCode === 200) console.log(`[Baileys] >> JARVIS OK`);
            else console.log(`[Baileys] >> JARVIS errore ${res.statusCode}`);
          });
        });
        req.on('error', e => console.log('[Baileys] HTTP errore:', e.message));
        req.write(payload);
        req.end();
      } catch (e) {
        console.log('[Baileys] Errore:', e.message);
      }
    }
  });
}

startSendServer();
start();
console.log('[Baileys] Avvio...');
