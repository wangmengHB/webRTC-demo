const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 8080;
const ROOT = __dirname;

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

function serveStatic(req, res) {
  const reqPath = decodeURIComponent(req.url.split('?')[0]);
  let filePath = path.join(ROOT, reqPath === '/' ? '/sender/index.html' : reqPath);

  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }

    if (stats.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }

    const ext = path.extname(filePath).toLowerCase();
    const mimeType = MIME_TYPES[ext] || 'application/octet-stream';

    fs.readFile(filePath, (readErr, data) => {
      if (readErr) {
        res.writeHead(500);
        res.end('Internal Server Error');
        return;
      }
      res.writeHead(200, { 'Content-Type': mimeType });
      res.end(data);
    });
  });
}

const server = http.createServer(serveStatic);
const wss = new WebSocketServer({ server, path: '/signal' });

const rooms = new Map();

function getOrCreateRoom(roomId) {
  if (!rooms.has(roomId)) {
    rooms.set(roomId, { sender: null, receiver: null });
  }
  return rooms.get(roomId);
}

function sendJSON(ws, payload) {
  if (ws && ws.readyState === ws.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

function cleanupRoomIfEmpty(roomId) {
  const room = rooms.get(roomId);
  if (!room) return;
  if (!room.sender && !room.receiver) {
    rooms.delete(roomId);
  }
}

wss.on('connection', (ws) => {
  let currentRoomId = null;
  let currentRole = null;

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      sendJSON(ws, { type: 'error', message: 'Invalid JSON message' });
      return;
    }

    if (msg.type === 'join') {
      const roomId = String(msg.roomId || '').trim();
      const role = msg.role;

      if (!roomId || !['sender', 'receiver'].includes(role)) {
        sendJSON(ws, { type: 'error', message: 'join requires valid roomId and role' });
        return;
      }

      currentRoomId = roomId;
      currentRole = role;
      const room = getOrCreateRoom(roomId);

      if (room[role] && room[role] !== ws) {
        sendJSON(ws, { type: 'error', message: `Room already has a ${role}` });
        ws.close();
        return;
      }

      room[role] = ws;
      sendJSON(ws, { type: 'joined', roomId, role });

      const peerRole = role === 'sender' ? 'receiver' : 'sender';
      const peer = room[peerRole];
      if (peer) {
        sendJSON(peer, { type: 'peer-joined', role });
        sendJSON(ws, { type: 'peer-joined', role: peerRole });
      }

      return;
    }

    if (!currentRoomId || !currentRole) {
      sendJSON(ws, { type: 'error', message: 'You must join before signaling' });
      return;
    }

    const room = rooms.get(currentRoomId);
    if (!room) {
      sendJSON(ws, { type: 'error', message: 'Room no longer exists' });
      return;
    }

    const target = currentRole === 'sender' ? room.receiver : room.sender;
    if (!target) {
      sendJSON(ws, { type: 'info', message: 'Peer not connected yet' });
      return;
    }

    if (['offer', 'answer', 'candidate'].includes(msg.type)) {
      sendJSON(target, msg);
    }
  });

  ws.on('close', () => {
    if (!currentRoomId || !currentRole) return;
    const room = rooms.get(currentRoomId);
    if (!room) return;

    room[currentRole] = null;
    const peerRole = currentRole === 'sender' ? 'receiver' : 'sender';
    sendJSON(room[peerRole], { type: 'peer-left', role: currentRole });
    cleanupRoomIfEmpty(currentRoomId);
  });
});

server.listen(PORT, () => {
  console.log(`WebRTC demo server running at http://localhost:${PORT}`);
  console.log(`Sender page:   http://localhost:${PORT}/sender/`);
  console.log(`Receiver page: http://localhost:${PORT}/receiver/`);
});
