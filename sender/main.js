const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const roomIdEl = document.getElementById('roomId');
const localVideo = document.getElementById('localVideo');
const startBtn = document.getElementById('startBtn');
const connectBtn = document.getElementById('connectBtn');

let localStream;
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

  localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

  pc.onicecandidate = (event) => {
    if (event.candidate && ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate }));
    }
  };

  pc.onconnectionstatechange = () => {
    log(`Peer state: ${pc.connectionState}`);
    setStatus(`peer: ${pc.connectionState}`);
  };

  return pc;
}

async function makeOffer() {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  ws.send(JSON.stringify({ type: 'offer', sdp: offer }));
  log('Sent offer');
}

startBtn.onclick = async () => {
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    localVideo.srcObject = localStream;
    setStatus('camera ready');
    log('Camera started');
  } catch (err) {
    setStatus('camera error');
    log(`Camera error: ${err.message}`);
  }
};

connectBtn.onclick = async () => {
  const roomId = roomIdEl.value.trim();
  if (!roomId) {
    log('Room ID is required');
    return;
  }
  if (!localStream) {
    log('Start camera first');
    return;
  }

  ws = new WebSocket(`ws://${location.host}/signal`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'join', role: 'sender', roomId }));
    setStatus('joined signaling');
    log(`Joined room: ${roomId} as sender`);
  };

  ws.onmessage = async (evt) => {
    const msg = JSON.parse(evt.data);

    if (msg.type === 'peer-joined') {
      log('Receiver joined, creating offer');
      if (!pc) createPeerConnection();
      await makeOffer();
    } else if (msg.type === 'answer') {
      await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
      log('Received answer');
    } else if (msg.type === 'candidate') {
      if (pc) {
        await pc.addIceCandidate(msg.candidate);
        log('Received ICE candidate');
      }
    } else if (msg.type === 'peer-left') {
      setStatus('receiver disconnected');
      log('Receiver disconnected');
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
