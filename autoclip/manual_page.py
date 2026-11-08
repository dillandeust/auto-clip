MANUAL_HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>AutoClip — À poster à la main</title>
<style>
 body{font-family:system-ui;margin:2rem;background:#111;color:#eee}
 .card{border:1px solid #333;border-radius:8px;padding:1rem;margin:1rem 0;background:#1b1b1b}
 .platform{display:inline-block;padding:.1rem .5rem;border-radius:4px;background:#444;font-size:.8rem}
 .err{color:#f88;font-size:.85rem}
 textarea{width:100%;height:4rem;background:#000;color:#eee;border:1px solid #333}
 a.btn{display:inline-block;margin-top:.5rem;padding:.4rem .8rem;background:#2563eb;color:#fff;border-radius:6px;text-decoration:none}
</style></head><body>
<h1>À poster à la main</h1>
<p>Clips dont la publication automatique a échoué. Télécharge, colle la légende, publie manuellement.</p>
<div id="list">Chargement…</div>
<script>
async function load(){
  const r = await fetch('/api/social/manual');
  const d = await r.json();
  const el = document.getElementById('list');
  if(!d.items.length){ el.innerHTML = '<p>Rien à poster à la main. 🎉</p>'; return; }
  el.innerHTML = d.items.map(it => `
    <div class="card">
      <span class="platform">${it.platform}</span>
      <p class="err">Erreur: ${it.last_error||''}</p>
      <textarea readonly>${(it.caption||'').replace(/</g,'&lt;')}</textarea>
      <a class="btn" href="${it.download_url}" download>Télécharger le clip</a>
    </div>`).join('');
}
load();
</script></body></html>"""
