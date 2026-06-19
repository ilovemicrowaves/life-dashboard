<script>
  import { createEventDispatcher } from 'svelte'
  import { api } from './api.js'

  export let config

  const dispatch = createEventDispatcher()

  // --- Log invoer ---
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

  // --- Spraakherkenning ---
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  let recognition = null
  let listening = false
  let speechSupported = !!SpeechRecognition
  let speechError = ''
  let finalTranscript = ''  // accumulatie over meerdere utterances

  function initRecognition() {
    if (!SpeechRecognition) return
    const r = new SpeechRecognition()
    r.lang = 'nl-NL'
    r.interimResults = true
    r.continuous = true   // blijft luisteren tot gebruiker stopt — ook bij 5+s stilte

    r.onresult = (event) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalTranscript += result[0].transcript + ' '
        } else {
          interim += result[0].transcript
        }
      }
      // Toon accumulatie + live interim.
      text = (finalTranscript + interim).trim()
    }

    r.onerror = (event) => {
      listening = false
      if (event.error === 'not-allowed') {
        speechError = 'Microfoon niet toegestaan. Controleer browser-rechten.'
      } else if (event.error === 'no-speech') {
        // Niet meteen als fout tonen — wacht op volgende poging.
        if (!finalTranscript.trim()) {
          speechError = 'Geen spraak gedetecteerd. Blijf praten, of klik om te stoppen.'
        }
      } else if (event.error === 'audio-capture') {
        speechError = 'Geen microfoon gevonden.'
      } else if (event.error === 'network') {
        speechError = 'Netwerkfout bij spraakherkenning.'
      } else if (event.error === 'aborted') {
        // Normaal — gebruiker stopte zelf.
        speechError = ''
      } else {
        speechError = `Spraakfout: ${event.error}`
      }
      if (event.error !== 'no-speech') {
        recognition = null
      }
    }

    r.onend = () => {
      listening = false
      recognition = null
    }

    return r
  }

  function toggleSpeech() {
    if (listening) {
      // Stop actieve herkenning. Laat opgebouwde tekst staan.
      if (recognition) {
        recognition.stop()
        recognition = null
      }
      listening = false
      return
    }

    speechError = ''
    finalTranscript = ''
    recognition = initRecognition()
    if (!recognition) return

    try {
      recognition.start()
      listening = true
    } catch (e) {
      speechError = 'Kon spraakherkenning niet starten.'
      listening = false
      recognition = null
    }
  }
</script>

<section class="logfield">
  <h2 class="title">Log</h2>

  <div class="input-row">
    <input
      class="input"
      type="text"
      bind:value={text}
      on:keydown={onKeydown}
      placeholder={listening ? '● Luistert… spreek nu' : config.logPlaceholder}
      aria-label="Logregel"
      maxlength="2000"
    />

    {#if speechSupported}
      <button
        class="mic"
        class:listening
        on:click={toggleSpeech}
        aria-label={listening ? 'Stop spraakherkenning' : 'Spreek je log in'}
        title={listening ? 'Stop' : 'Spreek in'}
      >
        {#if listening}
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="8" y="1" width="4" height="12" rx="2" fill="currentColor" />
            <path d="M12 17v4M8 21h8" />
            <circle cx="12" cy="12" r="3" fill="none" />
          </svg>
        {:else}
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        {/if}
      </button>
    {/if}
  </div>

  {#if speechError}
    <div class="speech-error" role="alert">{speechError}</div>
  {/if}

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

  .input-row {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .input {
    flex: 1;
    min-height: var(--tap-min);
    padding: 14px 18px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 1.15rem;
    transition: border-color 0.2s;
  }
  .input::placeholder { color: var(--muted); }
  .input:focus { border-color: var(--accent); outline: none; }

  /* --- Mic-knop --- */
  .mic {
    flex-shrink: 0;
    width: var(--tap-min);
    height: var(--tap-min);
    border-radius: 50%;
    background: var(--bg);
    border: 2px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    transition: all 0.2s ease;
  }
  .mic:hover {
    border-color: var(--accent);
    color: var(--accent);
  }
  .mic:focus-visible {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }

  /* Luister-status: pulserende rode ring. */
  .mic.listening {
    border-color: var(--danger);
    color: var(--danger);
    animation: mic-pulse 1.4s ease-in-out infinite;
  }
  @keyframes mic-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.5); }
    50%      { box-shadow: 0 0 0 12px rgba(255, 107, 107, 0); }
  }

  .speech-error {
    color: var(--amber);
    font-size: 0.9rem;
    padding: 0 4px;
  }

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
