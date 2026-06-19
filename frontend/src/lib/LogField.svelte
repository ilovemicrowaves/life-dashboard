<script>
  import { createEventDispatcher } from 'svelte'
  import { api } from './api.js'

  export let config

  const dispatch = createEventDispatcher()

  let text = ''
  let theme = config.defaultTheme || (config.themes && config.themes[0]) || 'algemeen'
  let sending = false
  let saved = false
  let savedTimer

  async function submit() {
    const t = text.trim()
    if (!t || sending) return
    sending = true
    try {
      await api.log(t, theme)
      text = ''
      saved = true
      clearTimeout(savedTimer)
      savedTimer = setTimeout(() => (saved = false), 2200)
      dispatch('logged')
    } catch (e) {
      console.error(e)
    } finally {
      sending = false
    }
  }

  function onKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }
</script>

<section class="logfield">
  <h2 class="title">Log</h2>

  <input
    class="input"
    type="text"
    bind:value={text}
    on:keydown={onKeydown}
    placeholder={config.logPlaceholder}
    aria-label="Logregel"
    maxlength="2000"
  />

  <div class="row">
    <label class="theme">
      <span class="muted">#log/</span>
      <select bind:value={theme} aria-label="Thema">
        {#each config.themes as t}
          <option value={t}>{t}</option>
        {/each}
      </select>
    </label>

    <button class="send" on:click={submit} disabled={sending || !text.trim()}>
      {sending ? 'Bezig…' : 'Voeg toe'}
    </button>
  </div>

  {#if saved}
    <div class="saved" role="status">Toegevoegd aan de dagnotitie.</div>
  {/if}
</section>

<style>
  .logfield {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .title { font-size: 1.3rem; }

  .input {
    width: 100%;
    min-height: var(--tap-min);
    padding: 14px 18px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 1.15rem;
  }
  .input::placeholder { color: var(--muted); }
  .input:focus { border-color: var(--accent); outline: none; }

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
  }

  .theme {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 6px 14px 6px 16px;
    min-height: 48px;
  }
  .theme select {
    background: transparent;
    border: none;
    font-size: 1.05rem;
    padding: 6px 4px;
  }
  .theme select:focus { outline: none; }

  .send {
    min-height: var(--tap-min);
    padding: 12px 28px;
    background: var(--accent);
    color: #04201e;
    font-weight: 700;
    border-radius: 999px;
    font-size: 1.1rem;
    transition: background 0.12s ease;
  }
  .send:hover { background: var(--accent-strong); }
  .send:disabled { opacity: 0.45; cursor: default; }

  .saved { color: var(--accent); font-size: 0.95rem; }
</style>
