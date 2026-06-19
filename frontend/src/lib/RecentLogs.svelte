<script>
  export let recent = []

  // Subtiele kleur per thema; onbekende thema's vallen terug op 'algemeen'.
  const THEME_VARS = {
    algemeen: 'var(--t-algemeen)',
    werk: 'var(--t-werk)',
    gezondheid: 'var(--t-gezondheid)',
    idee: 'var(--t-idee)',
    relatie: 'var(--t-relatie)',
  }
  function themeColor(t) {
    return THEME_VARS[t] || 'var(--t-algemeen)'
  }
</script>

<section class="recent">
  <h2 class="title">Recente logs</h2>

  {#if recent.length === 0}
    <p class="muted">Nog geen logs.</p>
  {:else}
    <ul>
      {#each recent as log, i (log.date + '-' + i)}
        <li>
          <span class="date">{log.date.slice(5)}</span>
          <span class="text">{log.text}</span>
          <span class="chip" style="--c: {themeColor(log.theme)}">{log.theme}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .recent {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
  }
  .title { font-size: 1.3rem; margin-bottom: 14px; }

  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
  li {
    display: grid;
    grid-template-columns: 3.4rem 1fr auto;
    align-items: start;
    gap: 12px;
    padding: 12px 0;
    border-top: 1px solid var(--border);
  }
  li:first-child { border-top: none; }

  .date {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    font-size: 0.95rem;
    padding-top: 2px;
  }
  .text { line-height: 1.4; }

  .chip {
    align-self: start;
    font-size: 0.8rem;
    color: var(--c);
    border: 1px solid var(--c);
    border-radius: 999px;
    padding: 2px 12px;
    white-space: nowrap;
    opacity: 0.92;
  }
</style>
