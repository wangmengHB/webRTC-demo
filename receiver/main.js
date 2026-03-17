const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const remoteVideo = document.getElementById('remoteVideo');
const createAnswerBtn = document.getElementById('createAnswerBtn');
const addSenderCandidatesBtn = document.getElementById('addSenderCandidatesBtn');
const offerInEl = document.getElementById('offerIn');
const answerOutEl = document.getElementById('answerOut');
const senderCandidatesInEl = document.getElementById('senderCandidatesIn');
const receiverCandidatesOutEl = document.getElementById('receiverCandidatesOut');

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

  pc.ontrack = (event) => {
    remoteVideo.srcObject = event.streams[0];
    log('Remote track received');
  };

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      localCandidates.push(event.candidate);
      receiverCandidatesOutEl.value = JSON.stringify(localCandidates, null, 2);
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

createAnswerBtn.onclick = async () => {
  try {
    const offer = JSON.parse(offerInEl.value);

    localCandidates.length = 0;
    receiverCandidatesOutEl.value = '';

    if (pc) {
      pc.close();
    }
    createPeerConnection();

    await pc.setRemoteDescription(new RTCSessionDescription(offer));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    answerOutEl.value = JSON.stringify(pc.localDescription, null, 2);
    setStatus('answer ready');
    log('Offer applied and answer created. Copy answer to sender page.');
  } catch (err) {
    log(`Invalid offer JSON: ${err.message}`);
  }
};

addSenderCandidatesBtn.onclick = async () => {
  if (!pc) {
    log('Create answer first');
    return;
  }

  try {
    const candidates = JSON.parse(senderCandidatesInEl.value);
    if (!Array.isArray(candidates)) {
      throw new Error('Sender ICE candidates must be a JSON array');
    }

    for (const candidate of candidates) {
      await pc.addIceCandidate(candidate);
    }

    log(`Added ${candidates.length} sender ICE candidates`);
  } catch (err) {
    log(`Invalid sender ICE JSON: ${err.message}`);
  }
};
