# Intégration AutoClip ↔ OpenShorts

Le fork OpenShorts vit dans `_ref_openshorts/` (git-ignoré par notre repo, il a son
propre `.git`). Nos modifications de `_ref_openshorts/app.py` sont donc versionnées
ici sous forme de **patch** reproductible.

## Ce que fait le patch (`autoclip_openshorts.patch`)

Remplace la brique de publication payante (Upload-Post) par notre file SQLite
`post_queue` + worker Playwright :

1. **Bloc d'import AutoClip** (avant `class SocialPostRequest`) : charge la config,
   ouvre la connexion SQLite partagée (chemin résolu en **absolu** via la racine du
   package, pour que serveur et worker tapent le même fichier), expose `_ac_now()`.
2. **`POST /api/social/post`** (`post_to_socials`) : au lieu d'envoyer à Upload-Post,
   enfile une ligne par plateforme dans `post_queue` et renvoie `{request_id, queued_ids, status:"queued"}`.
3. **`GET /api/social/post-status/{request_id}`** : lit le statut d'une ligne `post_queue`.
4. **`GET /api/social/scheduled`** : liste les lignes `pending` de `post_queue`.
5. **`GET /manual` + `GET /api/social/manual`** : page de repli pour les clips en `needs_manual`.

Le front React d'OpenShorts n'a pas besoin d'être modifié (mêmes endpoints, mêmes formes de réponse).

## Appliquer le patch sur un clone frais d'OpenShorts

```bash
git clone --depth 1 https://github.com/mutonby/openshorts.git _ref_openshorts
cd _ref_openshorts
git apply ../integration/autoclip_openshorts.patch
```

Régénérer le patch après de nouvelles modifs : `git -C _ref_openshorts diff > integration/autoclip_openshorts.patch`.

## Dépendances à épingler (compat)

- **`av==13.1.0`** : faster-whisper 1.2.1 appelle `av.open(..., metadata_errors="ignore")`,
  paramètre supprimé par PyAV ≥ 14. Le `requirements.txt` du fork ne fige pas `av`, donc pip
  installe la 19.x → `TypeError: open() got an unexpected keyword argument 'metadata_errors'`
  à la transcription. Forcer `pip install "av==13.1.0"` dans le `.venv`.

## Limites connues (hors scope)

- Les endpoints **analytics / historique / gestion de comptes** et le
  `DELETE /api/social/scheduled/{job_id}` appellent encore Upload-Post et resteront
  inactifs sans clé (non utilisés par le flux semi-auto).
- L'**autopilot** d'OpenShorts (fonction cloud, `app.py` ~l.7533) poste directement
  via Upload-Post et **contourne notre file** : ne pas l'activer (laisser `BILLING_ENABLED` désactivé).
- Le serveur FastAPI et le `autoclip worker` doivent tourner dans le **même venv**
  (`.venv`) pour partager le package et le fichier SQLite. Lancer `autoclip worker`
  depuis la racine du projet.
