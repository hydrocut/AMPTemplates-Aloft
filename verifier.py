# -*- coding: utf-8 -*-
"""
Contrôle du template avant de le pousser (même rôle que ceux de Dominions 6 et de Wesnoth).

    python verifier.py

Aloft est payant et n'a qu'un serveur Windows : on ne peut pas lancer le vrai serveur ici.
Ce script vérifie donc tout ce qui peut casser sans le jeu :

1. tous les JSON se parsent ;
2. le .kvp : fichiers inclus, Ref des ports, bloc Console.* / Limits.* complet, connexion Steam
   non anonyme, image Wine de CubeCoders, délai d'arrêt plus long que celui du lanceur ;
3. chaque réglage exposé dans AMP sert (ligne de commande ou Update), et chaque {{Réglage}}
   utilisé est défini ;
4. la ligne de commande d'AMP : un argument "cle={{Réglage}}" entre guillemets par réglage, et
   exactement les clés que lit le lanceur ;
5. les choix proposés (îles, corruption, cases à cocher, nombre de joueurs) sont ceux que le
   lanceur accepte, et chaque option donnée au jeu est documentée (wiki officiel d'Aloft et notes
   de version 0.3.4.23 « Bloom & Blight ») ;
6. les étapes d'Update : SteamCMD 1660080 en version Windows vers jeu/, fichiers téléchargés
   depuis le dépôt du manifest, winetricks à une version figée, étape « preparer » ;
7. le lanceur : LF, ASCII, sans {{, `bash -n` ;
8. aller-retour réel (si bash est disponible) : la ligne de commande rendue comme le ferait AMP,
   avec les valeurs par défaut puis des valeurs piégées, passe par le vrai lanceur, qui doit
   produire les bons arguments ou refuser proprement ; monde existant ou importé = pas de
   création ;
9. les regex de console sur les lignes que le lanceur écrit.
"""
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = 'aloft'
SCRIPT = 'scripts/lancer-aloft.sh'
soucis = []


def lire(nom, binaire=False):
    chemin = os.path.join(ICI, nom)
    if binaire:
        with open(chemin, 'rb') as f:
            return f.read()
    with io.open(chemin, encoding='utf-8') as f:
        return f.read()


def ok(quoi, detail):
    print('ok   %-26s %s' % (quoi, detail))


def py(motif):
    # AMP est en C# : (?<nom>...) ; Python veut (?P<nom>...)
    return re.compile(motif.replace('(?<', '(?P<'))


# ── 1. JSON ──────────────────────────────────────────────────────────────────
data = {}
for nom in ('manifest.json', NOM + 'config.json', NOM + 'metaconfig.json', NOM + 'ports.json', NOM + 'updates.json'):
    try:
        data[nom] = json.loads(lire(nom))
        ok(nom, 'JSON valide')
    except Exception as e:
        soucis.append('%s : JSON invalide (%s)' % (nom, e))
if soucis:
    print('\n'.join('NON  ' + s for s in soucis))
    sys.exit(1)
config = data[NOM + 'config.json']
updates = data[NOM + 'updates.json']
ports = data[NOM + 'ports.json']
script = lire(SCRIPT, binaire=True).decode('utf-8')

# ── 2. kvp ───────────────────────────────────────────────────────────────────
kvp = lire(NOM + '.kvp')
cles = dict(l.split('=', 1) for l in kvp.splitlines() if '=' in l)
for ref in re.findall(r'@IncludeJson\[([^\]]+)\]', kvp):
    if not os.path.isfile(os.path.join(ICI, ref)):
        soucis.append('@IncludeJson[%s] : fichier absent' % ref)
for cle in ('Meta.ConfigManifest', 'Meta.MetaConfigManifest'):
    if not os.path.isfile(os.path.join(ICI, cles.get(cle, '?'))):
        soucis.append('%s pointe sur un fichier absent' % cle)
refs = {p['Ref']: p for p in ports}
if cles.get('App.PrimaryApplicationPortRef') not in refs:
    soucis.append('PrimaryApplicationPortRef ne correspond à aucun port')
for r in re.findall(r'\{\{\$(\w+)\}\}', cles.get('App.CommandLineArgs', '')):
    if r not in refs and r != 'FullBaseDir':
        soucis.append('{{$%s}} : aucun port ne porte ce Ref' % r)
if 'QueryPort' in refs and refs['QueryPort']['Port'] != refs['GamePort']['Port'] + 1:
    soucis.append('le port de requête réservé doit valoir port du jeu + 1 (guide Steam : 15636 / 15637)')
ok('ports', ', '.join('%s %s/%s' % (p['Ref'], p['Port'], p['Protocol']) for p in ports))
ATTENDUES = ['App.SupportsUniversalSleep', 'App.WakeupMode', 'App.ApplicationReadyMode', 'Console.FilterMatchRegex',
             'Console.FilterMatchReplacement', 'Console.ThrowawayMessageRegex', 'Console.AppReadyRegex',
             'Console.UserJoinRegex', 'Console.UserLeaveRegex', 'Console.UserChatRegex', 'Console.UpdateAvailableRegex',
             'Console.PreConnectRegex', 'Console.ConnectIPRegex', 'Console.MetricsRegex', 'Console.HideFromConsoleRegex',
             'Console.SuppressLogAtStart', 'Console.UserActions', 'Limits.SleepMode', 'Limits.SleepOnStart',
             'Limits.SleepDelayMinutes', 'Limits.DozeDelay', 'Limits.AutoRetryCount', 'Limits.SleepStartThresholdSeconds']
absentes = [c for c in ATTENDUES if c not in cles]
if absentes:
    soucis.append('clés absentes du .kvp : ' + ', '.join(absentes))
else:
    ok('kvp complet', 'les %d clés Console/Limits sont là' % len(ATTENDUES))
if cles.get('App.ApplicationReadyMode') == 'RegexMatch' and not cles.get('Console.AppReadyRegex'):
    soucis.append('RegexMatch sans AppReadyRegex : l’instance ne serait jamais déclarée prête')
ATTENDU_KVP = {
    'App.SteamUpdateAnonymousLogin': 'False',   # jeu payant : compte Steam qui le possède
    'App.SteamForceLoginPrompt': 'True',        # comme Starbound / Stardew Valley / Risk of Rain 2 chez CubeCoders
    'App.ExitMethod': 'SIGTERM',                # le lanceur le traduit en Ctrl+C pour Aloft.exe
    'App.ExecutableLinux': '/bin/bash',
    'App.MaxUsers': '8',                        # = défaut de JoueursMax (capacité affichée ; lignes d'arrivée inconnues)
    'Meta.ContainerPolicy': 'Required',
    'Meta.SpecificDockerImage': 'cubecoders/ampbase:wine-stable',
    'Meta.DisplayImageSource': 'steam:1660080',
    'Meta.OS': 'Linux',
}
for cle, val in ATTENDU_KVP.items():
    if cles.get(cle) != val:
        soucis.append('%s devrait valoir %s (vaut %r)' % (cle, val, cles.get(cle)))
m = re.search(r'^ATTENTE=(\d+)$', script, re.M)
if not m or int(cles.get('App.ExitTimeout', '0')) <= int(m.group(1)) + 5:
    soucis.append('App.ExitTimeout doit dépasser d’au moins 5 s l’ATTENTE du lanceur (sinon AMP tue Aloft avant la fin)')
if cles.get('Meta.URL') != data['manifest.json']['url']:
    soucis.append('Meta.URL et manifest.json ne désignent pas le même dépôt')
ok('kvp', 'Steam non anonyme, image Wine, SIGTERM, délai d’arrêt %s s' % cles.get('App.ExitTimeout'))

# ── 3. réglages utilisés <-> définis ─────────────────────────────────────────
definis = [c['FieldName'] for c in config]
if len(definis) != len(set(definis)):
    soucis.append('réglages en double')
for c in config:
    if c['FieldName'] != c.get('ParamFieldName'):
        soucis.append('%s : FieldName et ParamFieldName différents' % c['FieldName'])
cmd = cles['App.CommandLineArgs']
dans_cmd = set(re.findall(r'\{\{([A-Za-z]\w*)\}\}', cmd))
dans_update = set(re.findall(r'\{\{([A-Za-z]\w*)\}\}', json.dumps(updates)))
utilises = dans_cmd | dans_update
for u in sorted(utilises - set(definis)):
    soucis.append('{{%s}} utilisé mais défini nulle part dans %sconfig.json' % (u, NOM))
for d in sorted(set(definis) - utilises):
    soucis.append('réglage %s exposé dans AMP mais utilisé nulle part' % d)
if not (utilises ^ set(definis)):
    ok('réglages', '%d définis : %d en ligne de commande, %d dans l’Update' % (len(definis), len(dans_cmd), len(dans_update)))
par_nom = {c['FieldName']: c for c in config}
for c in config:
    ev, d = c.get('EnumValues') or {}, c.get('DefaultValue')
    if c['InputType'] == 'enum' and d not in ev:
        soucis.append('%s : DefaultValue %r absente de la liste' % (c['FieldName'], d))
    if c['InputType'] == 'checkbox' and d not in ev.values():
        soucis.append('%s : DefaultValue %r absente des valeurs de la case' % (c['FieldName'], d))

# ── 4. ligne de commande <-> lanceur ─────────────────────────────────────────
morceaux = shlex.split(cmd)
if morceaux[0] != '{{$FullBaseDir}}lancer-aloft.sh':
    soucis.append('la ligne de commande doit commencer par le lanceur')
cles_cmd = {}
for mo in morceaux[1:]:
    r = re.fullmatch(r'([a-z]+)=\{\{\$?(\w+)\}\}', mo)
    if not r:
        soucis.append('argument %r : attendu cle={{Réglage}}, entre guillemets' % mo)
        continue
    cles_cmd[r.group(1)] = r.group(2)
for brut in re.findall(r'"[^"]*"|\S+', cmd)[1:]:
    if not (brut.startswith('"') and brut.endswith('"')):
        soucis.append('argument %s sans guillemets : une espace dans la valeur le couperait en deux' % brut)
lues = set(re.findall(r'\$\{V\[(\w+)\]', script))
if set(cles_cmd) != lues:
    soucis.append('clés passées par AMP %s ≠ clés lues par le lanceur %s' % (sorted(cles_cmd), sorted(lues)))
else:
    ok('ligne de commande', '%d arguments cle=valeur, tous lus par le lanceur' % len(cles_cmd))


# ── 5. choix proposés <-> lanceur <-> documentation ──────────────────────────
def accepte(variable):
    m = re.search(r'\[\[ "\$%s" =~ \^\(([^)]*)\)\$ \]\]' % variable, script)
    return set(m.group(1).split('|')) if m else None


for champ, variable in (('Iles', 'ILES'), ('Corruption', 'CORRUPTION')):
    permis, choix = accepte(variable), set(par_nom[champ]['EnumValues'])
    if permis is None:
        soucis.append('contrôle de %s introuvable dans le lanceur' % variable)
    elif choix != permis:
        soucis.append('%s : AMP propose %s, le lanceur accepte %s' % (champ, sorted(choix), sorted(permis)))
    else:
        ok('choix ' + champ, ', '.join(sorted(choix)))
for champ, variable in (('Visible', 'VISIBLE'), ('IlesPrivees', 'PRIVEES'), ('Creatif', 'CREATIF')):
    if set(par_nom[champ]['EnumValues'].values()) != accepte(variable):
        soucis.append('%s : la case doit donner true/false, comme l’attend le lanceur' % champ)
j = par_nom['JoueursMax']
if (j['MinValue'], j['MaxValue']) != ('1', '8') or '-le 8 ]' not in script:
    soucis.append('JoueursMax : 1 à 8 (limite du jeu, dite par le développeur), dans AMP comme dans le lanceur')
if cles.get('App.MaxUsers') != j['DefaultValue']:
    soucis.append('App.MaxUsers doit valoir le défaut de JoueursMax (%s) : sinon AMP et le site affichent une autre capacité' % j['DefaultValue'])
# Options du serveur Aloft : wiki officiel (Dedicated Server how-to) et notes de version 0.3.4.23.
DOC = {'create', 'islandcount', 'corruptioncount', 'creative', 'log', 'load', 'servername', 'isvisible',
       'privateislands', 'playercount', 'serverport', 'admin'}
blocs = re.findall(r'ARGS(?:_CREATION)?\+?=\((.*?)\)', script, re.S)
donnees = set(re.findall(r'"([a-z]+)#', ' '.join(blocs)))
if donnees - DOC:
    soucis.append('options non documentées données au jeu : %s' % ', '.join(sorted(donnees - DOC)))
elif DOC - donnees:
    soucis.append('options documentées jamais données : %s' % ', '.join(sorted(DOC - donnees)))
else:
    ok('options du jeu', '%d options, toutes documentées' % len(donnees))
for o in ('-batchmode', '-nographics', '-server', '-logFile'):
    if o not in ' '.join(blocs):
        soucis.append('option Unity %s absente' % o)

# ── 6. étapes d'Update ───────────────────────────────────────────────────────
depot = data['manifest.json']['url'].replace('https://github.com/', '')
st = [e for e in updates if e['UpdateSource'] == 'SteamCMD']
if (len(st) != 1 or st[0]['UpdateSourceData'] != '1660080' or st[0].get('ForceDownloadPlatform') != 'Windows'
        or st[0].get('UpdateSourceTarget') != '{{$FullBaseDir}}jeu'):
    soucis.append('étape SteamCMD : app 1660080, version Windows, vers {{$FullBaseDir}}jeu')
elif 'JEU="$ICI/jeu"' not in script or 'EXE="$JEU/Aloft.exe"' not in script:
    soucis.append('le lanceur ne cherche pas Aloft.exe dans jeu/, là où SteamCMD l’installe')
else:
    ok('SteamCMD', 'app 1660080 (Windows) -> jeu/')
for e in [e for e in updates if e['UpdateSource'] == 'FetchURL']:
    if e['UpdateSourceArgs'] == 'winetricks':
        if not re.search(r'/winetricks/refs/tags/\d{8}/src/winetricks$', e['UpdateSourceData']):
            soucis.append('winetricks doit être pris à une version figée (tag), pas sur master')
        continue
    attendu = 'https://raw.githubusercontent.com/%s/main/scripts/%s' % (depot, e['UpdateSourceArgs'])
    if e['UpdateSourceData'] != attendu:
        soucis.append('URL inattendue pour %s : %s' % (e['UpdateSourceArgs'], e['UpdateSourceData']))
    elif not os.path.isfile(os.path.join(ICI, 'scripts', e['UpdateSourceArgs'])):
        soucis.append('scripts/%s absent du dépôt' % e['UpdateSourceArgs'])
    else:
        ok('téléchargé à l’Update', 'scripts/%s' % e['UpdateSourceArgs'])
prep = [e for e in updates if e['UpdateSource'] == 'Executable']
if (len(prep) != 1 or prep[0]['UpdateSourceArgs'] != '"{{$FullBaseDir}}lancer-aloft.sh" preparer "composants={{ComposantsWindows}}"'
        or prep[0] is not updates[-1]):
    soucis.append('dernière étape attendue : lancer-aloft.sh preparer "composants={{ComposantsWindows}}"')
else:
    ok('étape preparer', 'préfixe Wine + winetricks + lien des sauvegardes, en dernier')

# ── 7. lanceur ───────────────────────────────────────────────────────────────
brut = lire(SCRIPT, binaire=True)
if b'\r' in brut:
    soucis.append('%s : fins de ligne Windows (CRLF), bash refusera' % SCRIPT)
if any(o > 127 for o in brut):
    soucis.append('%s : caractères non ASCII' % SCRIPT)
if '{{' in script:
    soucis.append('%s contient {{ : AMP pourrait le remplacer' % SCRIPT)
if not script.startswith('#!/bin/bash\n'):
    soucis.append('%s : doit commencer par #!/bin/bash' % SCRIPT)
for besoin, pourquoi in [
    ('ln -sfn "../../../../../../donnees" "$cible"', 'lien relatif des sauvegardes vers donnees/'),
    ('export WINEDLLOVERRIDES="mscoree,mshtml="', 'pas de fenêtre Mono/Gecko sans écran'),
    ('xvfb-run -a wine Aloft.exe', 'faux écran'),
    ('wineserver -k', 'ménage des processus Wine orphelins'),
    ('trap arreter TERM INT', 'arrêt demandé par AMP'),
    ('kill -INT', 'Ctrl+C à Aloft.exe, comme l’œuf Pterodactyl'),
]:
    if besoin not in script:
        soucis.append('lanceur : %s (%s)' % (besoin, pourquoi))


def trouver_bash():
    for c in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files\Git\usr\bin\bash.exe', '/bin/bash'):
        if os.path.isfile(c):
            return c
    c = shutil.which('bash')
    if c and 'system32' not in c.lower():   # le bash de WSL ne verrait pas les chemins Windows
        return c
    return None


bash = trouver_bash()
if bash:
    r = subprocess.run([bash, '-n', os.path.join(ICI, SCRIPT)], capture_output=True, text=True)
    if r.returncode:
        soucis.append('bash -n : %s' % r.stderr.strip())
    else:
        ok('lanceur', 'LF, ASCII, sans {{, bash -n')

# ── 8. aller-retour réel par le lanceur ──────────────────────────────────────
DEFAUTS = {c['FieldName']: c.get('DefaultValue', '') for c in config}
PORT = str(refs['GamePort']['Port'])


def lancer(dossier, valeurs):
    ligne = cmd.replace('{{$FullBaseDir}}', dossier.replace('\\', '/') + '/').replace('{{$GamePort}}', PORT)
    for k, v in valeurs.items():
        ligne = ligne.replace('{{%s}}' % k, v)
    argv = shlex.split(ligne)
    sortie = os.path.join(dossier, 'args.txt')
    if os.path.exists(sortie):
        os.remove(sortie)
    env = dict(os.environ, TK_ESSAI_ARGS=sortie.replace('\\', '/'))
    p = subprocess.run([bash] + argv, env=env, capture_output=True, timeout=60)
    texte = p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')
    creation, serveur = None, None
    if os.path.exists(sortie):
        creation, serveur = [], []
        with io.open(sortie, encoding='utf-8') as f:
            for l in f.read().split('\n')[:-1]:
                quoi, _, arg = l.partition(' ')
                (creation if quoi == 'CREATION' else serveur).append(arg)
    return p.returncode, texte, creation, serveur


UNITY = ['-batchmode', '-nographics', '-server', '-logFile']
CREA = UNITY + ['teamkit-creation.log', 'create#TeamKit#', 'islandcount#normal#', 'corruptioncount#normal#',
                'creative#false#', 'log#ERROR#']


def serveur(nom='Serveur_FR_TeamKit', fin=(), monde='TeamKit', visible='true', privees='false', joueurs='8'):
    return UNITY + ['teamkit-serveur.log', 'load#%s#' % monde, 'servername#%s#' % nom, 'log#ERROR#',
                    'isvisible#%s#' % visible, 'privateislands#%s#' % privees, 'playercount#%s#' % joueurs,
                    'serverport#%s#' % PORT] + list(fin)


if not bash:
    print('---  aller-retour             bash introuvable : étape 8 sautée (à faire avant de pousser)')
else:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(ICI, SCRIPT), os.path.join(tmp, 'lancer-aloft.sh'))
        os.makedirs(os.path.join(tmp, 'jeu'))
        with open(os.path.join(tmp, 'jeu', 'Aloft.exe'), 'w') as f:
            f.write('faux binaire\n')
        CAS = [
            ('valeurs par défaut', {}, 0, CREA, serveur()),
            ('valeurs piégées', {'NomServeur': '  TeamKit   serveur FR ', 'Admins': '76561198000000001, 76561198000000002',
                                 'OptionsEnPlus': 'disablevideo#true#  foo#a b#', 'Iles': 'huge', 'Corruption': 'shrooms',
                                 'Creatif': 'true', 'Visible': 'false', 'IlesPrivees': 'true', 'JoueursMax': '4',
                                 'NomMonde': 'Monde2'}, 1, None, None),
            ('valeurs vives', {'NomServeur': 'TeamKit serveur FR', 'Admins': '76561198000000001,76561198000000002',
                               'OptionsEnPlus': 'disablevideo#true#', 'Iles': 'huge', 'Corruption': 'shrooms',
                               'Creatif': 'true', 'Visible': 'false', 'IlesPrivees': 'true', 'JoueursMax': '4',
                               'NomMonde': 'Monde2'}, 0,
             UNITY + ['teamkit-creation.log', 'create#Monde2#', 'islandcount#huge#', 'corruptioncount#shrooms#',
                      'creative#true#', 'log#ERROR#'],
             serveur('TeamKit_serveur_FR', ['admin#76561198000000001#', 'admin#76561198000000002#', 'disablevideo#true#'],
                     'Monde2', 'false', 'true', '4')),
            ('monde avec une espace', {'NomMonde': 'Mon monde'}, 1, None, None),
            ('monde avec un accent', {'NomMonde': 'Monde_été'}, 1, None, None),
            ('monde avec _', {'NomMonde': 'Mon_monde'}, 1, None, None),
            ('monde vide', {'NomMonde': ''}, 1, None, None),
            ('monde trop long', {'NomMonde': 'A' * 21}, 1, None, None),
            ('serveur avec apostrophe', {'NomServeur': "L'île"}, 1, None, None),
            ('serveur vide', {'NomServeur': ''}, 1, None, None),
            ('9 joueurs', {'JoueursMax': '9'}, 1, None, None),
            ('0 joueur', {'JoueursMax': '0'}, 1, None, None),
            ('admin invalide', {'Admins': '7656119800000000'}, 1, None, None),
            ('admin avec lettres', {'Admins': 'Kevin'}, 1, None, None),
            ('option sans #', {'OptionsEnPlus': 'disablevideo'}, 1, None, None),
            ('île inconnue', {'Iles': 'tiny'}, 1, None, None),
        ]
        for titre, change, code_attendu, crea, serv in CAS:
            code, texte, c, s = lancer(tmp, dict(DEFAUTS, **change))
            if code != code_attendu:
                soucis.append('aller-retour « %s » : code %s au lieu de %s\n%s' % (titre, code, code_attendu, texte))
            elif code == 0 and (c or None, s) != (crea, serv):
                soucis.append('aller-retour « %s » :\n       obtenu  %s / %s\n       attendu %s / %s' % (titre, c, s, crea, serv))
            elif code == 1 and ('ERREUR' not in texte or s is not None):
                soucis.append('aller-retour « %s » : refus sans message clair, ou jeu lancé quand même' % titre)
        # monde déjà créé (repère du lanceur) puis monde importé (fichiers w_<nom>) : pas de création
        donnees = os.path.join(tmp, 'donnees')
        os.makedirs(donnees)
        open(os.path.join(donnees, '.teamkit-monde-TeamKit'), 'w').close()
        code, texte, c, s = lancer(tmp, DEFAUTS)
        if code != 0 or c or s != serveur():
            soucis.append('aller-retour « monde existant » : %s %s %s' % (code, c, s))
        os.makedirs(os.path.join(donnees, 'Aloft', 'Data01', 'Saves', 'w_Importe'))
        code, texte, c, s = lancer(tmp, dict(DEFAUTS, NomMonde='Importe'))
        if code != 0 or c or s != serveur(monde='Importe'):
            soucis.append('aller-retour « monde importé » : %s %s %s' % (code, c, s))
        code, texte, c, s = lancer(tmp, dict(DEFAUTS, NomMonde='Autre'))
        if code != 0 or not c or 'create#Autre#' not in c:
            soucis.append('aller-retour « autre nom = nouveau monde » : %s %s' % (code, c))
        if not [x for x in soucis if x.startswith('aller-retour')]:
            ok('aller-retour', '%d cas par le vrai lanceur (bash), dont 3 sur un monde existant' % (len(CAS) + 3))
        # sans les fichiers du jeu : message clair, code 1
        os.remove(os.path.join(tmp, 'jeu', 'Aloft.exe'))
        code, texte, c, s = lancer(tmp, DEFAUTS)
        if code != 1 or '1660080' not in texte:
            soucis.append('lanceur sans Aloft.exe : message ou code inattendu')
        p = subprocess.run([bash, os.path.join(tmp, 'lancer-aloft.sh').replace('\\', '/'), 'preparer', 'composants=vcrun2022'],
                           capture_output=True, timeout=60)
        if p.returncode != 1 or b'POSSEDE' not in p.stdout:
            soucis.append('lancer-aloft.sh preparer sans le jeu : message ou code inattendu')

# ── 9. regex de console ──────────────────────────────────────────────────────
pret = re.findall(r'echo "(TeamKit : Aloft est pret\. Code pour rejoindre : [^"]*)"', script)
if len(pret) != 2:
    soucis.append('les deux lignes « prêt » du lanceur sont introuvables')
else:
    ESSAIS = [
        ('Console.AppReadyRegex', pret[0].replace('$code', '482913'), True),
        ('Console.AppReadyRegex', pret[1], True),
        ('Console.AppReadyRegex', 'TeamKit : ATTENTION, Aloft n\'a toujours ni code ni "Server Ready" apres 15 minutes.', False),
        ('Console.AppReadyRegex', 'Server Ready', False),
        ('Console.AppReadyRegex', 'TeamKit : monde TeamKit cree.', False),
        ('Console.AppReadyRegex', 'TeamKit : Aloft est pret. Code pour rejoindre : ', False),
    ]
    for cle, ligne, attendu in ESSAIS:
        if bool(py(cles[cle]).search(ligne)) != attendu:
            soucis.append('%s %s : %s' % (cle, 'devrait reconnaître' if attendu else 'ne devrait pas reconnaître', ligne))
    ok('console', '%d lignes testées' % len(ESSAIS))
for champ, motif in (('NomMonde', r'[A-Za-z0-9]{1,20}'), ('NomServeur', r'[A-Za-z0-9_-]{1,64}')):
    if not re.fullmatch(motif, DEFAUTS[champ]):
        soucis.append('valeur par défaut de %s refusée par le lanceur' % champ)
if 'TeamKit' not in DEFAUTS['NomServeur']:
    soucis.append('le nom du serveur par défaut doit citer TeamKit')

print()
if soucis:
    print('%d problème(s) :' % len(soucis))
    print('\n'.join('  NON  ' + s for s in soucis))
    sys.exit(1)
print('Tout est bon.')
