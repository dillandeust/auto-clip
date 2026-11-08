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
- **File `post_queue`** (table DB) : `(id, clip_path, platform, profile, caption, scheduled_at, status, attempts, last_error, posted_url)`.
  - États : `pending → in_progress → posted` | `failed` | `needs_manual`.
- **Worker** : interroge périodiquement la file pour les posts dus (`scheduled_at <= now` et `status=pending`), appelle l'adaptateur Playwright correspondant, met à jour l'état. Réutilise le mécanisme de planification d'OpenShorts si présent ; sinon APScheduler.
- **Approbation depuis le dashboard** : valider un clip dans l'UI insère une/des lignes dans `post_queue` avec l'horaire choisi.

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

- `.env` :
  - `LLM_PROVIDER=openai`, `OPENAI_BASE_URL=http://localhost:11434/v1` (Ollama), `OPENAI_MODEL=<modèle>`
  - `TRANSCRIBE_BACKEND=whisper`, taille de modèle Whisper, flags GPU
  - chemins `PROFILES_DIR`, `LOGS_DIR`, DB
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
│   ├── queue.py            # modèle post_queue + transitions d'état
│   └── worker.py
├── profiles/               # sessions Playwright (git-ignoré)
├── logs/                   # captures d'écran d'échec (git-ignoré)
├── docs/superpowers/specs/ # ce document
└── .env                    # config (git-ignoré)
```

> La structure exacte d'intégration (fork autonome vs module à côté d'OpenShorts, point de câblage du dashboard vers `post_queue`) sera tranchée dans le plan d'implémentation après inspection du code d'OpenShorts (schéma DB, système de planification existant, API FastAPI du dashboard).

---

## 10. Risques & points ouverts (à lever dans le plan)

1. **Fragilité Playwright** : les UIs TikTok/IG/YT changent souvent → adaptateurs isolés + dry-run + captures pour diagnostic rapide. Risque accepté, mitigé par le repli manuel.
2. **Intégration dashboard** : OpenShorts planifie via Upload-Post ; il faut identifier le point exact où brancher `post_queue` + le worker Playwright à la place. À confirmer par lecture du code.
3. **CGU des plateformes** : l'automatisation navigateur est contre les CGU → risque de ban assumé, atténué par petit volume + comportement humain.
4. **Ollama & qualité de détection** : la détection locale peut être moins fine que Gemini → modèle à choisir/évaluer pendant l'implémentation.
