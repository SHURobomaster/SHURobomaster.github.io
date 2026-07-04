function setStatus(message) {
  const status = document.getElementById("contact-status");
  if (status) status.textContent = message;
}

document.getElementById("copy-email")?.addEventListener("click", async () => {
  const email = "srm_robomaster@163.com";
  try {
    await navigator.clipboard.writeText(email);
    setStatus("报名邮箱已复制。");
  } catch (error) {
    setStatus(`报名邮箱：${email}`);
  }
});

window.addEventListener("load", () => {
  const canvas = document.getElementById("hero-pointcloud");
  const reset = document.getElementById("reset-pointcloud");
  const payload = window.SRM_VEHICLE_POINT_CLOUD;
  if (!canvas || !payload || !Array.isArray(payload.points)) return;

  const ctx = canvas.getContext("2d");
  const maxRenderPoints = 9000;
  const step = Math.max(1, Math.ceil(payload.points.length / maxRenderPoints));
  const rawPoints = payload.points
    .filter((_, index) => index % step === 0)
    .map(([x, y, z, component]) => ({ x, y, z, component }));

  let rotationX = -0.34;
  let rotationY = -0.72;
  let targetX = rotationX;
  let targetY = rotationY;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let lastFrame = 0;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const scale = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(rect.width * scale));
    canvas.height = Math.max(1, Math.floor(rect.height * scale));
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
  }

  function rotatePoint(point) {
    const cosY = Math.cos(rotationY);
    const sinY = Math.sin(rotationY);
    const cosX = Math.cos(rotationX);
    const sinX = Math.sin(rotationX);
    const x1 = point.x * cosY - point.z * sinY;
    const z1 = point.x * sinY + point.z * cosY;
    const y1 = point.y * cosX - z1 * sinX;
    const z2 = point.y * sinX + z1 * cosX;
    return { x: x1, y: y1, z: z2, component: point.component };
  }

  function draw(now = 0) {
    if (now - lastFrame < 33) {
      requestAnimationFrame(draw);
      return;
    }
    lastFrame = now;

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    ctx.clearRect(0, 0, width, height);

    rotationX += (targetX - rotationX) * 0.08;
    rotationY += (targetY - rotationY) * 0.08;
    if (!dragging) targetY -= 0.004;

    const scale = Math.min(width, height) * 0.2;
    const centerX = width * 0.56;
    const centerY = height * 0.56;

    ctx.save();
    ctx.globalCompositeOperation = "screen";
    for (const rawPoint of rawPoints) {
      const point = rotatePoint(rawPoint);
      const depth = 1 / (1 + Math.max(0, point.z + 4.2) * 0.08);
      const px = centerX + point.x * scale * depth;
      const py = centerY - point.y * scale * depth;
      const near = Math.max(0, Math.min(1, (point.z + 2.9) / 5.8));
      const alpha = point.component === 7
        ? 0.035
        : Math.max(0.13, Math.min(0.68, 0.18 + near * 0.5));
      const size = point.component === 7 ? 0.34 : 0.62 + near * 1.12;
      const tone = point.component === 6 ? "164, 186, 226" : point.component === 3 ? "235, 242, 255" : "204, 220, 248";
      ctx.fillStyle = point.component === 7 ? "rgba(78, 88, 110, 0.035)" : `rgba(${tone}, ${alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.strokeStyle = "rgba(240, 240, 250, 0.1)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(width * 0.18, height * 0.82);
    ctx.lineTo(width * 0.82, height * 0.82);
    ctx.stroke();

    requestAnimationFrame(draw);
  }

  canvas.addEventListener("pointerdown", (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    targetY += (event.clientX - lastX) * 0.008;
    targetX += (event.clientY - lastY) * 0.006;
    lastX = event.clientX;
    lastY = event.clientY;
  });

  canvas.addEventListener("pointerup", () => {
    dragging = false;
  });

  reset?.addEventListener("click", () => {
    targetX = -0.34;
    targetY = -0.72;
  });

  window.addEventListener("resize", resize);
  resize();
  draw();
});
