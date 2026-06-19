<script>
  import { createEventDispatcher } from 'svelte'
  import { api } from './api.js'

  const dispatch = createEventDispatcher()

  let open = false
  let sending = false
  let error = ''
  let success = false

  // Form data.
  let summary = ''
  let date = todayISO()
  let startTime = '10:00'
  let endTime = '11:00'
  let allDay = false
  let location = ''
  let description = ''

  function todayISO() {
    const d = new Date()
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0')
  }

  function reset() {
    summary = ''
    date = todayISO()
    startTime = '10:00'
    endTime = '11:00'
    allDay = false
    location = ''
    description = ''
    error = ''
  }

  function openForm() {
    reset()
    open = true
  }

  function closeForm(e) {
    // Alleen sluiten als de overlay zelf geklikt is, niet de modal erin.
    if (e && e.target !== e.currentTarget) return
    open = false
    error = ''
    if (success) {
      dispatch('created')
      success = false
    }
  }

  async function submit() {
    if (!summary.trim()) return
    sending = true
    error = ''
    try {
      const body = {
        summary: summary.trim(),
        start: allDay ? date : date + 'T' + startTime + ':00',
        end: allDay ? nextDay(date) : date + 'T' + endTime + ':00',
        description: description.trim() || undefined,
        location: location.trim() || undefined,
        all_day: allDay,
      }
      await api.createEvent(body)
      success = true
      sending = false
      // Sluit na korte pauze zodat de gebruiker de check ziet.
      setTimeout(() => {
        closeForm()
      }, 1500)
    } catch (e) {
      error = e.message || 'Aanmaken mislukt.'
      sending = false
    }
  }

  function nextDay(d) {
    const dt = new Date(d + 'T12:00:00')
    dt.setDate(dt.getDate() + 1)
    return dt.getFullYear() + '-' +
      String(dt.getMonth() + 1).padStart(2, '0') + '-' +
      String(dt.getDate()).padStart(2, '0')
  }

  function onKeydown(e) {
    if (e.key === 'Escape') closeForm()
  }
</script>

<svelte:window on:keydown={onKeydown} />

<!-- "+" knop -->
<button class="add-btn" on:click={openForm} aria-label="Nieuwe afspraak">
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
  <span>Afspraak</span>
</button>

<!-- Modaal -->
{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div class="overlay" on:click={closeForm} on:keydown={onKeydown} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal">
      <h2 class="modal-title">Nieuwe afspraak</h2>

      {#if success}
        <div class="success">✓ Afspraak aangemaakt</div>
      {:else}
        <form class="form" on:submit|preventDefault={submit}>
          <label class="field">
            <span class="label-text">Titel</span>
            <input class="input" type="text" bind:value={summary} placeholder="Wat staat er op de planning?" maxlength="500" />
          </label>

          <label class="field">
            <span class="label-text">Datum</span>
            <input class="input" type="date" bind:value={date} />
          </label>

          <label class="field checkbox-field">
            <input type="checkbox" bind:checked={allDay} />
            <span class="label-text">Hele dag</span>
          </label>

          {#if !allDay}
            <div class="time-row">
              <label class="field">
                <span class="label-text">Van</span>
                <input class="input" type="time" bind:value={startTime} />
              </label>
              <label class="field">
                <span class="label-text">Tot</span>
                <input class="input" type="time" bind:value={endTime} />
              </label>
            </div>
          {/if}

          <label class="field">
            <span class="label-text">Locatie <span class="opt">(optioneel)</span></span>
            <input class="input" type="text" bind:value={location} placeholder="Waar?" maxlength="500" />
          </label>

          <label class="field">
            <span class="label-text">Omschrijving <span class="opt">(optioneel)</span></span>
            <textarea class="input textarea" bind:value={description} placeholder="Details..." maxlength="2000" rows="3"></textarea>
          </label>

          {#if error}
            <div class="error">{error}</div>
          {/if}

          <div class="buttons">
            <button type="button" class="cancel" on:click={closeForm}>Annuleren</button>
            <button type="submit" class="submit" disabled={sending || !summary.trim()}>
              {sending ? 'Bezig…' : 'Aanmaken'}
            </button>
          </div>
        </form>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* "+" knop */
  .add-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-height: var(--tap-min);
    padding: 10px 22px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--accent);
    font-weight: 600;
    font-size: 1.05rem;
    transition: all 0.12s ease;
    margin-bottom: var(--gap);
    cursor: pointer;
  }
  .add-btn:hover {
    border-color: var(--accent);
    background: rgba(90,209,201,0.06);
  }

  /* Overlay */
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.75);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 20px;
  }

  /* Modal */
  .modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .modal-title { font-size: 1.4rem; }

  .form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 10px;
  }
  .checkbox-field input[type="checkbox"] {
    width: 22px;
    height: 22px;
    accent-color: var(--accent);
  }

  .label-text { font-size: 0.9rem; color: var(--muted); }
  .opt { font-size: 0.8rem; }

  .input {
    min-height: var(--tap-min);
    padding: 12px 16px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 1.05rem;
    color: var(--text);
    font-family: inherit;
  }
  .input::placeholder { color: var(--muted); }
  .input:focus { border-color: var(--accent); outline: none; }

  .textarea {
    resize: vertical;
    min-height: 80px;
  }

  .time-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .buttons {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 4px;
  }

  .cancel {
    min-height: var(--tap-min);
    padding: 10px 22px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    font-size: 1rem;
    cursor: pointer;
  }
  .cancel:hover { color: var(--text); border-color: var(--text); }

  .submit {
    min-height: var(--tap-min);
    padding: 10px 28px;
    background: var(--accent);
    color: #04201e;
    font-weight: 700;
    font-size: 1rem;
    border: none;
    border-radius: 999px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .submit:hover { background: var(--accent-strong); }
  .submit:disabled { opacity: 0.4; cursor: default; }

  .error {
    color: var(--danger);
    font-size: 0.9rem;
  }
  .success {
    color: var(--accent);
    font-size: 1.2rem;
    text-align: center;
    padding: 20px 0;
  }
</style>
