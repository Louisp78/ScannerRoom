# Cartographie sous-marine des côtes — Spécification produit

## Vision

Une application web permettant de visualiser les fonds côtiers du globe sous forme de **"Street View sous-marin"** : une carte mondiale où chaque portion de côte scannée est explorable en 3D, en défilement continu. La donnée est capturée une seule fois (vidéo de transect), puis présentée différemment selon le public.

---

## Utilisateurs cibles

| Profil | Besoin principal |
|--------|------------------|
| **Scientifique / chercheur** | Accéder aux modèles 3D détaillés, aux métriques (rugosité, couverture benthique), comparer l'évolution d'un site dans le temps, exporter les données brutes. |
| **Plongeur (plongée sous-marine)** | Repérer un site avant une sortie : profondeur, relief, vie marine visible, difficulté. |
| **Snorkeleur** | Savoir en un coup d'œil si un spot côtier vaut le détour (accessibilité, faible profondeur, intérêt visuel). |
| **Cadre pédagogique (enseignant, médiateur, étudiant)** | Illustrer les écosystèmes marins, faire "visiter" un fond sans plonger, support de cours interactif. |

---

## Features & User stories

### 1. Carte mondiale des côtes

- **US-1.1** — En tant qu'utilisateur, je veux voir une carte du monde avec les sites scannés matérialisés par des points, afin de repérer où de la donnée existe.
- **US-1.2** — En tant qu'utilisateur, je veux cliquer sur un point pour ouvrir un aperçu léger du site (vignette, profondeur, tags de vie marine), afin de décider si je veux l'explorer.
- **US-1.3** — En tant qu'utilisateur, je veux filtrer les sites (profondeur, type de public, présence de corail/tortue/etc.), afin de trouver ce qui correspond à mon besoin.
- **US-1.4** — En tant qu'utilisateur, je veux que seuls les points visibles à l'écran soient chargés, afin que l'app reste fluide.

### 2. Viewer 3D scrollable

- **US-2.1** — En tant qu'utilisateur, je veux ouvrir la reconstruction 3D d'un site et naviguer dedans, afin de visualiser le fond marin.
- **US-2.2** — En tant qu'utilisateur, je veux avancer en défilement continu le long de la côte (comme Street View), afin d'explorer sans changer de "scène".
- **US-2.3** — En tant qu'utilisateur, je veux que le modèle 3D lourd ne se charge qu'à la demande, afin d'éviter les temps de chargement inutiles.
- **US-2.4** — En tant que scientifique, je veux basculer vers une vue détaillée (métriques, historique, export), afin d'exploiter la donnée scientifiquement.

### 3. Découpage en tuiles (streaming)

- **US-3.1** — En tant qu'utilisateur, je veux que la scène 3D se charge par morceaux (tuiles) selon ma position virtuelle, afin de naviguer sur de longues distances sans tout télécharger.
- **US-3.2** — En tant qu'utilisateur, je veux un niveau de détail adaptatif (LOD) selon le zoom, afin d'avoir de la fluidité de loin et de la précision de près.
- **US-3.3** — En tant que contributeur, je veux uploader une vidéo de transect géolocalisée, afin qu'elle soit reconstruite et ajoutée à la carte.

---

## Périmètre MVP

Objectif du MVP : **valider la sensation "scroll sous-marin" sur un seul transect**, avec une carte minimale.

### Inclus dans le MVP

- **US-1.1** — Carte mondiale avec points des sites.
- **US-1.2** — Aperçu léger au clic sur un point.
- **US-2.1** — Viewer 3D d'un site.
- **US-2.2** — Défilement le long d'une trajectoire prédéfinie (un seul transect).
- **US-2.3** — Chargement à la demande du modèle 3D.

### Hors MVP (versions ultérieures)

- **US-1.3 / US-1.4** — Filtres avancés et chargement par zone.
- **US-2.4** — Vue scientifique détaillée + export.
- **US-3.1 / US-3.2** — Vrai système de tuiles + LOD à l'échelle planétaire.
- **US-3.3** — Pipeline d'upload et de reconstruction automatisé.

---

## Notes techniques (indicatives)

- **Rendu 3D** : WebGL / Three.js dans le navigateur.
- **Méthode de reconstruction** : Gaussian Splatting privilégié pour un rendu photoréaliste haute résolution (mesh classique type Meshroom possible pour un premier jet).
- **Streaming à terme** : format de tuiles 3D géo-indexées (ex. approche Cesium 3D Tiles) pour la navigation continue.
- **Principe directeur** : une seule source de données brute, deux couches de présentation (grand public léger / scientifique détaillé).
