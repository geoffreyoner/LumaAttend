(function() {
  let page = 1;
  const tbody = document.getElementById('historyBody');
  const pagEl = document.getElementById('pagination');

  async function load() {
    const params = new URLSearchParams({
      page: page,
      from: document.getElementById('filterFrom').value,
      to: document.getElementById('filterTo').value,
      status: document.getElementById('filterStatus').value,
    });
    tbody.innerHTML = '<tr><td colspan="6" class="text-muted">Loading...</td></tr>';
    try {
      const data = await apiFetch('/api/attendance/history?' + params.toString());
      if (!data.history.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-muted">No records</td></tr>';
      } else {
        tbody.innerHTML = data.history.map(r => `
          <tr>
            <td>${window.escapeHtml(r.attendance_date)}</td>
            <td>${window.escapeHtml(r.employee_code)}</td>
            <td>${window.escapeHtml(r.full_name)}</td>
            <td>${window.escapeHtml(r.check_in || '-')}</td>
            <td>${window.escapeHtml(r.check_out || '-')}</td>
            <td><span class="badge ${window.escapeHtml(r.status.split(' ')[0])}">${window.escapeHtml(r.status)}</span></td>
          </tr>
        `).join('');
      }
      pagEl.innerHTML = '';
      for (let i = 1; i <= data.pages; i++) {
        const b = document.createElement('button');
        b.className = 'btn btn-sm ' + (i === data.page ? 'btn-primary' : 'btn-ghost');
        b.textContent = i;
        b.addEventListener('click', () => { page = i; load(); });
        pagEl.appendChild(b);
      }
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Error: ${window.escapeHtml(e.message)}</td></tr>`;
    }
  }

  document.getElementById('applyFilter').addEventListener('click', () => { page = 1; load(); });
  load();
})();