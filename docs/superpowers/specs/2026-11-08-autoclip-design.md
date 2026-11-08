# AutoClip — Design Spec

**Date:** 2026-11-08
**Auteur:** dillan@medialog.fr
**Statut:** Approuvé (brainstorming) → prêt pour le plan d'implémentation

---

## 1. Objectif

Pipeline **semi-automatique** qui transforme des vidéos longues de tiers (streams Twitch/Kick, vidéos YouTube, fichiers locaux) en clips courts verticaux (9:16, sous-titrés) et les publie sur **TikTok, Instagram Reels et YouTube Shorts** après validation humaine.

Flux retenu : **l'outil génère les clips → l'humain valide/édite/planifie un batch → le worker poste automatiquement aux horaires prévus**, avec repli manuel si une publication échoue.

### Responsabilité éditoriale

Le contenu source appartient à des tiers. L'utilisateur est seul responsable de disposer du droit de clipper/reposter chaque source (permission du créateur, programme de clippeurs officiel, etc.). L'outil ne vérifie pas les droits.

---

## 2. Décisions actées (brainstorming)

| Sujet | Décision |
|---|---|
| Source du contenu | Tiers : Twitch/Kick + YouTube + fichiers locaux |
| Niveau d'automatisation | Semi-auto planifié (validation d'un batch, puis post auto aux meilleurs horaires) |
| Mécanisme de publication | **Playwright** (gratuit), repli manuel par l'utilisateur |
| Stratégie de construction | **Fork d'OpenShorts** + ajout d'un module de posting Playwright |
| Stack | Python/FastAPI + dashboard React (fournis par OpenShorts) |
| LLM détection de moments | **Ollama local** (gratuit) |
| Transcription | faster-whisper **local sur GPU** |
| Machine | PC Linux local avec GPU NVIDIA, Playwright en mode visible pour les logins |
| Volume | 1 compte par plateforme, petit volume (quelques clips/jour) |
| Nom du projet | **AutoClip** |

---

## 3. Périmètre

### Dans le scope
- Ingestion des 3 types de source via `yt-dlp` (gère Twitch, Kick, YouTube) + fichiers locaux.
- Transcription locale GPU (faster-whisper).
- Détection des moments forts via **Ollama** (serveur local compatible OpenAI).
- Rendu des clips 9:16 avec sous-titres + hooks (modules OpenShorts).
- Dashboard de review : validation, édition de légende/hashtags, choix d'horaire.
- **Module de posting Playwright** (TikTok, Instagram Reels, YouTube Shorts).
- Worker de planification qui déclenche les publications dues.
- Repli manuel : tout clip reste téléchargeable ; un échec de post est signalé.

### Hors scope (YAGNI)
- **Multi-comptes** par plateforme — mais le module poster accepte un paramètre `profile` pour l'ajouter plus tard sans refonte.
- Analytics / suivi de performance des posts.
- B-roll contextuel, voix IA, doublage (fonctions OpenShorts laissées désactivées).
- Tout le dossier `cloud/` d'OpenShorts (**licence commerciale** — on n'utilise **que le cœur MIT**).

---

## 4. Architecture

### 4.1 Réutilisé vs écrit

| Brique | Origine | Action |
|---|---|---|
| Ingestion Twitch/YT/local | OpenShorts (`yt_dlp`, `twitch_signals.py`, `yt_clients.py`) | réutilisé / configuré |
| Transcription | OpenShorts `transcribe_backends.py` (faster-whisper GPU) | réutilisé |
| Détection moments | OpenShorts `llm_backend.py` → **Ollama** (`LLM_PROVIDER=openai`, base_url local) | configuré |
| Recadrage 9:16 + sous-titres + hooks | OpenShorts (`reframe_v2.py`, `subtitles.py`, `hooks.py`) | réutilisé |
| Dashboard review + planification | OpenShorts (React + FastAPI) | réutilisé / adapté |
| **Module posting** | **nouveau code `poster/`** | **écrit** |
| **Worker planification → poster** | **nouveau câblage** | **écrit** |

> Note licence : le cœur OpenShorts est MIT. Le dossier `cloud/` est source-available sous licence commerciale (self-host personnel uniquement) — AutoClip n'en dépend pas et ne doit pas l'importer.

### 4.2 Composants que nous écrivons

#### `poster/` — publication Playwright
- **Sessions persistantes** : un répertoire de profil navigateur par plateforme/compte sous `profiles/<platform>/` (stocke cookies + storage state). Login une seule fois.
- **Commande de login** : `autoclip login <platform>` ouvre un navigateur **visible** (headful) ; l'utilisateur se connecte manuellement ; la session est sauvegardée (`storage_state`).
- **Adaptateurs** — un par plateforme, interface commune :
  - `poster/tiktok.py`
  - `poster/instagram.py`
  - `poster/youtube.py`
  - Interface commune `Poster` :
    ```
    class Poster(Protocol):
        name: str
        def post(self, clip_path: str, caption: str, *,
                 profile: str = "default", dry_run: bool = False) -> PostResult
    ```
  - Chaque adaptateur : ouvre la page d'upload → injecte le fichier → remplit légende/hashtags → (si `dry_run=False`) clique "Publier" → renvoie `PostResult(ok, url|error, screenshot_path)`.
- **Extensibilité multi-comptes** : le paramètre `profile` sélectionne le répertoire de session → ajouter un compte = ajouter un profil, zéro changement de code.

#### `scheduler/` — file + worker
- **Persistance : SQLite** (nouveau fichier `autoclip.db`), mono-utilisateur, local. **On n'utilise PAS** le Postgres de `cloud/models.py` (licence commerciale + multi-tenant inutile ici).
- **File `post_queue`** (table SQLite) : `(id, job_id, clip_index, clip_path, platform, profile, caption, scheduled_at, status, attempts, last_error, posted_url, created_at)`.
  - États : `pending → in_progress → posted` | `failed` | `needs_manual`.
- **Worker** (nouveau process standalone) : OpenShorts n'a **aucun** scheduler en self-host (il déléguait à Upload-Post) → on l'écrit entièrement. Boucle qui interroge SQLite pour les posts dus (`scheduled_at <= now` ET `status=pending`), appelle l'adaptateur Playwright, met à jour l'état (APScheduler ou simple boucle `asyncio.sleep`).
- **Approbation depuis le dashboard** : valider un clip insère une ligne `post_queue` par (clip, plateforme) avec l'horaire choisi.

### 4.3 Points d'intégration tranchés (inspection OpenShorts)

> Références vérifiées dans `_ref_openshorts/`.

| Point | Fait vérifié | Décision AutoClip |
|---|---|---|
| **Seam de publication** | Toute publication passe par **une seule fonction** `post_to_socials()` (`app.py:6319`, endpoint `POST /api/social/post`), qui appelle Upload-Post. | **Remplacer le corps** de cette fonction : au lieu d'appeler Upload-Post, insérer dans `post_queue`. Signature + modèle `SocialPostRequest` **inchangés**. |
| **Dashboard** | Le front React appelle déjà `/api/social/post` avec `scheduled_date`+`timezone`, et lit `/api/social/scheduled`, `/api/social/post-status/{id}`, `DELETE /api/social/scheduled/{id}`. | **Front quasi inchangé.** On ré-implémente ces 3-4 endpoints contre SQLite au lieu d'Upload-Post. |
| **Clip & métadonnées** | Fichier en `OUTPUT_DIR/{job_id}/{file}` ; métadonnées dans `job['result']['clips'][i]` avec légendes déjà générées par plateforme (`video_description_for_tiktok`, `..._instagram`, `video_title_for_youtube_short`). | On réutilise ces légendes comme valeurs par défaut éditables. |
| **Persistance jobs** | En self-host, jobs **en mémoire** (`jobs[job_id]`, `app.py:1332`), pas de DB. | Notre SQLite ne stocke que la file de posting (indépendant des jobs). |
| **Repli manuel (UI)** | — | **Nouvelle section « À poster à la main »** dans le dashboard : liste les lignes `status=needs_manual` avec aperçu, légende pré-remplie, bouton télécharger. (Décision validée : vraie file UI, pas simple notif.) |
| **LLM local** | `llm_backend.py` lit `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. La détection **texte** (scoring du transcript) part sur Ollama ; les passes **vision** (`get_visual_clips`) nécessitent Gemini et **se dégradent proprement** sans clé. | **Full-free = détection basée transcript via Ollama.** Qualité à évaluer ; Gemini free tier reste activable en option. |

---

## 5. Flux de données

```
Source (URL Twitch/Kick/YouTube ou fichier local)
  → yt-dlp : téléchargement
  → faster-whisper (GPU) : transcription + timestamps mot-à-mot
  → Ollama (LLM local) : détection des moments forts
  → rendu : clips 9:16 + sous-titres + hook overlay
  → 📋 DASHBOARD : l'utilisateur valide, édite légende/hashtags, choisit l'horaire par plateforme
  → insertion dans post_queue (une ligne par (clip, plateforme))
  → worker : à scheduled_at → adaptateur Playwright de la plateforme
  → ✅ posted (posted_url enregistrée)
     ⚠️ failed/needs_manual → clip reste téléchargeable + notification
```

---

## 6. Gestion d'erreurs

| Cas | Comportement |
|---|---|
| Sélecteur cassé / UI du site modifiée | N retries (backoff), **capture d'écran** sauvée dans `logs/`, statut `failed` → repli manuel |
| Session expirée (mur de login détecté) | Pause de la file pour cette plateforme + notification de relancer `autoclip login <platform>` ; statut `needs_manual` |
| Échec yt-dlp (source indispo/privée) | Erreur remontée dans le statut de job du dashboard |
| Upload timeout / publication lente | Attente bornée + polling de l'état, puis retry |
| Anti-ban (petit volume) | Jitter aléatoire entre posts, publications espacées, navigateur visible (comportement humain) |

---

## 7. Stratégie de tests

- **Mode `--dry-run`** par adaptateur : exécute tout le flux **sauf le clic final "Publier"**, et sauvegarde une capture de l'état prêt-à-poster. C'est la **vérification principale** des adaptateurs (impossible de tester automatiquement contre les vrais sites).
- **Tests unitaires** du `scheduler/` : sélection des posts dus, transitions d'état, logique de retry, passage en `needs_manual` — avec un `Poster` mocké.
- **Smoke test** de bout en bout : 1 fichier local court → clip généré → dry-run TikTok → capture produite.

---

## 8. Configuration

- `.env` (noms de variables **vérifiés** dans OpenShorts) :
  - `LLM_PROVIDER=openai`, `LLM_BASE_URL=http://localhost:11434/v1` (Ollama), `LLM_MODEL=llama3.1:8b` (→ `qwen2.5:14b` si qualité insuffisante), `LLM_API_KEY=` (ignoré par Ollama), `LLM_TIMEOUT=600`
  - `TRANSCRIBE_BACKEND=whisper`, taille de modèle Whisper, flags GPU
  - `GEMINI_API_KEY=` (optionnel : active les passes vision ; vide = détection texte seule, 100% gratuit)
  - chemins `PROFILES_DIR`, `LOGS_DIR`, `AUTOCLIP_DB` (SQLite)
- `profiles/<platform>/` : sessions Playwright (git-ignoré, contient des cookies de session → **secret**).
- Prérequis système : Ollama installé + un modèle tiré, ffmpeg, pilotes NVIDIA/CUDA, navigateurs Playwright (`playwright install`).

### Sécurité
- `profiles/` (cookies de session) et `.env` sont **git-ignorés** et ne doivent jamais être committés ni partagés.
- Aucune donnée de carte bancaire n'est manipulée par ce projet.

---

## 9. Arborescence cible (haut niveau)

```
clippping/
├── _ref_openshorts/        # fork OpenShorts (base, MIT core uniquement)
├── poster/                 # NOUVEAU : adaptateurs Playwright
│   ├── base.py             # Poster protocol + PostResult
│   ├── tiktok.py
│   ├── instagram.py
│   ├── youtube.py
│   └── login.py            # commande de login (headful)
├── scheduler/              # NOUVEAU : file + worker
│   ├── queue.py            # modèle post_queue SQLite + transitions d'état
│   └── worker.py           # process standalone qui poste les clips dus
├── autoclip.db             # SQLite (file post_queue) (git-ignoré)
├── profiles/               # sessions Playwright (git-ignoré)
├── logs/                   # captures d'écran d'échec (git-ignoré)
├── docs/superpowers/specs/ # ce document
└── .env                    # config (git-ignoré)
```

> Point de câblage **tranché** (voir §4.3) : on remplace le corps de `post_to_socials()` (`app.py:6319`) pour enfiler dans `post_queue` (SQLite) au lieu d'appeler Upload-Post, et on ré-implémente `/api/social/scheduled` + `/api/social/post-status/{id}` contre SQLite. Le front React reste quasi inchangé (sauf ajout de la section « À poster à la main »).

---

## 10. Risques & points ouverts

**Tranché après inspection (§4.3) :** seam d'intégration (`post_to_socials` / `app.py:6319`), persistance (SQLite, pas de couplage `cloud/`), repli manuel (vraie section UI), vars Ollama vérifiées.

**Risques restants (assumés, mitigés) :**
1. **Fragilité Playwright** : les UIs TikTok/IG/YT changent souvent → adaptateurs isolés + dry-run + captures pour diagnostic rapide. Risque accepté, mitigé par le repli manuel.
2. **CGU des plateformes** : l'automatisation navigateur est contre les CGU → risque de ban assumé, atténué par petit volume + comportement humain.
3. **Ollama & qualité de détection** : la détection locale (texte seul, sans vision Gemini) peut être moins fine → modèle à évaluer pendant l'implémentation (`llama3.1:8b` → `qwen2.5:14b`). Gemini free tier reste activable si besoin.
