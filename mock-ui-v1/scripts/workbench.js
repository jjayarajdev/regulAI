// Mapping Workbench — light interactivity for the mock

(function () {
  // Table node expand/collapse
  document.querySelectorAll('.table-header').forEach(h => {
    h.addEventListener('click', () => {
      h.parentElement.classList.toggle('open');
    });
  });

  // Mapping row selection
  const rows = document.querySelectorAll('.mapping-row');
  rows.forEach(r => {
    r.addEventListener('click', () => {
      rows.forEach(x => x.classList.remove('selected'));
      r.classList.add('selected');
      // Visual echo — highlight source fields tied to this mapping
      const mid = r.dataset.mid;
      document.querySelectorAll('.field-row.selected').forEach(f => f.classList.remove('selected'));
      // For the demo we only wire highlighting for M-GW-028
      if (mid === 'M-GW-028') {
        document.querySelectorAll('[data-mapping="M-GW-028"]').forEach(f => f.classList.add('selected'));
      }
    });
  });

  // Tabs
  document.querySelectorAll('.tabs .tab').forEach(t => {
    t.addEventListener('click', () => {
      t.parentElement.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
    });
  });

  // Segmented control
  document.querySelectorAll('.seg').forEach(seg => {
    seg.querySelectorAll('button').forEach(b => {
      b.addEventListener('click', () => {
        seg.querySelectorAll('button').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
      });
    });
  });
})();
