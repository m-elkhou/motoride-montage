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
