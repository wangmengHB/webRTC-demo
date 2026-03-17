# WebRTC Sender/Receiver Demo

这是一个由 AI 生成的最小的 webrtc demo。 这个 demo 由 3 部分组成：
1. server： 一个简单的 web server，它在这个 demo 中存在的唯一作用建立 webRTC 握手链接
2. sender： 视频发送端
3. receiver: 视频接收端



After startup:

- Sender: `http://localhost:8080/sender/`
- Receiver: `http://localhost:8080/receiver/`






A simple local WebRTC demo with:

- **Sender** page: captures local camera video and publishes it via WebRTC.
- **Receiver** page: receives and plays remote video stream.
- **Signaling server**: WebSocket server for SDP and ICE exchange.

## Prerequisites

- Node.js 18+
- A modern browser (Chrome/Edge/Safari)
- Camera permission allowed on sender page

## Install

```bash
npm install
```

## Run

```bash
npm start
```

After startup:

- Sender: `http://localhost:8080/sender/`
- Receiver: `http://localhost:8080/receiver/`

## How to use

1. Open sender page in one tab/window and receiver page in another.
2. Keep same **Room ID** on both pages (default: `demo-room`).
3. On sender page, click **Start Camera**.
4. On sender page, click **Connect**.
5. On receiver page, click **Connect**.
6. Receiver should show sender's video.

## Notes

- This is a local demo using a public STUN server (`stun.l.google.com:19302`).
- For production/NAT-restricted environments, add a TURN server.
- Signaling is in-memory; no persistence/database is used.

## Troubleshooting

- If receiver shows no video, make sure sender started camera before connecting.
- Check that both tabs use the same room ID.
- Ensure camera permissions are granted in browser settings.
