# AMPTemplates-Aloft — Aloft dedicated server for AMP (Linux, Wine)

**AMP Generic Module** template to host an **Aloft** dedicated server (Astrolabe Interactive /
Funcom, co-op survival on floating islands, Early Access, up to 8 players) on Linux.
Written for TeamKit, a free French game host, on 10 Oct. 2026.
CubeCoders ships no Aloft template (checked in CubeCoders/AMPTemplates, 10 Oct. 2026).

> Résumé en français à la fin du fichier.

**Aloft is a paid game** (Steam app `1660080`). This repository contains **no game file**. There is
**no separate server app**: the dedicated server *is* the game (`Aloft.exe -batchmode -nographics
-server`), so the files come from SteamCMD with a **Steam account that owns Aloft**. Every player
also needs their own copy.

> **Status: never run against the real game.** Wine, the prefix, winetricks, the save redirection,
> the launcher, the ready line and the stop sequence were tested in a throwaway
> `cubecoders/ampbase:wine-stable` container with a stand-in Windows program (see
> *What was tested*). See *What must be checked on first start*.

## Facts this template relies on

| Point | Finding | Source |
|---|---|---|
| Server app | **none**. App `1874900`, quoted by a hosting company as "Aloft server", is the **Arma Reforger Server** | api.steamcmd.net `/v1/info/1874900` |
| Game files | app `1660080`, **Windows only** (`oslist windows`), depot `1660082` ~8.5 GB, + DLC depot `3352580` ~1.8 GB if the account owns it | api.steamcmd.net `/v1/info/1660080` |
| Anonymous download | refused: `ERROR! Failed to install app '1660080' (Missing configuration)` | SteamCMD, anonymous login, 10 Oct. 2026 |
| Developers' position | no anonymous server depot planned; the server tool ships next to the game | Pterodactyl egg README; Steam discussions (dev reply, 15 Jan 2025) |
| Create a world | `create#NAME# islandcount#normal|big|huge# corruptioncount#none|little|normal|lots|shrooms# creative#false|true# log#ERROR#`, the process exits when done | Aloft 0.3.4.23 patch notes (4 Nov 2025); official wiki |
| Load / run | `load#NAME# servername#NAME# log#ERROR# isvisible#true# privateislands#false# playercount#8# serverport#0# admin#STEAMID#…` | official wiki *Dedicated Server how-to* |
| Names | no spaces in world or server names | official wiki; egg (`alpha_num`, `alpha_dash`) |
| Players | 8 max | developer (Steam discussions) |
| Joining | in-game server list (`isvisible`) or a **room code** printed at each start and written to `ServerRoomCode.txt`; it changes at every restart | wiki; hosting docs |
| Port | **none documented**; one port given by `serverport`. A community Steam guide uses 15636 (game) and 15637 (Steam query) | egg README; Steam guide 3408123643 |
| Linux | runs under Wine: the official Pterodactyl egg does it (`yolks:wine_latest`, `winetricks mono vcrun2022 wmp11 mf`, `WINEDLLOVERRIDES=mscoree,mshtml=`) | pterodactyl/game-eggs `aloft/egg-aloft.json` |
| Saves | in the Wine prefix, `AppData/LocalLow/Astrolabe Interactive/Aloft/…` | egg README |
| Resources | ~2 GB RAM minimum, up to 4 GB; up to 2 cores; 12 GB disk | community Steam guide |

## Files

| File | Role |
|---|---|
| `aloft.kvp`, `aloft*.json`, `manifest.json` | the AMP template |
| `scripts/lancer-aloft.sh` | launcher, fetched from this repository at each Update (**the repository must be public**) |
| `verifier.py` | pre-push checks, must print `Tout est bon.` |

Instance layout: `aloft/jeu/` = game files (SteamCMD), `aloft/donnees/` = Aloft's save folder,
`aloft/.wine/` = Wine prefix (~1.5 GB), `aloft/lancer-aloft.sh`, `aloft/winetricks`,
`aloft/code-pour-rejoindre.txt` (last room code).

## Container

`cubecoders/ampbase:wine-stable` (Wine 11.0 stable from WineHQ, Debian 13, Xvfb, cabextract,
`pgrep`), **required**: the same image CubeCoders uses for Sunkenland, ASKA, Sons of the Forest or
Risk of Rain 2. No extra package is needed (checked in a throwaway container).

## Update stages

1. create `jeu/` and `donnees/`;
2. **SteamCMD** app `1660080`, `ForceDownloadPlatform: Windows`, into `jeu/`, with a Steam
   account that owns the game (`App.SteamUpdateAnonymousLogin=False`,
   `App.SteamForceLoginPrompt=True`, as CubeCoders' Risk of Rain 2 / Stardew Valley);
3. **FetchURL** `scripts/lancer-aloft.sh` from this repository;
4. **FetchURL** `winetricks`, pinned tag `20260125` (the one CubeCoders' ASKA template uses);
5. `lancer-aloft.sh preparer "composants=…"`: creates the Wine prefix if missing (`wineboot --init`
   then `wineserver -w`: without the wait, the registry is not written yet), installs the
   winetricks verbs of *Composants Windows* (default `vcrun2022`) under `xvfb-run`, links the save
   folder, and prints the `Arguments` lines of the game's own `AloftServerNoGui*.ps1` scripts so
   a change in the official options shows up in the console.

## How the server is started

AMP runs `/bin/bash lancer-aloft.sh "port=…" "monde=…" "serveur=…" …`: one quoted `key=value`
argument per setting, so an empty setting stays an argument and never shifts the others. The
launcher checks every value (French error, exit 1), then:

1. `wineserver -k` (leftovers of a killed run), prefix created if missing, save link checked;
2. **first start of a world**: `xvfb-run -a wine Aloft.exe -batchmode -nographics -server -logFile
   teamkit-creation.log create#NAME# islandcount#…# corruptioncount#…# creative#…# log#ERROR#`,
   waits for it to exit, checks that something appeared in `donnees/`, writes the marker
   `donnees/.teamkit-monde-NAME`. A world is "existing" if that marker exists or a `w_NAME` entry
   exists under `donnees/` (an imported world). **Changing the world name = a new world**; the old
   one stays;
3. `xvfb-run -a wine Aloft.exe -batchmode -nographics -server -logFile teamkit-serveur.log load#NAME#
   servername#…# log#ERROR# isvisible#…# privateislands#…# playercount#…# serverport#PORT#
   admin#ID#… [extra options]`;
4. the Unity log is followed (`tail -F`, CR removed) into the AMP console;
5. **ready line** (`Console.AppReadyRegex`): written by the launcher when a fresh
   `ServerRoomCode.txt` appears (searched in `jeu/` and `donnees/`), with the code:
   `TeamKit : Aloft est pret. Code pour rejoindre : 482913`. If no code file appears but the log
   says `Server Ready` (the egg's ready string), the launcher declares ready one minute later
   with "introuvable";
6. **stop**: AMP sends SIGTERM to the launcher, which sends SIGINT (Ctrl+C, as the egg's `^C`) to
   `Aloft.exe`, waits up to 45 s, then `wineserver -k`. `App.ExitTimeout=60`.

### Saves outside the prefix

Aloft writes to `C:\users\<user>\AppData\LocalLow\Astrolabe Interactive`. The launcher replaces
that folder by a **relative symlink to `aloft/donnees/`** (every Wine profile found: `$USER`, the
registry's `ProfileImagePath`, other `users/` folders). Saves are then visible in the AMP file
manager, and rebuilding the prefix (`rm -rf .wine`, then Update) does not lose them. If a real
folder with content is found there (the game wrote before the link), it is **moved** to
`aloft/recupere-<user>-<date>/`, never merged nor deleted, and the console says so.

### Why values are restricted

AMP writes values as they are. World name: 1-20 letters/digits (egg rule). Server name: spaces are
turned into `_` (the game refuses spaces), then only `A-Z a-z 0-9 _ -`. Admins: 17-digit
SteamID64s, separated by spaces or commas. Extra options: `key#value#` tokens only.

## Settings (French UI)

| Setting | Game option | Default |
|---|---|---|
| Port du jeu (Network tab) | `serverport` | 15636 (TCP+UDP) |
| Port de requête Steam (reserved) | none | 15637/UDP |
| Nom du monde | `create#` / `load#` | `TeamKit` |
| Nombre d'îles (creation) | `islandcount` | normal |
| Corruption (creation) | `corruptioncount` | normal |
| Mode créatif (creation) | `creative` | off |
| Nom du serveur | `servername` | `Serveur_FR_TeamKit` |
| Visible dans la liste | `isvisible` | on |
| Joueurs maximum | `playercount` (1-8) | 8 |
| Îles d'origine protégées | `privateislands` | off (game default) |
| Administrateurs (SteamID64) | `admin#…#`, repeated | empty |
| Options du jeu en plus | any `key#value#` | empty |
| Composants Windows | winetricks verbs (Update) | `vcrun2022` |

Aloft has no message-of-the-day: the server name is the only text players see.

## How players join

*Multiplayer → Join Game*: pick the server in the list (it can take 15-30 minutes to appear), or
type the **room code** shown in the AMP console (`TeamKit : Aloft est pret. Code pour rejoindre : …`)
and in `aloft/code-pour-rejoindre.txt`. The code changes at every restart. Players never type an
IP:port. Server and players must run the same game version: update the server after each patch.

## What was tested (10 Oct. 2026, throwaway containers, 2 GB, non-root user)

| Test | Result |
|---|---|
| `ampbase:wine-stable` content | Debian 13.7, wine-11.0, Xvfb, xvfb-run, xauth, cabextract, pgrep; no winetricks (downloaded at Update) |
| `wineboot --init` + `wineserver -w` | prefix ready in 9 s, 1.4-1.5 GB; Wine names the profile after `$USER` |
| winetricks `vcrun2022` | **fails without a display** (vc_redist exits 130); **works under `xvfb-run`** (~5 s) |
| Writes through the `LocalLow` symlink | land in `donnees/` |
| Launcher, stand-in `Aloft.exe` (Wine's notepad, a GUI program like Unity): preparer, creation, load, log relay with CRLF, ready line with code, SIGTERM stop | all OK; stop in 1 s, no process left |
| Launcher killed with SIGKILL | Wine processes stay; the next start's `wineserver -k` removes them |
| SIGINT / SIGTERM / SIGHUP to a Wine GUI process | all three end it |
| Anonymous SteamCMD for 1660080 | refused (Missing configuration), nothing downloaded |
| `verifier.py` | 19 launcher cases through bash; 5 deliberate errors all caught |

## What must be checked on first start

1. SteamCMD login + Steam Guard from AMP, Windows download of 1660080 (~8.5-10 GB).
2. That `Aloft.exe` really runs under Wine 11 with only `vcrun2022` (else add `mf`, as the egg).
3. The `.ps1` argument lines printed at Update (did the options change?).
4. World creation: duration, exit by itself, files under `donnees/` (is it still `w_NAME`?).
5. The real log lines (ready text, player join/leave → `Console.UserJoinRegex` for the AMP list).
6. Where `ServerRoomCode.txt` is written, and that the ready line shows the code.
7. Whether players can join with only the declared ports (bridge network), via list and code.
8. Whether Ctrl+C makes Aloft save before quitting (else rely on its autosave + AMP backups).
9. Real RAM use (the guide says ~2 GB, up to 4 GB).

## Before pushing

```
python verifier.py      # must print "Tout est bon."
```

## Sources

- Steam: api.steamcmd.net `/v1/info/1660080` and `/v1/info/1874900`; store API `appdetails?appids=1660080`;
  ISteamNews for 1660080 (patch notes 0.3.4.23 "Bloom & Blight", 0.3.4.35, 0.3.6.48).
- Official Aloft wiki: <https://aloft.wiki.gg/wiki/Dedicated_Server_how-to>.
- Pterodactyl egg: <https://eggs.pterodactyl.io/egg/games-aloft>, `pterodactyl/game-eggs` `aloft/egg-aloft.json` and README.
- XGamingServer: setup guide and troubleshooting (room code, `ServerRoomCode.txt`, list delay, `privateislands` message).
- Steam guide 3408123643 "How to Host Your Own Aloft Dedicated Server" (ports 15636/15637, requirements).
- Steam discussion "Dedicated Servers" (app 1660080): developer replies, Ubuntu + Wine + SteamCMD report.
- CubeCoders AMPTemplates: `sunkenland`, `aska`, `sons-of-the-forest`, `risk-of-rain-2` (Wine image, xvfb-run, winetricks tag).

## Credits

Aloft is © Astrolabe Interactive, published by Funcom. This repository only contains the template.

---

## Résumé en français

Template AMP pour un **serveur dédié Aloft** (îles volantes, coopération jusqu'à 8, accès
anticipé, **jeu payant**, Steam 1660080).

- **Pas de serveur à part ni de version Linux** : le serveur, c'est le jeu Windows lancé sans
  affichage, sous **Wine** dans l'image CubeCoders `ampbase:wine-stable`. L'app 1874900 citée
  par un hébergeur est en réalité le serveur d'Arma Reforger.
- **Fichiers du jeu** : SteamCMD avec un compte Steam qui **possède** Aloft (validation Steam
  Guard la première fois). Le téléchargement anonyme est refusé (essayé).
- **Monde créé au premier démarrage** (taille, corruption, créatif), puis rechargé ; changer le
  nom = nouveau monde. **Sauvegardes dans `aloft/donnees/`** (lien depuis le préfixe Wine).
- **Rejoindre** : liste des serveurs du jeu, ou **code pour rejoindre** affiché dans la console à
  chaque démarrage (il change à chaque redémarrage). Pas d'IP:port.
- **Ports** : 15636 (TCP+UDP) et 15637/UDP réservé ; aucun port officiel documenté.
- **Pas encore lancé avec le vrai jeu** : la liste des vérifications est plus haut.
- Avant de pousser : `python verifier.py` doit répondre « Tout est bon. ».
