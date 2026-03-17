# WebRTC Sender/Receiver Demo (No WebSocket)

A minimal local WebRTC demo with manual signaling:

- **Sender page**: captures local camera video.
- **Receiver page**: receives and plays remote video stream.
- **Signaling**: done by **copy/paste** of SDP and ICE JSON between pages.

## Architecture

- `server.js`: static file server only.
- `sender/`: offer creator + local camera publisher.
- `receiver/`: answer creator + remote stream viewer.

No WebSocket server is used.

## Prerequisites

- Node.js 18+
- Modern browser (Chrome/Edge/Safari)
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

## How to use (manual signaling)

1. Open sender page and receiver page in separate tabs/windows.
2. On **sender** page, click **启动摄像头**.
3. On **sender** page, click **生成 Offer**.
4. Copy sender **Offer** JSON into receiver **Offer** input.
5. On **receiver** page, click **应用 Offer 并生成 Answer**.
6. Copy receiver **Answer** JSON into sender **Answer** input.
7. On **sender** page, click **应用 Answer**.
8. Copy sender **Sender ICE Candidates** JSON array into receiver **Sender ICE Candidates** input.
9. On **receiver** page, click **添加 Sender ICE**.
10. Copy receiver **Receiver ICE Candidates** JSON array into sender **Receiver ICE Candidates** input.
11. On **sender** page, click **添加 Receiver ICE**.
12. Receiver should display sender video.

## Notes

- ICE candidates are collected asynchronously; if arrays are still changing, copy once more after a few seconds.
- Uses public STUN server: `stun:stun.l.google.com:19302`.
- For stricter NAT/firewall environments, TURN server is recommended.

## Troubleshooting

- If no video appears, ensure sender camera started before generating offer.
- Re-run from step 3 when either side refreshes.
- Confirm pasted data is valid JSON and arrays remain arrays.
