# -*- coding: utf-8 -*-
"""Langue de la voix (en, fr, ar) : quels MOTS comparer entre la phrase voulue et ce que Whisper a entendu.

mm_voicecheck.py refuse un essai de voix si Whisper n'entend pas exactement les mots voulus. « Exactement » depend de
la langue :
  - anglais : la regle d'origine (« P.O.V. » = « pov », sigle epele, quelques homophones) ;
  - francais : Whisper ecrit « d 'un » pour « d'un », des chiffres pour des nombres dits en mots, et choisit seul
    l'orthographe d'un son (« bat » entendu « bas ») : les elisions sont separees, les chiffres developpes, les sigles
    epeles reunis, et deux mots de meme son (`sound_fr`) comptent pour le meme mot ;
  - arabe : les signes de vocalisation (tashkeel) et l'allongement (tatweel) sont retires, les formes d'alef unifiees,
    les ligatures de presentation ramenees a leurs lettres (NFKC).

En francais et en arabe, toute suite de lettres ou de chiffres est un mot, quelle que soit l'ecriture : une fin de
phrase inventee dans un autre alphabet (« Спасибо », « 谢谢 ») compte comme des mots en trop. L'anglais garde sa regle
d'origine, lettres latines sans accent seulement : les voix anglaises deja validees le restent.

Langue par defaut : variable MM_VOICE_LANG, sinon cle `voice_lang` de local_paths.json, sinon « en ».
Bibliotheque standard seulement (aucun modele, aucun dictionnaire).
"""
import re
import unicodedata

import mm_paths

LANGS = ("en", "fr", "ar")
HOMOPHONES = {"rode": "road", "rowed": "road", "ok": "okay"}       # anglais : ramenes a une seule forme
_WORD = re.compile(r"[^\W\d_]+|\d+")              # une suite de lettres (de n'importe quelle ecriture) ou de chiffres


def checked(lang):
    """La langue si elle est geree, sinon ValueError qui nomme les valeurs permises."""
    if lang not in LANGS:
        raise ValueError(f"langue de voix inconnue : {lang!r} (valeurs permises : {', '.join(LANGS)})")
    return lang


def default_lang():
    """Langue quand `--lang` n'est pas donne : MM_VOICE_LANG, sinon `voice_lang` de local_paths.json, sinon en."""
    return checked(str(mm_paths._get("voice_lang", "MM_VOICE_LANG", "en")).strip().lower())


# ───────────────────────── anglais ─────────────────────────

def _words_en(text):
    """Regle d'origine de mm_voicecheck.normalize_words, inchangee : les voix anglaises deja validees le restent."""
    t = str(text).lower().replace("p.o.v.", " pov ").replace("p.o.v", " pov ").replace("’", "'")
    words = re.findall(r"[a-z0-9']+", t)
    merged = []                                   # sigle epele lettre par lettre (« P O V ») = un seul mot (« pov »)
    for w in words:
        if len(w) == 1 and w.isalpha() and merged and merged[-1][1]:
            merged[-1] = (merged[-1][0] + w, True)
        else:
            merged.append((w, len(w) == 1 and w.isalpha()))
    return [HOMOPHONES.get(w, w) for w, _ in merged]


# ───────────────────────── francais ─────────────────────────

_FR_UNITS = "zéro un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize".split()
_FR_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}
# milliers ecrits en groupes de trois chiffres : « 1 000 », « 10 000 » (espace, insecable ou fine), « 1.000 »
_FR_GROUPS = re.compile(r"(?<!\d)\d{1,3}(?:[ .\N{NO-BREAK SPACE}\N{NARROW NO-BREAK SPACE}]\d{3})+(?!\d)")
_FR_DOTTED = re.compile(r"(?<!\w)(?:[a-z]\.){2,}(?:[a-z](?!\w))?")        # sigle a points : p.o.v., g.p.s.
_FR_TOKEN = re.compile(r"aujourd'hui|" + _WORD.pattern)


def number_fr(n):
    """Mots francais d'un entier de 0 a 999 999, un mot par element (les traits d'union separent des mots) :
    80 -> quatre vingts, 21 -> vingt et un, 150 -> cent cinquante, 1000 -> mille, 200 000 -> deux cent mille."""
    if n < 17:
        return [_FR_UNITS[n]]
    if n < 20:
        return ["dix", _FR_UNITS[n - 10]]
    if n < 100:
        tens, unit = divmod(n, 10)
        if tens in (7, 9):                        # soixante-dix, quatre-vingt-dix : la dizaine d'avant, puis 10 a 19
            tens, unit = tens - 1, unit + 10
        if tens == 8:                             # quatre-vingts ; quatre-vingt-un, quatre-vingt-onze (sans « et »)
            return ["quatre", "vingt"] + number_fr(unit) if unit else ["quatre", "vingts"]
        if not unit:
            return [_FR_TENS[tens]]
        return [_FR_TENS[tens]] + (["et"] if unit in (1, 11) else []) + number_fr(unit)
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = [] if hundreds == 1 else [_FR_UNITS[hundreds]]
        return head + (["cent"] + number_fr(rest) if rest else ["cent" if hundreds == 1 else "cents"])
    thousands, rest = divmod(n, 1000)
    head = [] if thousands == 1 else number_fr(thousands)
    if head and head[-1] in ("cents", "vingts"):  # devant « mille » : deux cent mille, quatre-vingt mille (sans s)
        head[-1] = head[-1][:-1]
    return head + ["mille"] + (number_fr(rest) if rest else [])


def _merge_spelled(words):
    """Sigle epele lettre par lettre (« P O V », « G P S ») = un seul mot : les lettres latines seules qui se suivent
    sont collees, exactement comme en anglais (« y a » devient donc « ya », des deux cotes de la comparaison)."""
    merged = []
    for w in words:
        single = len(w) == 1 and "a" <= w <= "z"
        if single and merged and merged[-1][1]:
            merged[-1] = (merged[-1][0] + w, True)
        else:
            merged.append((w, single))
    return [w for w, _ in merged]


def _words_fr(text):
    """Minuscules (NFC), apostrophes droites et collees, elisions separees (d'un -> d, un) sauf « aujourd'hui », traits
    d'union = separateurs, « week-end » = « weekend », sigles reunis (P.O.V., P O V -> pov), nombres en chiffres
    (0 a 999 999, milliers separes par une espace ou un point compris) developpes en mots. Un mot = une suite de
    lettres, accentuees ou d'une autre ecriture.
    Refus connus (la phrase est refusee, il faut l'ecrire autrement) : « 1 » pour « une » (« 1 heure », « 21
    minutes »), les symboles et unites (km/h, %, €, n°), les decimales (« 9,5 »), les ordinaux (« 1er »), les heures
    (« 2h30 »), un nombre au-dela de 999 999 ou qui commence par zero (garde en chiffres)."""
    t = unicodedata.normalize("NFC", str(text)).lower()
    t = re.sub(r"\s*['’‘ʼ′]\s*", "'", t)
    t = re.sub(r"\bweek[ -]?end", "weekend", t)
    t = _FR_DOTTED.sub(lambda m: f" {m.group().replace('.', '')} ", t)
    t = _FR_GROUPS.sub(lambda m: re.sub(r"\D", "", m.group()), t)
    out = []
    for tok in _FR_TOKEN.findall(t):
        if tok.isascii() and tok.isdigit() and len(tok) <= 6 and (tok == "0" or tok[0] != "0"):
            out += number_fr(int(tok))
        else:
            out.append(tok)
    return _merge_spelled(out)


_FR_FOLD = str.maketrans("àâîôùûèê", "aaiouuéé")                    # le trema (maïs, Noël) reste : voyelle dite a part
_FR_FIXED = {"est": "é", "es": "é", "les": "lé", "des": "dé", "mes": "mé", "tes": "té", "ses": "sé", "ces": "sé",
             "c": "s", "clef": "clé", "clefs": "clé", "ok": "oké", "okay": "oké", "ca": "sa"}
# consonne finale PRONONCEE (jamais retiree), au singulier comme au pluriel : mots courants seulement. Les mots sont
# cherches avec leurs accents tels qu'ecrits : « mat » garde son t, « mât » le perd.
_FR_SOUNDED = frozenset((
    "fils bus sud net cet sept brut ouest mars ours os but six dix huit neuf cinq set start short raid mat stop top "
    "test donc avec sec chef sac lac parc truc choc bloc mec bol fil sel sol vol mal cap clip club pub web job gaz "
    "jazz quiz as sens vis bis virus bonus campus tennis atlas dot zut chut script concept direct correct contact "
    "impact strict").split())
# « -er » dit [èr] et non [é] (formes sans le s final : vers, divers, travers, univers)
_FR_ER_SOUNDED = frozenset(("mer fer ver ser cher hier fier tier amer hiver enfer super "
                            "diver enver rever traver univer").split())
# « -ent » dit [an] : noms, adjectifs et adverbes courants (les autres mots longs en -ent sont pris pour des verbes).
# Cherches avec leurs accents tels qu'ecrits : « précédent » (nom) est ici, « précèdent » (verbe) n'y est pas.
_FR_ENT_NASAL = frozenset((
    "souvent content argent parent talent accent agent présent absent récent urgent serpent torrent couvent différent "
    "excellent violent prudent évident accident incident continent innocent apparent transparent permanent président "
    "adolescent précédent résident sergent équivalent adhérent mécontent insolent patent moment vent dent cent lent "
    "client patient fréquent intelligent événement mouvement orient ingrédient récipient inconvénient conscient "
    "inconscient coefficient").split())


def _fr_ending(w, raw):
    """Fin de mot telle qu'on la dit : lettres finales muettes retirees, terminaisons de verbe ramenees a un son.
    `raw` est le meme mot avec ses accents tels qu'ecrits (c'est lui qu'on cherche dans les listes de mots)."""
    if raw in _FR_SOUNDED:
        return w
    if w[-1] == "s" and w[-2] != "s" or w[-1] == "x" and w[-2] in "ui":      # pluriel, verbes : roues, bas, deux, voix
        w, raw = w[:-1], raw[:-1]
        if raw in _FR_SOUNDED:                                            # shorts, tests, raids : la consonne reste
            return w
    if (w.endswith("ent") and len(w) > 4 and not w.endswith(("ment", "tient", "vient"))
            and raw not in _FR_ENT_NASAL):
        return w[:-3] + "e"                                               # ils roulent = il roule, ils rient = il rit
    if w.endswith(("ez", "et", "ed")) and (w[-1] != "d" or w.endswith("ied")):
        return w[:-2] + "é"                                               # roulez, et, billet, pied
    if w.endswith("er") and w not in _FR_ER_SOUNDED:
        return w[:-2] + "é"                                               # rouler, premier
    if w.endswith("gt"):
        return w[:-2]                                                     # vingt, doigt
    if len(w) > 2 and (w[-1] in "td" and w[-2] in "aeiouyénr" or w[-1] == "p" and w.endswith(("oup", "mp"))):
        return w[:-1]                                                     # bat, vent, grand, vert, coup, champ
    return w


def sound_fr(word):
    """Cle de SON d'un mot francais deja normalise : deux mots de meme cle sont traites comme le meme mot, parce que
    Whisper choisit seul l'orthographe d'un son (bat / bas / bât, et / est, a / à, ou / où, ces / ses, roule / roules /
    roulent, roulé / rouler / roulez / roulée, clé / clef, cœur / coeur, ça / ca, ok / okay, paie / paye).

    Regles d'orthographe simples, sans dictionnaire : lettres finales muettes (s, x, t, d, quelques p), terminaisons de
    verbe (-ent muet, y compris apres consonne + i : ils rient = il rit ; -er, -ez, -é, -ée, -ais, -ait, -aient = un
    seul son « é »), groupes de voyelles (au / eau = o, ai / ei / è / ê / -et = é, œu = eu), h muet, ph = f, sh = ch
    (short, cash), c doux et ç = s, consonnes doubles, e final muet.

    Limites, a connaitre :
      - sons differents CONFONDUS, par choix : é / è en fin de mot (roulé / roulait, été / était, les / lait) et les
        lettres finales muettes (œufs / œuf). Une consonne finale prononcee n'est gardee que pour les mots de la liste
        `_FR_SOUNDED` (but, six, dix, start, set, raid...) ; un mot en -ent n'est nasal que s'il est dans la liste
        `_FR_ENT_NASAL` ou finit par -ment, -tient, -vient (les autres sont pris pour des verbes : sans la liste,
        « content » vaudrait « conte »). Ajouter le mot a la liste concernee s'il pose probleme ;
      - homophones NON rapproches (l'essai est refuse a tort, un autre est genere, jamais une voix fautive gardee) :
        voyelles nasales (sans / cent / sang, tant / temps, pain / pin), « e » ouvert (mer / mère), consonnes dures
        (quand / camp), homophones en plusieurs mots (qu'elle / quelle), verbes en -ment (ils aiment ne rejoint pas
        il aime), verbes en -tient / -vient du premier groupe (ils envient), mots ajoutes aux listes et qui ont un
        homographe (tu as / un as, je vis / une vis, je sens / le sens, ils président / le président).
    Un mot sans lettre (nombre garde en chiffres) est sa propre cle."""
    raw = word.replace("œ", "oe").replace("æ", "ae").replace("'", "")
    w = raw.translate(_FR_FOLD)
    if not w.isalpha():
        return w
    if w in _FR_FIXED:
        return _FR_FIXED[w]
    if len(w) > 1:
        w = _fr_ending(w, raw)
    if w == "paye":                                                       # je paye = je paie (les deux s'ecrivent)
        w = "paie"
    w = re.sub(r"(?<=.)(?:ç|c(?=[eiyé]))", "ss", w)                        # c doux et ç = [s] ; un s seul entre
    w = re.sub(r"^(?:ç|c(?=[eiyé]))", "s", w)                              # voyelles reste a part (poison / poisson)
    w = re.sub(r"s{3,}", "ss", w)
    w = re.sub(r"(?<!c)h", "", w.replace("ph", "f").replace("sh", "ch"))   # sh = ch (short n'est pas sort) ; h muet
    w = re.sub(r"eau|au", "o", w.replace("oeu", "eu"))
    w = re.sub(r"(?:ai|ei)(?!l(?:l|$))", "é", w)                           # mais pas travail, soleil, paille
    w = re.sub(r"(?<=[aeou]i)ll|(?<!i)ll", "l", w)                         # elle, appelle, travaille ; pas fille
    w = re.sub(r"([bcdfgprt])\1", r"\1", w)                                # nn / mm gardes : bonne n'est pas bon
    if len(w) > 1 and w[-1] == "e" and (w[-2] in "aéiouy" or len(w) > 2 and w[-2] not in "nm"):
        w = w[:-1]                                                        # e final muet ; « une » n'est pas « un »
    return w


# ───────────────────────── arabe ─────────────────────────

# Les caracteres arabes sont donnes par leur point de code : des signes combinants colles dans le source seraient
# illisibles, et faciles a abimer. Retires : tashkeel (et signes voisins), alef suscrit, tatweel.
_AR_MARKS = re.compile("[{}-{}{}{}]".format(*map(chr, (0x064B, 0x065F, 0x0670, 0x0640))))
_AR_FOLD = {0x0623: 0x0627, 0x0625: 0x0627, 0x0622: 0x0627, 0x0671: 0x0627,       # alef a hamza, madda, wasla -> nu
            0x0649: 0x064A,                                                       # alef maqsura -> ya
            **{0x0660 + d: str(d) for d in range(10)},                            # chiffres arabes -> chiffres latins
            **{0x06F0 + d: str(d) for d in range(10)}}                            # chiffres persans aussi


def _words_ar(text):
    """Ligatures et formes de presentation ramenees aux lettres ordinaires (NFKC : U+FEFB -> lam, alef), sans tashkeel
    (U+064B a U+0652 et les signes voisins, U+0670) ni tatweel (U+0640), formes d'alef ramenees a l'alef nu, alef
    maqsura -> ya, chiffres arabes et persans -> chiffres latins. Un mot = une suite de lettres (arabes, latines en
    minuscules, ou d'une autre ecriture) ou de chiffres.
    Limites : ta marbuta / ha et les hamzas portees par waw ou ya ne sont pas unifiees, les nombres en chiffres ne
    sont pas developpes en mots."""
    t = _AR_MARKS.sub("", unicodedata.normalize("NFKC", str(text))).translate(_AR_FOLD).lower()
    return _WORD.findall(t)


# ───────────────────────── les trois langues ─────────────────────────

_WORDS = {"en": _words_en, "fr": _words_fr, "ar": _words_ar}


def words(text, lang):
    """Liste des mots comparables d'un texte dans la langue donnee."""
    return _WORDS[checked(lang)](text)


def key(word, lang):
    """Cle de comparaison d'un mot deja normalise : son en francais, le mot lui-meme en anglais et en arabe."""
    return sound_fr(word) if checked(lang) == "fr" else word


def same_word(a, b, lang):
    """Vrai si deux mots deja normalises comptent pour le meme mot : egaux, ou de meme son en francais."""
    return a == b or key(a, lang) == key(b, lang)
