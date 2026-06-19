<script>
  import { onMount } from 'svelte'
  import QRCode from 'qrcode'

  let qrDataUrl = ''
  let speakUrl = ''

  onMount(async () => {
    // Localhost mag HTTP, al het andere (NAS, LAN) forceert HTTPS voor microfoon.
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    const proto = isLocal ? window.location.protocol : 'https:'
    speakUrl = proto + '//' + window.location.host + '/speak.html'
    try {
      qrDataUrl = await QRCode.toDataURL(speakUrl, {
        width: 160,
        margin: 1,
        color: { dark: '#f4f4f5', light: '#000000' },
      })
    } catch (e) {
      console.error('QR genereren mislukt:', e)
    }
  })
</script>

{#if qrDataUrl}
  <div class="qr-wrap" title="Scan voor spraaklog op je telefoon">
    <img class="qr-img" src={qrDataUrl} alt="QR code naar spraaklog" />
    <span class="qr-label">Log via telefoon</span>
  </div>
{/if}

<style>
  .qr-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    opacity: 0.5;
    transition: opacity 0.3s;
  }
  .qr-wrap:hover {
    opacity: 0.85;
  }
  .qr-img {
    width: 64px;
    height: 64px;
    border-radius: 8px;
  }
  .qr-label {
    font-size: 0.6rem;
    color: var(--muted);
    white-space: nowrap;
  }
</style>
