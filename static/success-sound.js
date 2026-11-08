(function () {
  const sound = document.getElementById('findly-success-sound');
  if (!sound) return;

  function playFindlySound() {
    try {
      sound.currentTime = 0;
      const playPromise = sound.play();
      if (playPromise && playPromise.catch) playPromise.catch(function () {});
    } catch (error) {}
  }

  window.playFindlySound = playFindlySound;

  document.addEventListener('click', function (event) {
    const link = event.target.closest('a.item');
    if (!link || event.defaultPrevented) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    playFindlySound();
    window.setTimeout(function () { window.location.href = link.href; }, 450);
  }, true);

  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.findlySoundPlayed === '1') return;
    const isNewListing = form.matches('.form-card') && form.querySelector('input[name="title"]');
    const isStatusChange = Boolean(form.closest('.admin-actions'));
    if (!isNewListing && !isStatusChange) return;
    event.preventDefault();
    form.dataset.findlySoundPlayed = '1';
    playFindlySound();
    window.setTimeout(function () { HTMLFormElement.prototype.submit.call(form); }, 450);
  }, true);

  if (document.querySelector('.flash.success')) playFindlySound();
})();
