# Playground — de la vidéo de transect au nuage de points

Bac à sable **hors application** : il fabrique de la donnée de test réaliste pour le
viewer 3D à partir de vraies vidéos de transect sous-marin. Rien ici n'est importé
par l'app Vue ; le seul lien avec elle est le dossier exporté dans
`public/transects/<clé>/`, que le viewer charge sur la route `/transects/<clé>`.

## Source de données

[NOAA NCEI, accession 0172858](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc:0172858) —
*Video transects of coral reefs on the west coast of the island of Hawaii*
(février 2017). 27 vidéos MP4 filmées par des plongeurs le long de transects
balisés, sur 7 sites entre Kona et North Kohala, de 0,2 à 1,7 Go chacune.

Pourquoi cette source : c'est exactement le geste de captation visé par le produit
(un plongeur qui longe une côte corallienne, caméra vers le récif), la donnée est
publique (œuvre du gouvernement américain, sans restriction), et chaque fichier est
téléchargeable individuellement en HTTP, sans compte.

Vidéo utilisée par défaut : `Old Kona Site 3 2017-02-05 Transect 2 South Leg Return full.MP4`
(219 Mo, 1440×1080, 30 fps, 2 min 32 — la plus légère de l'accession).

## Pipeline

```bash
cd playground/scripts
./00-setup-lingbot.sh             # installe LingBot-Map (une seule fois)
./01-fetch-transect.sh            # télécharge la vidéo (--list pour les autres)
./02-extract-frames.sh            # vidéo -> séquence d'images
./03-reconstruct.sh               # images -> poses caméra + profondeur (LingBot-Map)
./04-export-web.sh                # nettoyage -> public/transects/<clé>/
```

Chaque étape écrit dans son propre dossier (`transects/`, `frames/`, `out/`), tous
ignorés par git : ces artefacts sont lourds et reproductibles à partir des scripts.
N'importe quel sous-dossier de `frames/` fait une clé valide.

L'extraction se règle par variables d'environnement :

```bash
FPS=3 START=30 DURATION=90 ./02-extract-frames.sh
```

Elle écrit aussi `frames/<clé>.json` (fps et début de fenêtre), dont l'étape 04 se
sert pour dater chaque image dans la vidéo source. Le fichier est posé **à côté**
du dossier d'images et non dedans, pour que la reconstruction ne voie que des images.

## Étape 03 — LingBot-Map

[LingBot-Map](https://github.com/robbyant/lingbot-map) (Ant Group, Apache 2.0) est
un modèle de reconstruction 3D en flux, dérivé de VGGT. On utilise son portage
[MLX](https://github.com/uqer1244/mlx_lingbot-map) pour Apple Silicon, figé à un
commit précis par `00-setup-lingbot.sh` et installé dans `vendor/` (ignoré par git,
poids FP16 de 2,2 Go téléchargés au premier lancement).

Fonctionnement, en bref :

1. un encodeur DINOv2 découpe chaque image (redimensionnée en 518×378) en patchs
   de 14 px et les décrit ;
2. un transformer compare les patchs de l'image courante à une mémoire des images
   passées (fenêtre glissante de 16 images, plus les 4 premières gardées comme
   référence d'échelle) ;
3. des têtes de sortie prédisent la pose de la caméra, une profondeur par pixel et
   une **confiance** par pixel (1,0 = « aucune idée ») ;
4. pixel + profondeur + pose donnent un point 3D, par simple géométrie.

C'est une **prédiction directe**, sans appariement de points ni ajustement de
faisceaux : environ 2 s par image sur un M3 Pro, là où la photogrammétrie classique
échouait souvent sur le voile et le flou sous-marins.

Ce que ça implique pour la donnée :

- **Échelle arbitraire.** Aucune référence métrique ; les distances sont relatives.
- **Portée courte.** Au loin, le récif se fond dans le bleu : le modèle le dit
  (confiance 1,0) et ces pixels sont écartés.
- **Dérive possible** sur de longues séquences, la mémoire ne couvrant que les
  dernières images.
- **Jamais entraîné sur du sous-marin.** Ça tient sur ce transect, sans garantie
  ailleurs.

## Étape 04 — export pour le viewer

`export-web.py` transforme l'archive `.npz` de l'étape 03 en deux fichiers :

| Fichier | Contenu |
| --- | --- |
| `cloud.ply` | Nuage de points coloré, binaire, ~1,1 M de points (18 Mo pour 60 s de vidéo, contre 165 Mo et 11 M de points en sortie brute). |
| `path.json` | Une position caméra par image et son horodatage dans la vidéo : la trajectoire du plongeur. |

Le nettoyage enchaîne quatre filtres :

1. **Confiance** au-dessus de `CONF` (1,05 par défaut) : garde ~57 % des pixels.
2. **Eau libre** : pixels à dominante bleue et sans texture, masque élargi de
   quelques pixels car la profondeur est peu fiable sur la silhouette du récif
   (points « volants »).
3. **Grille de voxels** de taille `VOXEL` (0,008 par défaut) : un point moyen par
   voxel.
4. **Points isolés** : retrait statistique sur la distance aux 8 voisins.

```bash
CONF=1.2 VOXEL=0.012 ./04-export-web.sh
```

### Piège : le portage MLX inverse les poses caméra

Au commit figé, `create_map.py` décode les poses comme « monde → caméra » et les
inverse, alors que le modèle prédit « caméra → monde ». Son `extrinsic_w2c` est
donc la vraie pose caméra → monde, et ses `world_points` sont faux. Symptômes : le
plongeur recule au lieu d'avancer, le transect apparaît **en miroir**, et les
images successives se recalent mal (nuage flou, surfaces dédoublées).

Vérifié en reprojetant chaque image k dans l'image k+2 : écart médian de
profondeur de **2,2 %** avec la bonne lecture, contre **11,7 %** avec celle du
portage. `export-web.py` reconstruit donc lui-même les points 3D à partir de la
profondeur, des intrinsèques et des poses corrigées. Effet de bord bienvenu :
à voxel égal, le nombre de points tombe de moitié, signe que les vues se
superposent enfin sur les mêmes surfaces — d'où un voxel par défaut plus fin.

La trajectoire est lissée ici, pas dans le viewer : position et direction de
visée de la caméra passent par un filtre gaussien dont la largeur est exprimée en
**secondes de vidéo** (`PATH_SMOOTH`, 1 s, et `HEADING_SMOOTH`, 1,5 s, par défaut).
Le réglage vaut donc pour n'importe quel transect et n'importe quel `FPS`
d'extraction. Le viewer se contente d'interpoler (spline Catmull-Rom pour la
position, interpolation linéaire pour la direction) : en lecture, la caméra suit
le chemin et regarde là où le plongeur filmait.

Les coordonnées restent dans le repère de la reconstruction (convention OpenCV :
x à droite, y vers le bas, z vers l'avant) ; c'est le viewer qui les convertit.

## Pistes testées et écartées

**Correction colorimétrique avant inférence** (étirement par canal + CLAHE),
mesurée sur les 40 images du jeu smoke : pixels conservés 63 % → 57 %, portée
typique 1,61× → 1,16× la profondeur médiane. Le modèle semble se servir du voile
bleu comme indice de distance ; le retirer le rend moins sûr de lui. Les images
brutes donnent un meilleur résultat.

## Historique

La première version de ce pipeline reposait sur NodeODM/OpenDroneMap
(photogrammétrie CPU en conteneur). Abandonnée : longue, complexe à régler pour du
sous-marin, et de qualité insuffisante.
