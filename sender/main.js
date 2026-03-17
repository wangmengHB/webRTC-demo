const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const localVideo = document.getElementById('localVideo');
const startBtn = document.getElementById('startBtn');
const createOfferBtn = document.getElementById('createOfferBtn');
const applyAnswerBtn = document.getElementById('applyAnswerBtn');
const addReceiverCandidatesBtn = document.getElementById('addReceiverCandidatesBtn');
const offerOutEl = document.getElementById('offerOut');
const answerInEl = document.getElementById('answerIn');
const senderCandidatesOutEl = document.getElementById('senderCandidatesOut');
const receiverCandidatesInEl = document.getElementById('receiverCandidatesIn');

let localStream;
let pc;
const localCandidates = [];

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
    if (event.candidate) {
      localCandidates.push(event.candidate);
      senderCandidatesOutEl.value = JSON.stringify(localCandidates, null, 2);
      log(`Collected local ICE candidate (${localCandidates.length})`);
      return;
    }

    log('Local ICE gathering complete');
  };

  pc.onconnectionstatechange = () => {
    log(`Peer state: ${pc.connectionState}`);
    setStatus(`peer: ${pc.connectionState}`);
  };

  return pc;
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

createOfferBtn.onclick = async () => {
  if (!localStream) {
    log('Start camera first');
    return;
  }

  localCandidates.length = 0;
  senderCandidatesOutEl.value = '';
  receiverCandidatesInEl.value = '';

  if (pc) {
    pc.close();
  }
  createPeerConnection();

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  offerOutEl.value = JSON.stringify(pc.localDescription, null, 2);
  setStatus('offer ready');
  log('Offer created. Copy it to receiver page.');
};

applyAnswerBtn.onclick = async () => {
  if (!pc) {
    log('Create offer first');
    return;
  }

  try {
    const answer = JSON.parse(answerInEl.value);
    await pc.setRemoteDescription(new RTCSessionDescription(answer));
    setStatus('answer applied');
    log('Answer applied successfully');
  } catch (err) {
    log(`Invalid answer JSON: ${err.message}`);
  }
};

addReceiverCandidatesBtn.onclick = async () => {
  if (!pc) {
    log('Create offer first');
    return;
  }

  try {
    const candidates = JSON.parse(receiverCandidatesInEl.value);
    if (!Array.isArray(candidates)) {
      throw new Error('Receiver ICE candidates must be a JSON array');
    }

    for (const candidate of candidates) {
      await pc.addIceCandidate(candidate);
    }

    log(`Added ${candidates.length} receiver ICE candidates`);
  } catch (err) {
    log(`Invalid receiver ICE JSON: ${err.message}`);
  }
};
