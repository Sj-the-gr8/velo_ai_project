(() => {
  const interactive = [...document.querySelectorAll('a, button, [role="button"], input, select, textarea')]
    .filter((element) => {
      const style = window.getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
    });
  document.querySelectorAll('[data-velo-mark]').forEach((mark) => mark.remove());
  interactive.forEach((element, index) => {
    const box = element.getBoundingClientRect();
    const mark = document.createElement('span');
    mark.dataset.veloMark = String(index + 1);
    mark.textContent = String(index + 1);
    Object.assign(mark.style, { position: 'fixed', left: `${box.left}px`, top: `${box.top}px`, zIndex: '2147483647', background: '#ffcc00', color: '#000', border: '2px solid #000', borderRadius: '50%', width: '24px', height: '24px', textAlign: 'center', font: 'bold 14px sans-serif', lineHeight: '20px', pointerEvents: 'none' });
    document.body.appendChild(mark);
    element.dataset.veloInteractiveIndex = String(index + 1);
  });
  return interactive.length;
})();
