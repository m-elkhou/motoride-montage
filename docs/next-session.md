# Next session

Brief for the next working session on video generation and montage (written 2026-11-13, for a new Claude
session on Claude Fable 5.2). Paste the block below as the first message.

```text
Nouvelle session : retravailler la GÉNÉRATION et le MONTAGE des vidéos de ma chaîne moto.

Deux dépôts, à lire AVANT tout le reste :
- C:\workdir\uw\scraper\motoride-montage : le moteur de montage (docs/handoff.md, docs/todo.md,
  docs/review.md R25-R32, docs/pipeline/*.md).
- C:\workdir\uw\scraper\social2shorts : le client YouTube, l'OAuth, les envois programmés, les références de ma
  voix (docs/handoff.md, docs/todo.md).
Lis aussi tes fiches mémoire : anonymity-absolute-rule, motoride-montage-public-repo, insta2youtube-motoride,
youtube-channel-standing-rules, git-explicit-authorization, after-merge-delete-branch-switch-main.

CE QUE JE VEUX
1. Musique TENDANCE, rythme moderne et plein d'énergie : pop marocaine, rap/pop marocain, pop anglaise et les
   autres tendances du moment (Shorts, TikTok, Reels ; Maroc, France, monde). Fais d'abord une recherche web
   des sons qui tendent MAINTENANT (titres, artistes, BPM, énergie), puis propose-moi une sélection.
2. Une NARRATION parlée avec MA voix clonée, comme ce Short : https://www.youtube.com/shorts/X__udVaBnUQ
   (c'est une de mes vidéos, reprise de mon TikTok par social2shorts ; source :
   social2shorts\work\copies\7483999753433550085.mp4, texte : social2shorts\work\subtitles\7483999753433550085.srt).
   Style : un monologue d'environ 50 s, phrases courtes, à la 2e personne, qui monte en intensité (« Quand on est
   à 150 à l'heure, il se passe quelque chose de spécial… Tu fais partie de la route… »). Écris des textes
   ORIGINAUX dans ce style (pas de citation de film protégée), en français d'abord.
3. Un montage qui suit le rythme de la musique, avec la voix bien devant la musique (ducking), et des
   sous-titres mot à mot lisibles.

DÉCISION À ME FAIRE PRENDRE AVANT TOUT RENDU : les droits de la musique tendance
- Un titre commercial envoyé par l'API est réclamé par Content ID (déjà constaté sur la chaîne) : revenus aux
  ayants droit, blocage possible selon le label ou le pays.
- Les « sons » sous licence de l'appli YouTube Shorts ne s'ajoutent qu'à la main, dans l'appli.
- Une bibliothèque sous licence (abonnement type Epidemic Sound ou Artlist, chaîne déclarée) donne des titres
  « dans le style tendance » sans réclamation ; la bibliothèque audio YouTube est gratuite mais moins tendance.
Présente-moi ces options (coût, risque, automatisable ou non) et attends mon choix. Jamais de musique obtenue
de façon illégale ; si je choisis des titres commerciaux, c'est moi qui fournis les fichiers.

ÉTAT TECHNIQUE (vérifié le 13/11)
- L'environnement de rendu C:\workdir\_s2s_cb\venv N'EXISTE PLUS (local_paths.json y pointe encore) et les poids
  des modèles ont été vidés du cache Hugging Face. Recrée un venv Python 3.12 : torch CUDA, Chatterbox
  Multilingual, transformers compatible, open_clip_torch, librosa, opencv-python, soundfile, numpy ; les modèles
  se re-téléchargent au premier usage. Vérifie le GPU.
- La voix et la réécoute sont écrites pour l'anglais : language_id="en" dans scan/gen_vo_clone.py et
  language="en" dans mm_voicecheck.py. Rends la langue configurable (fr, en, ar) ; clone depuis mes
  références FR : social2shorts\work\voiceover\ref_fr2_full.wav (125 s), ref_fr_full.wav (60 s),
  ref_fr3_full.wav (26 s), ref_fr2_expr.wav (13 s). Chaque prise doit repasser la validation Whisper
  (aucune répétition, aucun mot coupé, exactement le texte) : c'est la plainte n°1 du propriétaire.
- La matière vidéo vérifiée est presque épuisée sous la règle d'anonymat stricte (34 s de POV, 16 s de motos).
  Demande-moi : nouvelles images, ou assouplir « aucune autre personne » pour un motard casqué au loin, ou un
  thème « paysage ».

RÈGLES PERMANENTES
- Anonymat : jamais mon visage (même casque ouvert), jamais une autre personne proche ni une femme à l'image,
  aucune plaque ni papier lisible, aucun plan pris depuis une voiture. Doute = PRIVATE. Audit automatique PUIS
  relecture des planches par 3 relecteurs indépendants avant toute approbation.
- Rien d'envoyé ni de programmé sur YouTube sans mon « go ».
- social2shorts tourne en production (tâche planifiée, chaque heure à hh:05, depuis le dossier principal) :
  travaille dans un worktree, ne coupe jamais un passage en cours.
- Mémoire : 16 Go. Un seul gros modèle à la fois (Chatterbox, Whisper, détecteurs) : processus séparés.
- Git : commit seulement quand je dis « commit », puis toute la chaîne (push, PR, CI, merge) ; aucune signature
  Claude ; après le merge, supprime la branche locale et reviens sur main à jour.
- Descriptions YouTube : texte détaillé, signature Instagram, hashtags à la fin (règle stricte des 2 dépôts).
- Tiens à jour docs/handoff.md, docs/todo.md et la doc des deux dépôts à la fin de chaque lot.

Commence par : lire les handoffs, recréer l'environnement, faire la recherche des tendances, puis me présenter
le plan et la décision sur les droits de la musique.
```

## Why these points

| Point | Where it comes from |
|---|---|
| Trending music, Moroccan pop, English pop | owner, 2026-11-13 |
| Narration like the reference Short | owner, 2026-11-13; the reference is the owner's own TikTok re-published by social2shorts |
| Licensing decision first | commercial tracks get claimed through the API ([Music](pipeline/music.md)) |
| Rebuild the environment | the render venv and the model weights were gone on 2026-11-13 ([Handoff](handoff.md)) |
| French voice and re-listening | the voice stage and Whisper are hard-wired to English today ([Voice](pipeline/voice.md)) |
| Footage first | the strict review exhausted the verified footage ([Review](review.md), R31) |
