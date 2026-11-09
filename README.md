# AutoClip

Clipping automatique (Twitch/Kick/YouTube/fichiers) + publication **semi-auto planifiée**
(TikTok/Instagram/YouTube) via Playwright, basé sur un fork d'[OpenShorts](https://github.com/mutonby/openshorts) (MIT).

Le pipeline de clipping (ingestion → transcription → détection de moments → rendu 9:16 +
sous-titres → dashboard de review) est fourni par OpenShorts. AutoClip remplace sa brique
de publication payante par une **file SQLite + un worker Playwright gratuit**, avec repli manuel.

## Architecture

| Brique | Origine |
|---|---|
| Ingestion / transcription / détection moments / rendu / dashboard | OpenShorts (`_ref_openshorts/`) |
| Détection de moments | **Ollama local** (LLM gratuit) |
| File de publication (`post_queue`, SQLite) + worker + adaptateurs Playwright | package `autoclip/` |
| Seam d'intégration dans `app.py` | `integration/autoclip_openshorts.patch` |

## Installation

```bash
# 1. Cloner OpenShorts et appliquer le patch d'intégration
git clone --depth 1 https://github.com/mutonby/openshorts.git _ref_openshorts
git -C _ref_openshorts apply integration/autoclip_openshorts.patch

# 2. Environnement Python (venv) + AutoClip + Playwright
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && python -m playwright install chromium
pip install -r _ref_openshorts/requirements.txt   # deps du backend OpenShorts

# 3. ffmpeg + pilotes NVIDIA/CUDA (voir doc système)

# 4. Ollama (détection de moments, gratuit)
ollama serve
ollama pull llama3.1:8b        # ou qwen2.5:14b si la qualité ne suffit pas

# 5. Config
cp .env.example .env           # config AutoClip (DB, chemins, headless)
#   configurer aussi _ref_openshorts/.env (LLM_*, voir .env.example)
```

## Connexion aux plateformes (une fois)

Ouvre un navigateur visible ; connecte-toi, la session est sauvegardée dans `profiles/`.

```bash
autoclip login tiktok
autoclip login instagram
autoclip login youtube
```

## Usage quotidien

```bash
# Terminal 1 — backend (script qui exporte LD_LIBRARY_PATH pour Whisper GPU)
./run_backend.sh

# Terminal 2 — dashboard (script qui règle le proxy /api -> localhost:8000)
./run_dashboard.sh

# Terminal 3 — worker de publication (depuis la RACINE du projet)
.venv/bin/autoclip worker
```

> **Important** : lancer le dashboard via `./run_dashboard.sh` (et non `npm run dev` nu) :
> le proxy Vite cible par défaut `http://backend:8000` (nom de service docker, injoignable
> sur l'hôte) → le dashboard n'atteint pas l'API et affiche "required api keys missing".
> Le script force `VITE_PROXY_TARGET=http://localhost:8000`.
>
> Si tu restes en CPU (pas de GPU), `cd _ref_openshorts && ../.venv/bin/uvicorn app:app --port 8000` suffit (le `LD_LIBRARY_PATH` n'est utile que pour Whisper CUDA).

1. Dans le dashboard : colle une URL (VOD Twitch/YouTube) ou un fichier → les clips sont générés.
2. Valide les clips, édite légende/hashtags, coche les plateformes, choisis l'horaire, planifie.
3. Le worker publie les clips dus. Les échecs apparaissent sur **http://localhost:8000/manual**
   (clip téléchargeable + légende pré-remplie pour poster à la main).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q      # file + worker + config + enqueue (déterministe)
```

Les adaptateurs Playwright se vérifient en **dry-run** sur la vraie machine (ils font tout
sauf le clic « Publier » et sauvent une capture dans `logs/`), ex. :

```bash
python -c "from autoclip.config import load; from autoclip.poster.tiktok import TikTokPoster; \
print(TikTokPoster(load()).post('/chemin/clip.mp4', 'Test #fyp', dry_run=True))"
```

## GPU (Whisper CUDA)

Transcription sur GPU : drivers NVIDIA + libs `nvidia-cublas-cu12` et `nvidia-cudnn-cu12` dans le
`.venv`, et `_ref_openshorts/.env` en `WHISPER_DEVICE=cuda WHISPER_COMPUTE=float16 WHISPER_MODEL=small`.
Le backend DOIT alors être lancé via **`./run_backend.sh`** (il exporte le `LD_LIBRARY_PATH` vers ces libs).
Le reste (YOLO/mediapipe) reste en CPU (torch CPU), volontairement, pour éviter la contention VRAM
avec Ollama sur une carte 4 Go.

## Limites

- **Automatisation navigateur = contre les CGU** des plateformes (risque de ban ; petit volume conseillé).
- Les **sélecteurs Playwright** peuvent nécessiter un ajustement si une plateforme change son UI
  (les captures d'erreur sont dans `logs/`).
- **Droits sur le contenu source** : responsabilité de l'utilisateur.
- Serveur et worker doivent tourner dans le **même venv** et partager le fichier SQLite ; voir `integration/README.md`.
