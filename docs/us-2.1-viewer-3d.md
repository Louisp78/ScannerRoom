# US-2.1 — Viewer 3D d'un site

> En tant qu'utilisateur, je veux ouvrir la reconstruction 3D d'un site et naviguer dedans, afin de visualiser le fond marin.

## Contexte

Le viewer 3D est le cœur du MVP : il doit valider la sensation "scroll sous-marin" (cf. specs.md). Il sera ensuite étendu par US-2.2 (défilement continu le long d'un transect), US-2.3 (chargement à la demande), puis US-2.4, US-3.1 et US-3.2 (vue scientifique, tuiles, LOD). Ces évolutions ont pesé sur les choix ci-dessous.

## Décisions

### Séparation GUI / moteur 3D

- **Coquille applicative (GUI) : Vue.** Gère la carte, le routage entre la carte et le viewer, les panneaux et overlays (chargement, métadonnées de site).
- **Moteur 3D : module Three.js agnostique du framework.** Une classe indépendante possède la scène, la caméra, le renderer, la boucle de rendu et le chargement des assets. Vue se contente de monter un canvas, d'instancier le moteur, de le détruire au démontage, et communique avec lui via un pont d'état léger (store/callbacks : progression caméra, état de chargement, site sélectionné) plutôt que d'exposer les objets 3D individuels comme props réactives.

**Pourquoi :** la suite de la roadmap (caméra pilotée en continu le long d'une trajectoire, streaming de tuiles, LOD, puis rendu Gaussian Splatting) est dominée par des systèmes impératifs, pilotés frame par frame, avec beaucoup de chargement/déchargement. Les wrappers déclaratifs (type TresJS/React Three Fiber) conviennent bien à des scènes "qui réagissent à des props", pas à ces systèmes écrits à la main — les faire passer par un reconciler ajouterait une couche à combattre plutôt qu'une aide. De plus, les moteurs de rendu Gaussian Splatting sont impératifs par nature, sans binding déclaratif mature dans aucun framework : le moteur devait de toute façon rester agnostique.

**Implication :** le code du moteur (scène, caméra, loaders, streaming, LOD) doit rester hors des composants Vue. Les composants Vue ne font que monter/démonter le moteur et relayer un pont réactif minimal. Ne pas introduire TresJS ou équivalent sans revenir explicitement sur cette décision.

### Format de l'asset 3D (MVP)

- **Mesh classique (glTF/GLB)**, issu par exemple d'une reconstruction Meshroom — pas de Gaussian Splatting pour le MVP.

**Pourquoi :** le glTF/GLB bénéficie d'un outillage Three.js mature (`GLTFLoader`, compression Draco/meshopt, contrôles de caméra prêts à l'emploi), ce qui permet de valider vite l'expérience de navigation. Le Gaussian Splatting reste la cible qualité à long terme (cf. specs.md) mais ajoute un risque d'immaturité d'outillage et de poids de fichiers non nécessaire pour le MVP.

## Autre

- Modèle de navigation caméra détaillé pour US-2.1 vol libre on charge x tuile autour de la camera et quand elle se déplace elle charge les tuile correspondant; comme dans un jeux video ou on charge des chunks.
- Structure de dossiers / scaffolding du projet Vue :
  - eslint oxlint (utiliser la command d'init du site officiel a jour)
  - prettier
  - husky avec pre commit lint, pour message de conventional commit
  - ci github avec le job : build -> format, lint
