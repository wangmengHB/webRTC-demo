const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const roomIdEl = document.getElementById('roomId');
const remoteVideo = document.getElementById('remoteVideo');
const connectBtn = document.getElementById('connectBtn');

let ws;
let pc;

function setStatus(text) {
  statusEl.textContent = text;
}

function log(text) {
  logEl.textContent += `${new Date().toLocaleTimeString()} - ${text}\n`;
}

function createPeerConnection() {
  pc = new RTCPeerConnection({
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
  });

  pc.ontrack = (event) => {
    remoteVideo.srcObject = event.streams[0];
    log('Remote track received');
  };

  pc.onicecandidate = (event) => {
    if (event.candidate && ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate }));
    }
  };

  pc.onconnectionstatechange = () => {
    log(`Peer state: ${pc.connectionState}`);
    setStatus(`peer: ${pc.connectionState}`);
  };
}

connectBtn.onclick = () => {
  const roomId = roomIdEl.value.trim();
  if (!roomId) {
    log('Room ID is required');
    return;
  }

  ws = new WebSocket(`ws://${location.host}/signal`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'join', role: 'receiver', roomId }));
    setStatus('joined signaling');
    log(`Joined room: ${roomId} as receiver`);
    if (!pc) createPeerConnection();
  };

  ws.onmessage = async (evt) => {
    const msg = JSON.parse(evt.data);

    if (msg.type === 'offer') {
      await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      ws.send(JSON.stringify({ type: 'answer', sdp: answer }));
      log('Received offer and sent answer');
    } else if (msg.type === 'candidate') {
      if (pc) {
        await pc.addIceCandidate(msg.candidate);
        log('Received ICE candidate');
      }
    } else if (msg.type === 'peer-left') {
      setStatus('sender disconnected');
      log('Sender disconnected');
    } else if (msg.type === 'error') {
      setStatus('error');
      log(`Error: ${msg.message}`);
    }
  };

  ws.onclose = () => {
    setStatus('signaling closed');
    log('Signaling connection closed');
  };
};
