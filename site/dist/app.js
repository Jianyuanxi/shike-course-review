const dialog = document.querySelector('.image-dialog');
const dialogImage = dialog.querySelector('img');
const dialogCaption = dialog.querySelector('p');
const toast = document.querySelector('.toast');
let toastTimer;

for (const button of document.querySelectorAll('[data-zoom]')) {
  button.addEventListener('click', () => {
    const sourceImage = button.querySelector('img');
    dialogImage.src = button.dataset.zoom;
    dialogImage.alt = sourceImage.alt;
    dialogCaption.textContent = button.dataset.caption;
    dialog.showModal();
  });
}

dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => {
  if (event.target === dialog) dialog.close();
});

for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = '已复制';
      toast.textContent = '命令已复制到剪贴板';
      toast.classList.add('visible');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => {
        button.textContent = '复制';
        toast.classList.remove('visible');
      }, 1800);
    } catch {
      toast.textContent = '复制失败，请手动选择命令';
      toast.classList.add('visible');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('visible'), 2200);
    }
  });
}
