# Next session

Brief for the next working session on video generation and montage (rewritten 2026-11-16; the brief of
2026-11-13 is done: environment rebuilt, French voice stage, trend research, music decision, first narrated
pilot). Paste the block below as the first message.

```text
Nouvelle session : finir le premier Short NARRÉ de ma chaîne moto (pilote 01), puis en faire d'autres.

Deux dépôts, à lire AVANT tout le reste :
- C:\workdir\uw\scraper\motoride-montage : le moteur de montage (docs/handoff.md, docs/todo.md,
  docs/pipeline/narration.md, docs/pipeline/music.md).
- C:\workdir\uw\scraper\social2shorts : le client YouTube, l'OAuth, les envois programmés, les références de ma
  voix (docs/handoff.md, docs/todo.md).
Le travail du pilote est hors dépôt : C:\workdir\_s2s_cb\pilot01 (scripts, prises de voix, plans, rendus).

OÙ ON EN EST (16/11)
- Le pilote existe (37 s, plaques floutées, sous-titres mot à mot) et sa version « voix seule » est sur la chaîne
  en PRIVÉ. Rien n'est publié.
- J'ai trouvé sa voix encore ROBOTIQUE. Deux causes ont été mesurées et corrigées sur les mêmes prises (voir le
  handoff) ; la narration corrigée attend mon écoute : C:\workdir\_s2s_cb\pilot01\ecoute\.
- La vidéo porte encore l'ancienne voix. Avec la nouvelle, la narration dure 4,7 s de plus : tous les plans
  bougent.

CE QUE JE VEUX
1. Me demander d'abord mon avis sur la voix corrigée. Si elle ne me convient pas : essayer une amorce de ma voix
   plus propre et dans le ton du texte, plus de prises par phrase choisies sur leur qualité mesurée, puis
   l'entraînement du modèle sur un enregistrement de moi (10 à 30 minutes) ; me faire écouter avant d'aller plus
   loin.
2. Refaire le pilote avec la voix validée : plan, rendu, audit automatique, puis relecture des planches par
   3 relecteurs indépendants. Regarder les « doutes » du rapport (détections larges laissées visibles).
3. Musique : je choisis un titre pop, rap ou jazz de la bibliothèque audio YouTube (liste dans
   C:\workdir\_s2s_cb\channel\musiques_youtube\) ; le mixer sous ma voix (un instrumental).
4. Faire entrer les scripts du pilote dans le dépôt, avec des tests, puis préparer les Shorts narrés suivants.

DÉCISIONS QUI SONT LES MIENNES (ne pas trancher à ma place)
- Un autre motard très loin devant, de dos : acceptable ou non.
- Publier le pilote, et avec quelle musique.

RÈGLES PERMANENTES
- Anonymat : jamais mon visage (même casque ouvert), jamais une autre personne proche ni une femme à l'image,
  aucune plaque ni papier lisible, aucun plan pris depuis une voiture. Doute = PRIVATE. Audit automatique PUIS
  relecture des planches par 3 relecteurs indépendants avant toute approbation.
- Rien d'envoyé ni de programmé sur YouTube sans mon « go ».
- social2shorts tourne en production (tâche planifiée, chaque heure à hh:05, depuis le dossier principal) :
  travaille dans un worktree, ne coupe jamais un passage en cours.
- Mémoire : 16 Go. Un seul gros modèle à la fois (voix, Whisper, détecteurs) : processus séparés, et fermer ce
  qui ne sert pas avant un rendu.
- Git : commit seulement quand je dis « commit », puis toute la chaîne (push, PR, CI, merge) ; aucune signature
  Claude ; après le merge, supprime la branche locale et reviens sur main à jour.
- Descriptions YouTube : texte détaillé, signature Instagram, hashtags à la fin (règle stricte des 2 dépôts).
- Jamais de musique obtenue de façon illégale ; citer un titre commercial ne donne aucun droit.
- Tiens à jour docs/handoff.md, docs/todo.md et la doc des deux dépôts à la fin de chaque lot.

Commence par : lire les handoffs, puis me demander mon avis sur la voix corrigée.
```

## Why these points

| Point | Where it comes from |
|---|---|
| The voice first | owner, 2026-11-16: "the sound is still robotic"; causes and corrected narration in the [Handoff](handoff.md) |
| Rebuild, audit, three reviewers | the corrected narration is longer, so every shot moves ([Narrated montage](pipeline/narration.md)) |
| Music from the YouTube Audio Library | owner, 2026-11-16; the library and its two licences are in [Music](pipeline/music.md) |
| Pilot scripts into the repository | they still live outside it ([TODO](todo.md)) |
| Distant riders, publishing | open decisions of the owner ([Handoff](handoff.md)) |
