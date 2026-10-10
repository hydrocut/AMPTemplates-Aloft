#!/bin/bash
# lancer-aloft.sh - pose par le template AMP TeamKit (telecharge a chaque Update).
#
#   lancer-aloft.sh preparer "composants=..."   prefixe Wine + composants Windows (etape d'Update)
#   lancer-aloft.sh cle=valeur ...              creation du monde si besoin, puis serveur
#                                               (ligne de commande d'AMP)
#
# Aloft n'a pas de serveur Linux : on lance le jeu Windows lui-meme (Aloft.exe en mode
# -batchmode -nographics -server) sous Wine, dans un faux ecran (xvfb-run).
# AMP passe chaque reglage sous la forme cle=valeur, entre guillemets : un reglage vide
# reste un argument "cle=" et ne decale jamais les autres. Tout est controle ici.
cd "$(dirname "$0")" || exit 1
ICI="$PWD"
JEU="$ICI/jeu"
EXE="$JEU/Aloft.exe"
DONNEES="$ICI/donnees"
JOURNAL_CREATION="teamkit-creation.log"
JOURNAL_SERVEUR="teamkit-serveur.log"

export WINEPREFIX="$ICI/.wine"
export WINEARCH=win64
export WINEDEBUG=-all
# mscoree et mshtml coupes : Wine ne propose pas d'installer Mono et Gecko (inutiles ici,
# et la fenetre d'installation bloquerait sans ecran). Meme reglage que l'oeuf Pterodactyl.
export WINEDLLOVERRIDES="mscoree,mshtml="
if [ -z "$XDG_RUNTIME_DIR" ] || [ ! -d "$XDG_RUNTIME_DIR" ]; then
  export XDG_RUNTIME_DIR="/tmp/tk-aloft-$(id -u)"
  mkdir -p "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
fi

manque_jeu() {
  echo "ERREUR : les fichiers d'Aloft sont absents ($EXE introuvable)."
  echo "  Lance Update et connecte un compte Steam qui POSSEDE Aloft (app 1660080) :"
  echo "  il n'existe pas de serveur Aloft telechargeable sans le jeu."
}

prefixe_pret() { [ -f "$WINEPREFIX/system.reg" ] && [ -d "$WINEPREFIX/drive_c/users" ]; }

creer_prefixe() {
  echo "TeamKit : creation du prefixe Wine (.wine), quelques secondes..."
  wineboot --init > /dev/null 2>&1
  wineserver -w
  prefixe_pret || { echo "ERREUR : wineboot n'a pas cree le prefixe Wine."; return 1; }
  echo "TeamKit : prefixe Wine pret ($(wine --version 2>/dev/null))."
}

# Les sauvegardes d'Aloft vont dans AppData/LocalLow/Astrolabe Interactive, a l'interieur du
# prefixe Wine. On les range dans donnees/ (dossier visible de l'instance) et on met un lien
# a leur place : un prefixe refait ne les emporte pas, et on les trouve sans fouiller .wine.
relier_donnees() {
  local profils p ll cible ancien n=0
  # Profils Wine : celui de $USER (Wine nomme le profil d'apres $USER, verifie le 10/10/2026),
  # celui note dans le registre a la creation du prefixe, et tout autre dossier de users/
  # sauf Public : si $USER change un jour, le jeu ecrit quand meme dans donnees/.
  profils=$( { [ -n "$USER" ] && echo "$USER"
    grep -i '"ProfileImagePath"' "$WINEPREFIX/system.reg" 2>/dev/null | sed -n 's/.*users\\\\\([^"\\]*\)".*/\1/p'
    ls -1 "$WINEPREFIX/drive_c/users" 2>/dev/null; } | grep -v -x -i -E 'public|default|systemprofile' | sort -u)
  mkdir -p "$DONNEES"
  for p in $profils; do
    ll="$WINEPREFIX/drive_c/users/$p/AppData/LocalLow"
    cible="$ll/Astrolabe Interactive"
    mkdir -p "$ll"
    if [ -d "$cible" ] && [ ! -L "$cible" ]; then
      if [ -n "$(ls -A "$cible" 2>/dev/null)" ]; then
        # Un vrai dossier plein : le jeu a ecrit avant le lien. On ne melange rien et on n'efface rien.
        ancien="$ICI/recupere-$p-$(date +%Y%m%d-%H%M%S)"
        mv "$cible" "$ancien"
        echo "ATTENTION : des donnees d'Aloft etaient dans le prefixe Wine, deplacees dans $(basename "$ancien")/."
        echo "  Compare avec donnees/ et recopie ce qu'il faut a la main, serveur arrete."
      else
        rmdir "$cible"
      fi
    fi
    # Lien relatif : il reste bon si le dossier de l'instance change de place (restauration).
    ln -sfn "../../../../../../donnees" "$cible"
    [ -d "$cible/" ] || { echo "ERREUR : le lien vers donnees/ ne marche pas ($cible)."; return 1; }
    n=$((n + 1))
  done
  [ "$n" -gt 0 ] || { echo "ERREUR : aucun profil utilisateur dans le prefixe Wine."; return 1; }
}

# ---------------------------------------------------------------------------------------------
if [ "$1" = "preparer" ]; then
  shift
  COMPOSANTS=""
  for a in "$@"; do
    case "$a" in
      composants=*) COMPOSANTS="${a#composants=}" ;;
      *) echo "ERREUR : argument inattendu : $a" ; exit 1 ;;
    esac
  done
  if [ ! -f "$EXE" ]; then
    manque_jeu
    exit 1
  fi
  echo "Aloft.exe present ; dossier du jeu : $(du -sh "$JEU" 2>/dev/null | cut -f1)."
  prefixe_pret || creer_prefixe || exit 1
  for v in ${COMPOSANTS//,/ }; do
    if [[ ! "$v" =~ ^[a-z0-9_.=]{1,40}$ ]]; then
      echo "ERREUR : composant '$v' refuse (lettres minuscules, chiffres, _ . = seulement)."
      exit 1
    fi
    if [ ! -f "$ICI/winetricks" ]; then
      echo "ERREUR : winetricks absent (l'etape d'Update qui le telecharge a echoue)."
      exit 1
    fi
    echo "TeamKit : winetricks $v ..."
    if xvfb-run -a sh "$ICI/winetricks" -q "$v" > "$ICI/winetricks-$v.log" 2>&1; then
      echo "TeamKit : $v installe (ou deja la)."
    else
      echo "ERREUR : winetricks $v a echoue. Fin du journal (winetricks-$v.log) :"
      tail -n 8 "$ICI/winetricks-$v.log"
      wineserver -w
      exit 1
    fi
    wineserver -w
  done
  relier_donnees || exit 1
  echo "Sauvegardes d'Aloft : donnees/ (lien depuis le prefixe Wine)."
  # Les lignes officielles des scripts du jeu : utiles pour voir si les developpeurs ont
  # change les options du serveur.
  for ps in "$JEU"/AloftServerNoGui*.ps1; do
    [ -f "$ps" ] || continue
    echo "Script officiel $(basename "$ps") :"
    grep -i 'Arguments' "$ps" | tr -d '\r' | sed 's/^[[:space:]]*/    /'
  done
  exit 0
fi

# ---------------------------------------------------------------------------------------------
declare -A V
for a in "$@"; do
  case "$a" in
    *=*) V["${a%%=*}"]="${a#*=}" ;;
    *) echo "ERREUR : argument inattendu : $a" ; exit 1 ;;
  esac
done

refuser() {
  echo "ERREUR : $1"
  echo "Corrige ce reglage dans l'onglet Configuration d'AMP, puis relance."
  exit 1
}
entier() { [[ "$1" =~ ^[0-9]+$ ]]; }

PORT="${V[port]}"
MONDE="${V[monde]}"
SERVEUR="${V[serveur]}"
VISIBLE="${V[visible]:-true}"
PRIVEES="${V[privees]:-false}"
JOUEURS="${V[joueurs]:-8}"
ADMINS="${V[admins]}"
ILES="${V[iles]:-normal}"
CORRUPTION="${V[corruption]:-normal}"
CREATIF="${V[creatif]:-false}"
PLUS="${V[plus]}"
# Secondes laissees a Aloft pour se fermer (App.ExitTimeout du template est plus long).
ATTENTE=45

entier "$PORT" && [ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] || refuser "port invalide : '$PORT'."
[[ "$MONDE" =~ ^[A-Za-z0-9]{1,20}$ ]] || refuser "nom du monde '$MONDE' : 1 a 20 lettres sans accent ou chiffres, sans espace ni signe."
# Le jeu refuse les espaces dans le nom du serveur : on les change en _ plutot que de bloquer.
if [[ "$SERVEUR" == *" "* ]]; then
  SERVEUR=$(printf '%s' "$SERVEUR" | sed -e 's/^ *//' -e 's/ *$//' -e 's/  */_/g')
  echo "TeamKit : espaces du nom du serveur remplacees par _ (le jeu les refuse) : $SERVEUR"
fi
[[ "$SERVEUR" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || refuser "nom du serveur '$SERVEUR' : lettres sans accent, chiffres, _ ou - (64 au plus)."
[[ "$VISIBLE" =~ ^(true|false)$ ]] || refuser "visibilite '$VISIBLE' : true ou false."
[[ "$PRIVEES" =~ ^(true|false)$ ]] || refuser "iles privees '$PRIVEES' : true ou false."
entier "$JOUEURS" && [ "$JOUEURS" -ge 1 ] && [ "$JOUEURS" -le 8 ] || refuser "joueurs '$JOUEURS' : de 1 a 8 (limite du jeu)."
[[ "$ILES" =~ ^(normal|big|huge)$ ]] || refuser "nombre d'iles '$ILES' inconnu."
[[ "$CORRUPTION" =~ ^(none|little|normal|lots|shrooms)$ ]] || refuser "corruption '$CORRUPTION' inconnue."
[[ "$CREATIF" =~ ^(true|false)$ ]] || refuser "mode creatif '$CREATIF' : true ou false."
LISTE_ADMINS=()
for id in ${ADMINS//,/ }; do
  [[ "$id" =~ ^[0-9]{17}$ ]] || refuser "administrateur '$id' : un SteamID64 (17 chiffres, ex. 76561198000000000)."
  LISTE_ADMINS+=("$id")
done
EN_PLUS=()
for o in $PLUS; do
  [[ "$o" =~ ^[A-Za-z]+#[^#]*#$ ]] || refuser "option en plus '$o' : forme attendue cle#valeur# (ex. disablevideo#true#)."
  EN_PLUS+=("$o")
done

if [ ! -f "$EXE" ]; then
  manque_jeu
  exit 1
fi

# Le monde existe deja ? Repere pose par ce script apres la creation, ou fichiers du jeu
# portant le nom du monde (format w_<nom> releve par l'oeuf Pterodactyl), par exemple un
# monde importe dans donnees/.
REPERE="$DONNEES/.teamkit-monde-$MONDE"
monde_existe() {
  [ -f "$REPERE" ] && return 0
  [ -n "$(find "$DONNEES/" -mindepth 2 \( -name "w_$MONDE" -o -name "w_$MONDE.*" \) 2>/dev/null | head -n 1)" ]
}

ARGS_CREATION=()
if ! monde_existe; then
  ARGS_CREATION=(-batchmode -nographics -server -logFile "$JOURNAL_CREATION" "create#$MONDE#"
    "islandcount#$ILES#" "corruptioncount#$CORRUPTION#" "creative#$CREATIF#" "log#ERROR#")
fi
ARGS=(-batchmode -nographics -server -logFile "$JOURNAL_SERVEUR" "load#$MONDE#" "servername#$SERVEUR#"
  "log#ERROR#" "isvisible#$VISIBLE#" "privateislands#$PRIVEES#" "playercount#$JOUEURS#" "serverport#$PORT#")
for id in "${LISTE_ADMINS[@]}"; do ARGS+=("admin#$id#"); done
ARGS+=("${EN_PLUS[@]}")

# Utilise seulement par verifier.py : ecrit les arguments, un par ligne, sans lancer Wine.
if [ -n "$TK_ESSAI_ARGS" ]; then
  { [ ${#ARGS_CREATION[@]} -gt 0 ] && printf 'CREATION %s\n' "${ARGS_CREATION[@]}"
    printf 'SERVEUR %s\n' "${ARGS[@]}"; } > "$TK_ESSAI_ARGS"
  exit 0
fi

# Restes d'un arret brutal (processus Wine orphelins de ce prefixe).
wineserver -k > /dev/null 2>&1
prefixe_pret || creer_prefixe || exit 1
relier_donnees || exit 1

JPID=""
SUIVI=""
GUET=""
ARRET=0
arreter() {
  trap - TERM INT
  ARRET=1
  echo "TeamKit : arret demande, fermeture d'Aloft (Ctrl+C, comme l'oeuf Pterodactyl)."
  local p
  p=$(pgrep -x Aloft.exe)
  [ -n "$p" ] && kill -INT $p 2>/dev/null
  for _ in $(seq 1 "$ATTENTE"); do
    pgrep -x Aloft.exe > /dev/null || break
    sleep 1
  done
  if pgrep -x Aloft.exe > /dev/null; then
    echo "TeamKit : Aloft ne s'est pas ferme en $ATTENTE s, arret force."
  fi
  wineserver -k > /dev/null 2>&1
}
trap arreter TERM INT

# Lance Aloft.exe sous Wine dans un faux ecran et recopie son journal dans la console d'AMP
# (sans les retours chariot de Windows).
lancer() {
  local journal="$1"
  shift
  rm -f "$JEU/$journal"
  : > "$JEU/$journal"
  (cd "$JEU" && exec xvfb-run -a wine Aloft.exe "$@") > "$ICI/wine.log" 2>&1 &
  JPID=$!
  tail -n +1 -F --pid="$JPID" "$JEU/$journal" 2>/dev/null | sed -u 's/\r$//' &
  SUIVI=$!
}

if [ ${#ARGS_CREATION[@]} -gt 0 ]; then
  echo "TeamKit : le monde $MONDE n'existe pas encore, creation (iles $ILES, corruption $CORRUPTION, creatif $CREATIF)."
  echo "TeamKit : cela peut prendre plusieurs minutes ; Aloft se ferme tout seul a la fin."
  touch "$ICI/.teamkit-debut-creation"
  lancer "$JOURNAL_CREATION" "${ARGS_CREATION[@]}"
  wait "$JPID"
  [ "$ARRET" = 1 ] && wait "$JPID"
  sleep 1
  kill "$SUIVI" 2>/dev/null
  if [ "$ARRET" = 1 ]; then
    echo "TeamKit : creation interrompue."
    exit 0
  fi
  if [ -z "$(find "$DONNEES/" -mindepth 1 -newer "$ICI/.teamkit-debut-creation" -type f ! -name '*.log' 2>/dev/null | head -n 1)" ] \
     && [ -z "$(find "$DONNEES/" -mindepth 2 -name "*$MONDE*" 2>/dev/null | head -n 1)" ]; then
    echo "ERREUR : Aloft s'est ferme sans creer le monde $MONDE (rien de neuf dans donnees/)."
    echo "  Voir jeu/$JOURNAL_CREATION et wine.log."
    exit 1
  fi
  date '+cree le %d/%m/%Y a %H:%M' > "$REPERE"
  echo "TeamKit : monde $MONDE cree."
fi

AFFICHE="${ARGS[*]}"
echo "TeamKit : Aloft.exe $AFFICHE"
touch "$ICI/.teamkit-debut"
lancer "$JOURNAL_SERVEUR" "${ARGS[@]}"

# Ligne "pret" pour AMP, avec le code pour rejoindre (ServerRoomCode.txt, ecrit par le jeu
# a chaque demarrage). Si le fichier n'apparait pas mais que le journal dit "Server Ready"
# (texte attendu par l'oeuf Pterodactyl), on se declare pret quand meme au bout d'une minute.
(
  pret_vu=0
  for i in $(seq 1 900); do
    kill -0 "$JPID" 2>/dev/null || exit 0
    f=$(find "$JEU" "$DONNEES/" -maxdepth 6 -name ServerRoomCode.txt -newer "$ICI/.teamkit-debut" 2>/dev/null | head -n 1)
    if [ -n "$f" ]; then
      code=$(tr -dc 'A-Za-z0-9' < "$f" | head -c 32)
      if [ -n "$code" ]; then
        echo "TeamKit : Aloft est pret. Code pour rejoindre : $code"
        printf '%s\n' "$code" > "$ICI/code-pour-rejoindre.txt"
        exit 0
      fi
    fi
    if [ "$pret_vu" = 0 ] && grep -q "Server Ready" "$JEU/$JOURNAL_SERVEUR" 2>/dev/null; then
      pret_vu=$i
    fi
    if [ "$pret_vu" != 0 ] && [ $((i - pret_vu)) -ge 60 ]; then
      echo "TeamKit : Aloft est pret. Code pour rejoindre : introuvable (pas de ServerRoomCode.txt)."
      exit 0
    fi
    sleep 1
  done
  echo "TeamKit : ATTENTION, Aloft n'a toujours ni code ni \"Server Ready\" apres 15 minutes."
) &
GUET=$!

# Le SIGTERM d'AMP interrompt ce "wait" : on attend une seconde fois la vraie fin.
wait "$JPID"
CODE=$?
if [ "$ARRET" = 1 ]; then
  wait "$JPID"
  CODE=0
fi
sleep 1
kill "$GUET" "$SUIVI" 2>/dev/null
wineserver -k > /dev/null 2>&1
if [ "$ARRET" != 1 ]; then
  echo "TeamKit : Aloft s'est arrete tout seul (code $CODE). Fin de wine.log :"
  tail -n 15 "$ICI/wine.log"
fi
exit "$CODE"
