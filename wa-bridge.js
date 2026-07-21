#!/usr/bin/env node
/* wa-bridge.js — WhatsApp bridge con finestra visibile, riceve msg e li gira a JARVIS */
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');
const fs = require('fs');

const JARVIS_WEBHOOK = 'http://127.0.0.1:9999/api/whatsapp/webhook';
const DATA_DIR = path.join(__dirname, 'data', 'wa-bridge');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: DATA_DIR }),
  puppeteer: {
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--no-first-run',
      '--no-zygote',
      '--disable-gpu',
    ],
  },
});

client.on('qr', qr => {
  qrcode.generate(qr, { small: true });
  console.log('\n[WA-Bridge] SCANSIONA IL QR CODE SOPRA CON WHATSAPP\n');
});

client.on('authenticated', () => console.log('[WA-Bridge] Autenticato!'));
client.on('ready', () => console.log('[WA-Bridge] Pronto!'));
client.on('disconnected', r => console.log('[WA-Bridge] Disconnesso:', r));

client.on('message', async msg => {
  if (msg.fromMe) return; // ignora messaggi inviati da noi

  const payload = {
    event: 'message.received',
    data: {
      id: msg.id._serialized,
      from: msg.from,
      to: msg.to,
      chatId: msg.from,
      body: msg.body,
      type: msg.type,
      timestamp: msg.timestamp,
      fromMe: msg.fromMe,
      isGroup: msg.from.endsWith('@g.us'),
    },
  };

  console.log(`[WA-Bridge] << ${msg.from}: ${msg.body.slice(0, 80)}`);

  try {
    const postData = JSON.stringify(payload);
    const req = http.request(JARVIS_WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(postData) },
    }, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        if (res.statusCode === 200) console.log(`[WA-Bridge] >> Inviato a JARVIS (${res.statusCode})`);
        else console.log(`[WA-Bridge] >> Errore JARVIS: ${res.statusCode} ${body.slice(0,100)}`);
      });
    });
    req.on('error', e => console.log('[WA-Bridge] Errore HTTP:', e.message));
    req.write(postData);
    req.end();
  } catch (e) {
    console.log('[WA-Bridge] Errore:', e.message);
  }
});

client.initialize();
console.log('[WA-Bridge] Avvio...');
