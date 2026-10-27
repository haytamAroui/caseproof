/* Synthetic, read-only spike. No data leaves the host and no document edits. */
(() => {
  const button = document.getElementById('inspect');
  const status = document.getElementById('status');
  const result = document.getElementById('result');
  const selection = document.getElementById('selection');
  if (typeof Office === 'undefined') {
    status.textContent = 'Office could not load. Open this add-in in a supported Word host.';
    return;
  }
  Office.onReady((info) => {
    if (info.host !== Office.HostType.Word || !Office.context.requirements.isSetSupported('WordApi', '1.1')) {
      status.textContent = 'This spike requires a Word host with WordApi 1.1.';
      return;
    }
    button.disabled = false;
    status.textContent = 'Select a sentence in the synthetic document.';
  });
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.hidden = true;
    selection.textContent = '';
    status.textContent = 'Reading selection…';
    try {
      const text = await Word.run(async (context) => {
        const range = context.document.getSelection();
        range.load('text');
        await context.sync();
        return range.text;
      });
      if (!text.trim() || text.length > 1000) {
        status.textContent = 'Select a non-empty passage of at most 1,000 characters.';
      } else {
        selection.textContent = text;
        result.hidden = false;
        status.textContent = 'Example shown. This is not a verified match.';
      }
    } catch (_) {
      status.textContent = 'Could not read the selection. Return to Word, select text and try again.';
    } finally {
      button.disabled = false;
    }
  });
})();
