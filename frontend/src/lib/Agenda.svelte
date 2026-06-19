<script>
  import { api } from './api.js'

  export let agenda

  // Per event de briefing-status: { loading, text, configured, error }.
  let briefings = {}
  let openId = null

  async function toggle(ev) {
    if (openId === ev.id) {
      openId = null
      return
    }
    openId = ev.id
    if (!briefings[ev.id]) {
      briefings = { ...briefings, [ev.id]: { loading: true } }
      try {
        const b = await api.briefing(ev.id)
        briefings = { ...briefings, [ev.id]: { loading: false, text: b.text, configured: b.configured } }
      } catch (e) {
        briefings = { ...briefings, [ev.id]: { loading: false, error: 'Briefing kon niet geladen worden.' } }
      }
    }
  }
</script>

<h2 class="section-title">Vandaag</h2>

{#if agenda.today.events.length === 0}
  <p class="empty">Niets gepland vandaag.</p>
{:else}
  <ul class="cards">
    {#each agenda.today.events as ev (ev.id)}
      <li>
        <button class="card" class:open={openId === ev.id} on:click={() => toggle(ev)}>
          <span class="time">{ev.time_label}</span>
          <span class="body">
            <span class="title-row">
              <span class="title">{ev.summary}</span>
              <span class="chev" aria-hidden="true">{openId === ev.id ? '▾' : '▸'}</span>
            </span>
            {#if ev.location}<span class="loc">{ev.location}</span>{/if}
          </span>
        </button>

        {#if openId === ev.id}
          <div class="briefing">
            {#if briefings[ev.id] && briefings[ev.id].loading}
              <span class="muted">Briefing laden…</span>
            {:else if briefings[ev.id] && briefings[ev.id].error}
              <span class="muted">{briefings[ev.id].error}</span>
            {:else if briefings[ev.id]}
              <p>{briefings[ev.id].text}</p>
            {/if}
          </div>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<h2 class="section-title week">Deze week</h2>

{#if agenda.week.days.length === 0}
  <p class="empty">Geen afspraken meer deze week.</p>
{:else}
  <ul class="week-list">
    {#each agenda.week.days as day (day.date)}
      <li class="week-day">
        <span class="week-date">{day.label}</span>
        <ul class="week-events">
          {#each day.events as ev (ev.id)}
            <li><span class="w-time">{ev.time_label}</span> <span class="w-title">{ev.summary}</span></li>
          {/each}
        </ul>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .section-title {
    font-size: 1.5rem;
    margin-bottom: 12px;
    color: var(--text);
  }
  .section-title.week {
    margin-top: 32px;
    color: var(--muted);
    font-size: 1.2rem;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .empty { color: var(--muted); }

  ul { list-style: none; margin: 0; padding: 0; }

  .cards { display: flex; flex-direction: column; gap: 14px; }

  .card {
    width: 100%;
    min-height: var(--tap-min);
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 4px 18px;
    text-align: left;
    padding: 18px 22px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 5px solid var(--accent);
    border-radius: var(--radius);
    transition: background 0.12s ease, border-color 0.12s ease;
  }
  .card:hover { background: var(--surface-2); }
  .card.open { border-color: var(--accent); background: var(--surface-2); }

  .time {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .body { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
  }
  .title { font-size: 1.3rem; font-weight: 600; min-width: 0; }
  .loc { color: var(--muted); font-size: 0.95rem; }
  .chev { color: var(--muted); font-size: 1.3rem; flex: none; }

  .briefing {
    margin-top: -4px;
    padding: 16px 22px 18px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 var(--radius) var(--radius);
  }
  .briefing p { margin: 0; line-height: 1.5; }

  .week-list { display: flex; flex-direction: column; gap: 14px; }
  .week-day {
    display: grid;
    grid-template-columns: 7rem 1fr;
    gap: 12px;
    padding: 12px 0;
    border-top: 1px solid var(--border);
  }
  .week-date { color: var(--accent); font-weight: 600; text-transform: capitalize; }
  .week-events { display: flex; flex-direction: column; gap: 6px; }
  .w-time { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 8px; }
</style>
