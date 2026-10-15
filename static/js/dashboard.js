(async function() {
  const clockEl = document.getElementById('liveClock');
  function tick() {
    if (!clockEl) return;
    const d = new Date();
    clockEl.textContent = d.toLocaleString('id-ID', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }
  tick(); setInterval(tick, 1000);

  try {
    const data = await apiFetch('/api/dashboard/stats');
    const s = data.stats;
    document.getElementById('statsGrid').innerHTML = `
      <div class="glass stat-card"><div class="stat-value">${s.total_users}</div><div class="stat-label">Total Users</div></div>
      <div class="glass stat-card"><div class="stat-value" style="color:var(--success)">${s.checked_in}</div><div class="stat-label">Present Today</div></div>
      <div class="glass stat-card"><div class="stat-value" style="color:var(--warning)">${s.late}</div><div class="stat-label">Late Today</div></div>
      <div class="glass stat-card"><div class="stat-value" style="color:var(--danger)">${s.not_checked_in}</div><div class="stat-label">Not Checked In</div></div>
    `;
    const recent = document.getElementById('recentList');
    if (data.today && data.today.length) {
      recent.innerHTML = data.today.slice(0, 8).map(r => `
        <div class="record-item">
          <div><strong>${window.escapeHtml(r.full_name)}</strong> <span class="text-muted">(${window.escapeHtml(r.employee_code)})</span></div>
          <div><span class="badge ${window.escapeHtml(r.status.split(' ')[0])}">${window.escapeHtml(r.status)}</span>
          ${r.check_in ? `<span class="text-muted">${window.escapeHtml(r.check_in.slice(0,5))}</span>` : ''}</div>
        </div>
      `).join('');
    } else {
      recent.innerHTML = '<p class="text-muted">No attendance recorded today</p>';
    }
  } catch (e) {
    showToast('Failed to load dashboard: ' + e.message, 'error');
  }

  // Simple trend canvas
  try {
    const hist = await apiFetch('/api/attendance/history?page=1');
    const canvas = document.getElementById('trendChart');
    if (canvas && hist.history) {
      const byDate = {};
      hist.history.forEach(r => {
        byDate[r.attendance_date] = (byDate[r.attendance_date] || 0) + 1;
      });
      const dates = Object.keys(byDate).sort().slice(-7);
      const vals = dates.map(d => byDate[d]);
      const ctx = canvas.getContext('2d');
      const W = canvas.width = canvas.clientWidth;
      const H = canvas.height = 160;
      ctx.clearRect(0, 0, W, H);
      if (vals.length === 0) {
        ctx.fillStyle = '#A6ADC5';
        ctx.fillText('No data', 10, 30);
      } else {
        const maxV = Math.max(...vals, 1);
        const stepX = W / (vals.length + 1);
        ctx.beginPath();
        vals.forEach((v, i) => {
          const x = stepX * (i + 1);
          const y = H - 30 - (v / maxV) * (H - 50);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#8B9CFF';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        vals.forEach((v, i) => {
          const x = stepX * (i + 1);
          const y = H - 30 - (v / maxV) * (H - 50);
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#78E6D0';
          ctx.fill();
          ctx.fillStyle = '#A6ADC5';
          ctx.font = '11px sans-serif';
          ctx.fillText(dates[i].slice(5), x - 18, H - 8);
        });
      }
    }
  } catch (e) { /* ignore */ }
})();