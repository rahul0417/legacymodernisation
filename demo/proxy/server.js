// Panasa Modernisation Cockpit — local demo proxy
// Streams Claude Discovery output as Server-Sent Events.
// The cockpit (index.html) calls GET /discovery and renders the stream.

import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Anthropic from '@anthropic-ai/sdk';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT || 3737);
const MODEL = process.env.MODEL || 'claude-sonnet-4-6';
const SOURCE_DIR = path.resolve(__dirname, process.env.SOURCE_DIR || '../source/dimensions');
const PROMPT_PATH = path.resolve(__dirname, process.env.PROMPT_PATH || './prompt-discovery.md');

if (!process.env.ANTHROPIC_API_KEY) {
  console.error('[fatal] ANTHROPIC_API_KEY missing. Copy .env.example to .env and fill it in.');
  process.exit(1);
}

const client = new Anthropic();
const app = express();
app.use(cors());

// Serve the demo directory (index.html, source/, etc.) so the cockpit
// can be opened at http://localhost:PORT/ and SSE is same-origin.
app.use(express.static(path.resolve(__dirname, '..')));

// Line filter — keep only well-formed cockpit lines.
// Anything else (preamble, code blocks, stray prose) is silently dropped.
const COCKPIT_LINE = /^\[DISCOVERY\] .{8,200}$/;
const DONE_SENTINEL = '[DISCOVERY:DONE]';

async function loadSource() {
  const files = [];
  async function walk(dir, rel = '') {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      const abs = path.join(dir, e.name);
      const r = path.join(rel, e.name);
      if (e.isDirectory()) await walk(abs, r);
      else if (/\.(php|inc)$/.test(e.name)) {
        const text = await fs.readFile(abs, 'utf8');
        if (text.trim().length > 30) files.push({ path: `dimensions/${r}`, text });
      }
    }
  }
  await walk(SOURCE_DIR);
  return files;
}

function buildUserMessage(promptTemplate, files) {
  const embedded = files.map(f =>
    `### ${f.path} (${f.text.split('\n').length} lines)\n\`\`\`php\n${f.text}\n\`\`\``
  ).join('\n\n');
  return promptTemplate.replace('{{SOURCE_FILES}}', embedded);
}

app.get('/health', (_req, res) => res.json({ ok: true, model: MODEL }));

app.get('/discovery', async (req, res) => {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders();

  const send = (event, data) => {
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  let aborted = false;
  req.on('close', () => { aborted = true; });

  try {
    const [promptTemplate, files] = await Promise.all([
      fs.readFile(PROMPT_PATH, 'utf8'),
      loadSource(),
    ]);
    send('start', { files: files.length, loc: files.reduce((n, f) => n + f.text.split('\n').length, 0) });

    const userMessage = buildUserMessage(promptTemplate, files);

    const stream = await client.messages.stream({
      model: MODEL,
      max_tokens: 4000,
      messages: [{ role: 'user', content: userMessage }],
    });

    // Buffer text deltas and emit one cockpit line at a time.
    let buffer = '';
    let jsonMode = false;
    let jsonBuffer = '';
    let lineCount = 0;

    stream.on('text', (delta) => {
      if (aborted) return;
      buffer += delta;
      let idx;
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).trimEnd();
        buffer = buffer.slice(idx + 1);

        if (jsonMode) {
          if (line.startsWith('```')) {
            // close json
            try {
              const payload = JSON.parse(jsonBuffer.trim());
              send('summary', payload);
            } catch (err) {
              send('warn', { msg: 'summary JSON parse failed', err: String(err) });
            }
            jsonMode = false;
            jsonBuffer = '';
          } else {
            jsonBuffer += line + '\n';
          }
          continue;
        }

        if (line.startsWith('```json')) {
          jsonMode = true;
          continue;
        }
        if (line === DONE_SENTINEL) {
          send('done', { lines: lineCount });
          continue;
        }
        if (COCKPIT_LINE.test(line)) {
          lineCount++;
          // strip the prefix for cleaner UI rendering
          send('line', { text: line.replace(/^\[DISCOVERY\]\s*/, '') });
        }
        // else: silently drop preamble / stray text
      }
    });

    stream.on('error', (err) => {
      if (aborted) return;
      send('error', { msg: String(err?.message || err) });
      res.end();
    });

    stream.on('end', () => {
      if (aborted) return;
      send('end', { lines: lineCount });
      res.end();
    });
  } catch (err) {
    send('error', { msg: String(err?.message || err) });
    res.end();
  }
});

app.listen(PORT, () => {
  console.log(`[cockpit-proxy] listening on http://localhost:${PORT}`);
  console.log(`[cockpit-proxy] model=${MODEL} source=${SOURCE_DIR}`);
});
