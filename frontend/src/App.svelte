<script>
  import { onMount, onDestroy } from 'svelte'
  import { api } from './lib/api.js'
  import Agenda from './lib/Agenda.svelte'
  import CreateEvent from './lib/CreateEvent.svelte'
  import LogField from './lib/LogField.svelte'
  import RecentLogs from './lib/RecentLogs.svelte'
  import SpeakQR from './lib/SpeakQR.svelte'

  let config = null
  let agenda = null
  let recent = []
  let error = ''
  let rebuilding = false
  let reloadTimer

  async function loadAll() {
    error = ''
    try {
      config = await api.config()
      const [a, r] = await Promise.all([api.agenda(), api.recent()])
      agenda = a
      recent = r.logs
    } catch (e) {
      error = 'Kon het dashboard niet laden. Draait de API?'
      // eslint-disable-next-line no-console
      console.error(e)
    }
  }

  async function refreshRecent() {
    try {
      const r = await api.recent()
      recent = r.logs
    } catch (e) {
      console.error(e)
    }
  }

  async function rebuildIndex() {
    if (rebuilding) return
    rebuilding = true
    try {
      await api.rebuild()
      await loadAll()
    } catch (e) {
      error = 'Herbouwen mislukt.'
    } finally {
      rebuilding = false
    }
  }

  onMount(async () => {
    await loadAll()
    // Periodieke volledige page-reload tegen geheugenlekken op de TV.
    if (config && config.reloadMs > 0) {
      reloadTimer = setTimeout(() => location.reload(), config.reloadMs)
    }
  })

  onDestroy(() => clearTimeout(reloadTimer))
</script>

<div class="shell">
  <header class="top">
    <h1>Life&nbsp;Dashboard</h1>
    {#if agenda}
      <div class="today-label">{agenda.today.label}</div>
    {/if}
  </header>

  {#if error}
    <div class="banner">{error}</div>
  {/if}

  <main class="grid">
    <section class="col agenda-col">
      {#if config}
        <CreateEvent on:created={loadAll} />
      {/if}
      {#if agenda}
        <Agenda {agenda} />
      {:else if !error}
        <p class="muted">Laden…</p>
      {/if}
    </section>

    <aside class="col side-col">
      {#if config}
        <LogField {config} on:logged={refreshRecent} />
      {/if}
      <RecentLogs {recent} />
    </aside>
  </main>

  <footer class="bottom">
    <span class="muted">
      {#if agenda && agenda.last_rebuild}Index bijgewerkt: {agenda.last_rebuild.replace('T', ' ').slice(0, 16)}{/if}
    </span>
    <div class="bottom-right">
      <SpeakQR />
      <button class="ghost" on:click={rebuildIndex} disabled={rebuilding}>
        {rebuilding ? 'Herbouwen…' : 'Index herbouwen'}
      </button>
    </div>
  </footer>
</div>

<style>
  .shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    padding: clamp(16px, 3vw, 40px);
    gap: var(--gap);
  }

  .top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--gap);
    flex-wrap: wrap;
  }
  .top h1 {
    font-size: 1.9rem;
    letter-spacing: 0.5px;
  }
  .today-label {
    font-size: 1.4rem;
    color: var(--accent);
    text-transform: capitalize;
  }

  .banner {
    background: rgba(255, 107, 107, 0.12);
    border: 1px solid var(--danger);
    color: var(--text);
    padding: 14px 18px;
    border-radius: var(--radius);
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--gap);
    flex: 1;
  }
  /* Twee kolommen op breed (TV, desktop); één kolom op smal (telefoon). */
  @media (min-width: 900px) {
    .grid {
      grid-template-columns: 1.4fr 1fr;
      align-items: start;
    }
  }

  .col { min-width: 0; }
  .side-col {
    display: flex;
    flex-direction: column;
    gap: var(--gap);
  }

  .bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--gap);
    border-top: 1px solid var(--border);
    padding-top: 16px;
    font-size: 0.85rem;
    flex-wrap: wrap;
  }
  .bottom-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .ghost {
    min-height: 48px;
    padding: 8px 18px;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    background: var(--surface);
  }
  .ghost:hover { color: var(--text); border-color: var(--accent); }
  .ghost:disabled { opacity: 0.5; cursor: default; }
</style>
