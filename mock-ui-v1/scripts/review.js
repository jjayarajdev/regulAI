// HITL Review — light interactivity

(function () {
  // Queue item selection
  const items = document.querySelectorAll('.queue-item');
  items.forEach(i => {
    i.addEventListener('click', () => {
      items.forEach(x => x.classList.remove('active'));
      i.classList.add('active');
    });
  });

  // Segmented control (if present)
  document.querySelectorAll('.seg').forEach(seg => {
    seg.querySelectorAll('button').forEach(b => {
      b.addEventListener('click', () => {
        seg.querySelectorAll('button').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
      });
    });
  });

  // Candidate select buttons — echo to the action strip label
  document.querySelectorAll('.cand').forEach(c => {
    c.querySelector('.btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      const code = c.querySelector('.cand-code').textContent.trim();
      const approveBtn = document.querySelector('.action-strip .btn.primary');
      if (approveBtn) approveBtn.innerHTML = 'Approve · Code ' + code;
      // Visual echo
      document.querySelectorAll('.cand').forEach(x => x.classList.remove('primary'));
      c.classList.add('primary');
    });
  });
})();
