
const sourceVideo = document.getElementById('remoteVideo');

const readImageCanvas = document.getElementById('readImageCanvas');
const readImageCtx = readImageCanvas.getContext('2d');

const drawCanvas = document.getElementById('drawCanvas');
const drawCtx = drawCanvas.getContext('2d');

function drawVideoToCanvas() {
  if (sourceVideo.readyState >= 2) {
    if (readImageCanvas.width !== sourceVideo.videoWidth || readImageCanvas.height !== sourceVideo.videoHeight) {
      readImageCanvas.width = sourceVideo.videoWidth;
      readImageCanvas.height = sourceVideo.videoHeight;
      drawCanvas.width = sourceVideo.videoWidth;
      drawCanvas.height = sourceVideo.videoHeight;
    }

    // 将 video 的当前帧绘制到 readImageCanvas 上，从而可以提取每一个像素进行处理
    readImageCtx.drawImage(sourceVideo, 0, 0, readImageCanvas.width, readImageCanvas.height);
    const frame = readImageCtx.getImageData(0, 0, readImageCanvas.width, readImageCanvas.height);

    // Example processing: invert colors
    for (let i = 0; i < frame.data.length ; i += 4) {
      frame.data[i] = 255 - frame.data[i];       // R
      frame.data[i + 1] = 255 - frame.data[i + 1]; // G
      frame.data[i + 2] = 255 - frame.data[i + 2]; // B
    }

    // 在这里使用的是 2d context 进行绘制，
    // 在这里可以使用 webgl 或者 webgpu context 来进行更高效的绘制和处理
    drawCtx.putImageData(frame, 0, 0);
  }
  requestAnimationFrame(drawVideoToCanvas);
}

sourceVideo.addEventListener('play', () => {
  drawVideoToCanvas();
});
