const form = document.querySelector("#convert-form");
const fileInput = document.querySelector("#artwork");
const fileName = document.querySelector("#file-name");
const statusText = document.querySelector("#status");
const button = document.querySelector("#convert-button");
const maxWidth = document.querySelector("#max-width");
const maxWidthValue = document.querySelector("#max-width-value");
const canvas = document.querySelector("#preview-canvas");
const imageSize = document.querySelector("#image-size");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(320, Math.round(rect.width * devicePixelRatio));
  canvas.height = Math.max(320, Math.round(rect.height * devicePixelRatio));
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
}

function drawEmpty() {
  resizeCanvas();
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.fillStyle = "#6d6760";
  ctx.font = "16px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("請選擇要轉成 PES 的圖片", rect.width / 2, rect.height / 2);
}

function drawPreview(file) {
  const image = new Image();
  image.onload = () => {
    resizeCanvas();
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    const scale = Math.min((rect.width - 48) / image.width, (rect.height - 48) / image.height, 1);
    const width = image.width * scale;
    const height = image.height * scale;
    const x = (rect.width - width) / 2;
    const y = (rect.height - height) / 2;
    ctx.drawImage(image, x, y, width, height);
    imageSize.textContent = `${image.width} x ${image.height}px`;
    URL.revokeObjectURL(image.src);
  };
  image.src = URL.createObjectURL(file);
}

maxWidth.addEventListener("input", () => {
  maxWidthValue.value = `${maxWidth.value} mm`;
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileName.textContent = file.name;
  statusText.textContent = "";
  statusText.classList.remove("error");
  drawPreview(file);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;

  const data = new FormData(form);
  button.disabled = true;
  statusText.textContent = "正在建立針跡並輸出 PES...";
  statusText.classList.remove("error");

  try {
    const response = await fetch("/convert", {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "轉檔失敗");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="(.+)"/);
    const filename = match ? match[1] : "design.pes";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    statusText.textContent = "完成，已下載 PES 檔。";
  } catch (error) {
    statusText.textContent = error.message;
    statusText.classList.add("error");
  } finally {
    button.disabled = false;
  }
});

window.addEventListener("resize", drawEmpty);
drawEmpty();
