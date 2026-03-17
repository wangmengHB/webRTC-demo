const http = require('http');
const fs = require('fs');
const path = require('path');

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

server.listen(PORT, () => {
  console.log(`WebRTC demo server running at http://localhost:${PORT}`);
  console.log(`Sender page:   http://localhost:${PORT}/sender/`);
  console.log(`Receiver page: http://localhost:${PORT}/receiver/`);
  console.log('Signaling mode: manual copy/paste (no WebSocket server)');
});
