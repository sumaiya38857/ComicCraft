// Polls job status and redirects to the comic preview when done.
(() => {
  const root = document.getElementById('progress');
  if (!root) return;
  const jobId = root.dataset.job;
  const comicId = root.dataset.comic;
  const $ = id => document.getElementById(id);

  async function poll() {
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const job = await res.json();
      $('step').textContent = job.step;
      $('fill').style.width = `${job.progress}%`;
      $('pct').textContent = `${job.progress}%`;
      if (job.state === 'done') { window.location.href = `/comics/${comicId}`; return; }
      if (job.state === 'failed') {
        $('error').textContent = job.error || 'Something went wrong.';
        $('error').classList.remove('hidden');
        $('back').classList.remove('hidden');
        return;
      }
    } catch (err) {
      console.warn('poll failed', err);
    }
    setTimeout(poll, 2000);
  }
  poll();
})();
