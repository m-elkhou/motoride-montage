# Viral DNA — ADN des Shorts moto viraux (mesuré le 07/11/2026, 150 Shorts moto ≥1M vues, 23 téléchargés et analysés)

!!! note "Notes en français, mesurées le 07/11/2026"
    Échantillon : 150 Shorts moto ≥ 1 M de vues, 23 analysés en détail. Les scripts de collecte utilisés pour cette mesure ne font pas partie du dépôt.

## Ce qui fait les vues (par famille, vues cumulées sur l'échantillon)
1. **Edit / POV esthétique** — 48 Shorts, 406M : montage **calé sur le beat** (3–7 coupes/10 s) ou **un plan fort**, musique 120–140 BPM (trap/phonk/dramatique), hook texte en haut.
2. **Drame / near-miss** — 27 Shorts, 292M : police vs motard, sauvetage, accident évité, bus dangereux. **Un seul plan brut**, 13–23 s, titre-histoire.
3. **Son / échappement** — 8 Shorts, 53M : "LOUD … exhaust", pure sound, 0 coupe, son fort. Exige un VRAI micro (pas de vent).
4. Comédie / skits, produits/gear : secondaires.

## Les constantes (mesurées)
- **Durée 13–23 s** (médiane ~18 s). Jamais 30–45 s.
- **0 voix-off.** Quand on entend une voix, c'est du dialogue brut de la scène.
- **Niveau sonore fort** (‑13/‑17 dB RMS), master hot. Musique **120–140 BPM**.
- **Texte** : 2–6 mots, en haut, gras, contour noir ou boîte, souvent 1 emoji ; légende « histoire » possible (« Saved a Child », « Police vs Biker »).
- **Titre** = curiosité/enjeu/contraste (« Everyone's stuck. I'm not. », « Alguém me explica essa bike? »).
- **La qualité d'image n'est pas le facteur** : beaucoup de 4:3 letterboxés, caméras de téléphone. Le MOMENT l'est.
- Beaucoup de plans à la **3e personne** (motard filmé, interactions, réactions) : le POV pur est minoritaire.

## Ce que ça change pour la chaîne
- **Zéro narration posée.** Musique dark-trap/cinématique (libre de droits, à placer dans `public/`) ou son moteur réel s'il existe.
- **18 s max**, coupes sur le beat, slow-mo sur le drop, grade contrasté → moteur `viral_cut.py`.
- **Chercher des MOMENTS** dans les rushs (interactions, groupe, lumières, neige, ferry, réactions) plutôt que de "belles balades".
- **Tourner différemment** : un plan à la 3e personne par sortie (pote qui filme), un **micro** pour le son moteur (le vent du téléphone tue la famille "son"), capter les réactions.
- Musiques tendance TikTok/Reels : **interdites sur YouTube** (claim) sauf via la bibliothèque "Sons" de l'app Shorts (upload manuel). Via l'API : **YouTube Audio Library uniquement**.

## Mise à jour 2026 : le top 100 mondial (10 novembre 2026)

**Méthode.** YouTube Data API (lecture seule) : 60 recherches (10 mots-clés moto x 6 régions, tri par vues, Shorts de
moins de 61 s publiés depuis le 1er janvier 2026) -> 490 Shorts, dont 450 parlent vraiment de moto (les annonces
de téléphones « moto g » polluent le mot-clé `moto` et sont retirées). Le **top 100** va de **27 M à 363 M de vues**.

| Mesure du top 100 | Valeur |
|---|---|
| Durée | P10 12 s, P25 16 s, **médiane 23 s**, P75 40 s, P90 59 s ; 38 % entre 11 et 20 s, 39 % au-delà de 30 s |
| Hashtags les plus fréquents | `#shorts` 34 %, `#motorcycle` 22 %, `#motovlog` 13 %, `#viral` 11 %, `#bike` 10 %, `#funny` 7 %, `#biker` 6 % |
| Mots du titre ou de la description | « vlog » 15 %, « edit » 13 %, « funny » 12 %, « rider » 11 %, « superbike » 8 %, « crash » 6 %, « phonk » 2 % |
| Auteurs | 89 chaînes différentes pour 100 vidéos : aucun auteur ne domine |

**Ce qui marche en 2026** (vignettes des 36 premiers) : des **sketchs et blagues**, des histoires courtes (« Karen »,
rencontres sur la route), des astuces d'atelier, des **classements** (« Ranking the best throttle moments ») avec des
numéros à l'écran, des figures (saut, burnout), des caméras casque avec une **légende narrative** (« POV : ... »), et
presque toujours un **gros texte à l'écran dès la première seconde**. Les montages purement esthétiques sont rares. Un
titre court, un appel au commentaire (« Comment BIKE if you want one », 143 M de vues en 15 s) et les séries
(« Day 22/1000 ») reviennent souvent.

**Ce que le moteur en retient** (ce qui ne dépend ni d'un visage ni d'un événement) :
- **texte d'abord** : accroche de 3 à 6 mots en haut (question, « POV : ... », attente : « Wait for the turn »), et un
  **appel au commentaire** à la fin (« Comment BIKE if you ride ») : listes `HOOKS` et `OUTROS` de `scan/gen_batch.py` ;
- **15 à 25 s** (le P25 à la médiane) plutôt que 18 s fixes ;
- musique **moderne et énergique**, uniquement de la bibliothèque audio YouTube (aucune réclamation) ;
- la voix de l'accroche est la **voix clonée du propriétaire**, à un débit posé.

