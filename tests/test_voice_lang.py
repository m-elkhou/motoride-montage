"""Langue de la voix : mots comparables (anglais, francais, arabe), homophones francais, nombres, langue par defaut,
reference par langue, requete envoyee au serveur Whisper et choix du processeur (CPU ou carte graphique).

Les cas francais sont des transcriptions reelles de Whisper du 13/11 (espace avant l'apostrophe, « bat » entendu
« bas », phrase dite deux fois, mot en trop). Aucun modele, aucun reseau, jamais la vraie carte graphique.
"""
import io
import json
import os
import sys
import types

import pytest

import mm_lang
import mm_paths
import mm_voicecheck as vc

TAIT = "Et d'un coup, le monde se tait."
JUSTE = "Juste toi, deux roues, et une ligne d'asphalte qui t'appelle."
ROULE = "Alors roule. Tant que le cœur bat, roule."


# ───────────────────────── les huit transcriptions reelles ─────────────────────────

@pytest.mark.parametrize("expected,heard", [
    (TAIT, "Et d 'un coup, le monde se tait."),                                    # espace avant l'apostrophe
    (JUSTE, "Juste toi, deux roues et une ligne d 'asphalte qui t 'appelle."),
    (ROULE, "Alors roule, tant que le cœur bas roule."),                           # « bat » / « bas » : meme son
])
def test_french_takes_that_say_the_text_are_accepted(expected, heard):
    assert vc.word_problems(expected, heard, "fr") == []


@pytest.mark.parametrize("expected,heard,needle", [
    (TAIT, "Et d 'un coup, le monde se tait. Le monde se tait.", "repetition"),
    (JUSTE, "que ce soit de roues et une ligne d 'asphalte qui t 'appelle.", "entendu"),
    (ROULE, "Ou alors roule, tant que le cœur bat, roule.", "en trop"),
    (ROULE, "roule, donc le cœur bas roule", "manquant"),
    (ROULE, "en roule, tant que le cœur bas roule.", "entendu"),
])
def test_french_takes_that_say_something_else_are_refused(expected, heard, needle):
    problems = vc.word_problems(expected, heard, "fr")
    assert problems and any(needle in p for p in problems)


def test_a_french_homophone_is_not_reported_but_the_wrong_word_beside_it_is():
    assert vc.word_problems(ROULE, "Alors route, tant que le cœur bas roule.", "fr") == ["« roule » entendu « route »"]


# ───────────────────────── anglais : rien ne change ─────────────────────────

@pytest.mark.parametrize("text,words", [
    ("P.O.V., you left the city.", ["pov", "you", "left", "the", "city"]),
    ("P O V, you left the city.", ["pov", "you", "left", "the", "city"]),
    ("Rode first, everything else later.", ["road", "first", "everything", "else", "later"]),
    ("Take a road.", ["take", "a", "road"]),
    ("Don’t stop. OK?", ["don't", "stop", "okay"]),
])
def test_english_words_are_the_ones_of_before(text, words):
    assert mm_lang.words(text, "en") == words == vc.normalize_words(text)


def test_english_is_the_default_and_keeps_its_messages():
    assert vc.word_problems("Wait for the turn.", "Wait for the turn.") == []
    assert vc.word_problems("Wait for the turn.", "Wait on a turn.") == ["« for the » entendu « on a »"]
    assert vc.word_problems("Born to ride.", "Born to ride, to ride.") == ["repetition : « to ride »"]
    assert vc.word_problems("Which bike would you pick.", "Which bike would you") == ["mot(s) manquant(s) : « pick »"]
    for expected, heard in [("One more road.", "One more road. One."), ("This road hits hard.", "this road hits and")]:
        assert vc.word_problems(expected, heard) == vc.word_problems(expected, heard, "en")


def test_english_gets_no_french_tolerance():
    assert vc.word_problems("The bat flies.", "The bas flies.")                      # homophones francais seulement
    assert not mm_lang.same_word("bat", "bas", "en") and mm_lang.same_word("road", "road", "en")


def test_the_repetition_label_needs_whole_words_of_the_sentence():
    assert vc.word_problems("One more road.", "One more road. One.") == ["repetition : « one »"]
    assert vc.word_problems("Take the road.", "Take the road. Roa.") == ["mot(s) en trop : « roa »"]   # un bout de mot
    assert vc.word_problems("P.O.V., you left.", "POV, you left. P") == ["mot(s) en trop : « p »"]
    assert vc.word_problems("Born to ride.", "Born to ride, ride to.") == ["mot(s) en trop : « ride to »"]  # pas dans l'ordre


def test_a_replaced_block_is_reported_whole():
    assert vc.word_problems("Wait for the turn.", "Wait on a turn.") == ["« for the » entendu « on a »"]
    assert vc.word_problems(JUSTE, "que ce soit de roues et une ligne d 'asphalte qui t 'appelle.",
                            "fr") == ["« juste toi deux » entendu « que ce soit de »"]
    assert vc.word_problems("Un deux trois.", "Un quatre cinq six trois.", "fr") == ["« deux » entendu « quatre cinq six »"]


def test_english_words_ignore_other_scripts_as_before():
    assert vc.normalize_words("Wait. Спасибо 谢谢") == ["wait"] and vc.word_problems("Wait.", "Wait. Спасибо") == []
    assert vc.normalize_words("Café racer, 1 000 km") == ["caf", "racer", "1", "000", "km"]


# ───────────────────────── francais : mots, nombres, sons ─────────────────────────

@pytest.mark.parametrize("text,words", [
    ("Et d 'un coup", ["et", "d", "un", "coup"]),
    ("L’asphalte qui t’appelle", ["l", "asphalte", "qui", "t", "appelle"]),          # apostrophes courbes
    ("Aujourd'hui, c'est toi.", ["aujourd'hui", "c", "est", "toi"]),
    ("aujourd 'hui", ["aujourd'hui"]),
    ("Peut-être, vas-y !", ["peut", "être", "vas", "y"]),
    ("LÀ-BAS, L'ÉTÉ, LE CŒUR", ["là", "bas", "l", "été", "le", "cœur"]),
    ("e\u0301te\u0301", ["été"]),                                                   # accents decomposes (NFC)
])
def test_french_words_keep_their_accents_and_split_elisions(text, words):
    assert mm_lang.words(text, "fr") == words


@pytest.mark.parametrize("n,words", [
    (0, "zéro"), (1, "un"), (7, "sept"), (10, "dix"), (16, "seize"), (17, "dix sept"), (20, "vingt"),
    (21, "vingt et un"), (22, "vingt deux"), (70, "soixante dix"), (71, "soixante et onze"), (77, "soixante dix sept"),
    (80, "quatre vingts"), (81, "quatre vingt un"), (90, "quatre vingt dix"), (91, "quatre vingt onze"),
    (99, "quatre vingt dix neuf"), (100, "cent"), (101, "cent un"), (150, "cent cinquante"), (200, "deux cents"),
    (201, "deux cent un"), (280, "deux cent quatre vingts"), (1000, "mille"), (1001, "mille un"), (2000, "deux mille"),
    (1980, "mille neuf cent quatre vingts"), (9999, "neuf mille neuf cent quatre vingt dix neuf"),
    (10000, "dix mille"), (12000, "douze mille"), (21000, "vingt et un mille"), (80000, "quatre vingt mille"),
    (100000, "cent mille"), (200000, "deux cent mille"), (280500, "deux cent quatre vingt mille cinq cents"),
    (999999, "neuf cent quatre vingt dix neuf mille neuf cent quatre vingt dix neuf"),
])
def test_digits_are_expanded_to_french_number_words(n, words):
    assert mm_lang.words(f"{n}", "fr") == words.split()


def test_a_text_in_words_matches_a_transcript_in_digits():
    assert vc.word_problems("Cent cinquante chevaux et vingt et un virages.", "150 chevaux et 21 virages.", "fr") == []
    assert vc.word_problems("Quatre-vingt kilomètres, mille raisons.", "80 kilomètres, 1000 raisons.", "fr") == []
    assert vc.word_problems("Cent cinquante chevaux.", "160 chevaux.", "fr")          # un autre nombre est refuse
    assert mm_lang.words("12000 tours", "fr") == ["douze", "mille", "tours"]
    assert mm_lang.words("1000000 tours", "fr") == ["1000000", "tours"]              # au-dela de 999 999 : chiffres gardes


NBSP, NNBSP = chr(0x00A0), chr(0x202F)          # espace insecable, espace fine insecable


@pytest.mark.parametrize("expected,heard", [
    ("Mille kilomètres.", "1 000 kilomètres."),
    ("Mille kilomètres.", f"1{NBSP}000 kilomètres."),
    ("Mille kilomètres.", f"1{NNBSP}000 kilomètres."),
    ("Mille kilomètres.", "1.000 kilomètres."),
    ("Dix mille kilomètres.", "10 000 kilomètres."),
    ("Cent cinquante mille tours.", "150 000 tours."),
])
def test_a_thousands_separator_does_not_split_a_number(expected, heard):
    assert vc.word_problems(expected, heard, "fr") == []


def test_only_groups_of_three_digits_are_joined():
    assert mm_lang.words("3, 2, 1", "fr") == ["trois", "deux", "un"]
    assert mm_lang.words("en 2026 150 chevaux", "fr") == ["en", "deux", "mille", "vingt", "six", "cent", "cinquante",
                                                         "chevaux"]
    assert mm_lang.words("9.5 et 12 34", "fr") == ["neuf", "cinq", "et", "douze", "trente", "quatre"]
    assert mm_lang.words("1 000 000", "fr") == ["1000000"]


def test_a_number_with_a_leading_zero_is_kept_as_digits():
    assert mm_lang.words("007", "fr") == ["007"] and mm_lang.words("05 mai", "fr") == ["05", "mai"]
    assert mm_lang.words("0", "fr") == ["zéro"]
    assert vc.word_problems("Sept virages.", "007 virages.", "fr")                    # « 007 » n'est pas « sept »


@pytest.mark.parametrize("expected,heard", [
    ("Un week-end à moto.", "Un weekend à moto."),
    ("Un weekend à moto.", "Un week end à moto."),
    ("OK, on y va.", "Okay, on y va."),
    ("Ça roule.", "Ca roule."),
    ("Je paie.", "Je paye."),
    ("Ils paient.", "Ils payent."),
    ("POV : tu roules.", "P.O.V. tu roules."),
    ("POV : tu roules.", "P O V, tu roules."),
    ("POV : à moto.", "P.O.V. à moto."),
    ("Le GPS.", "Le G.P.S."),
    ("Ils oublient tout.", "Il oublie tout."),
])
def test_cheap_french_spelling_variants_are_the_same_words(expected, heard):
    assert vc.word_problems(expected, heard, "fr") == []


def test_french_sigles_are_merged_as_in_english():
    assert mm_lang.words("P.O.V. tu roules", "fr") == ["pov", "tu", "roules"] == mm_lang.words("POV : tu roules", "fr")
    assert mm_lang.words("Le G.P.S. a dit", "fr") == ["le", "gps", "a", "dit"]         # le mot d'apres n'est pas colle
    assert mm_lang.words("G P S", "fr") == ["gps"] == mm_lang.words("g. p. s.", "fr")
    assert mm_lang.words("P O V à moto", "fr") == ["pov", "à", "moto"]                # « à » n'est pas une lettre de sigle
    assert mm_lang.words("Y'a pas, il y a", "fr") == ["ya", "pas", "il", "ya"]        # comme en anglais : lettres collees


@pytest.mark.parametrize("expected,heard", [
    ("Une heure de route.", "1 heure de route."),               # « 1 » pour « une »
    ("Vingt et une minutes.", "21 minutes."),
    ("Sans limite.", "100 limites."),                           # voyelles nasales : sans / cent
    ("Ils aiment la route.", "Il aime la route."),              # verbe en -ment
    ("Cent pour cent.", "100 %."),                              # symboles
])
def test_known_french_refusals_stay_refusals(expected, heard):
    assert vc.word_problems(expected, heard, "fr")


@pytest.mark.parametrize("group", [
    ("bat", "bas", "bât"), ("et", "est"), ("a", "à"), ("ou", "où"), ("ces", "ses"), ("roule", "roules", "roulent"),
    ("roulé", "rouler", "roulez", "roulée"), ("clé", "clef"), ("cœur", "coeur"),
])
def test_french_homophones_are_the_same_word(group):
    for a in group:
        for b in group:
            assert mm_lang.same_word(a, b, "fr"), (a, b)


@pytest.mark.parametrize("a,b", [
    ("route", "roule"), ("moteur", "monteur"), ("vitesse", "tristesse"), ("vent", "vie"),
    ("un", "une"), ("de", "deux"), ("le", "les"), ("comme", "comment"), ("poison", "poisson"), ("tout", "tu"),
    ("bon", "bonne"), ("content", "conte"), ("mais", "maïs"), ("fille", "file"), ("alors", "en"),
    # sons differents que la cle confondait (revue du 13/11)
    ("but", "bu"), ("six", "si"), ("dix", "dit"), ("short", "sort"), ("start", "star"), ("set", "sait"),
    ("raid", "ré"), ("mat", "ma"), ("rient", "rien"), ("lient", "lien"), ("précédent", "précède"),
    ("résident", "réside"), ("sergent", "serge"), ("équivalent", "équivale"), ("adhérent", "adhère"),
    ("mécontent", "méconte"), ("insolent", "insole"), ("patent", "patte"), ("cash", "cas"), ("show", "sow"),
])
def test_french_words_that_sound_different_stay_different(a, b):
    assert not mm_lang.same_word(a, b, "fr")
    assert mm_lang.sound_fr(a) != mm_lang.sound_fr(b)


def test_sh_is_the_ch_sound_and_not_a_mute_h():
    assert vc.word_problems("Ce short est court.", "Ce sort est court.", "fr") == ["« short » entendu « sort »"]
    assert mm_lang.same_word("cash", "cache", "fr") and mm_lang.sound_fr("show") != mm_lang.sound_fr("so")


def test_a_verb_in_ient_has_a_silent_ending_and_is_not_the_word_in_ien():
    assert vc.word_problems("Ils rient.", "Il rien.", "fr") == ["« rient » entendu « rien »"]
    assert vc.word_problems("Ils lient.", "Il lien.", "fr") == ["« lient » entendu « lien »"]
    for plural, singular in [("rient", "rit"), ("lient", "lie"), ("crient", "crie"), ("prient", "prie"),
                             ("oublient", "oublie"), ("étudient", "étudie")]:
        assert mm_lang.same_word(plural, singular, "fr"), plural


@pytest.mark.parametrize("verb", ["tient", "vient", "revient", "devient", "contient", "appartient"])
def test_tient_and_vient_keep_their_nasal_sound(verb):
    assert mm_lang.sound_fr(verb).endswith("ien")
    assert not mm_lang.same_word(verb, verb[:-3] + "e", "fr")                       # « vient » n'est pas « vie »
    assert mm_lang.same_word(verb, verb[:-1] + "s", "fr")                           # je viens, il vient : meme son


@pytest.mark.parametrize("expected,heard,problem", [
    ("Top départ, start.", "Top départ, star.", "« start » entendu « star »"),
    ("C'est un but.", "C'est un bu.", "« but » entendu « bu »"),
    ("Le set.", "Le sait.", "« set » entendu « sait »"),
    ("Un raid à moto.", "Un ré à moto.", "« raid » entendu « ré »"),
    ("Six virages.", "Si virages.", "« six » entendu « si »"),
    ("Le virage précédent.", "Le virage précède.", "« précédent » entendu « précède »"),
    ("Un résident.", "Un réside.", "« résident » entendu « réside »"),
])
def test_a_pronounced_final_consonant_or_a_nasal_ending_is_not_dropped(expected, heard, problem):
    assert vc.word_problems(expected, heard, "fr") == [problem]


def test_e_acute_and_e_grave_endings_stay_merged_on_purpose():
    assert vc.word_problems("Il roulait vite.", "Il roulé vite.", "fr") == []
    for a, b in [("été", "était"), ("rouler", "roulaient"), ("aller", "allait"), ("thé", "tes")]:
        assert mm_lang.same_word(a, b, "fr"), (a, b)


PRONOUNCED = ("but six dix sept huit neuf cinq set start short raid mat stop top test ouest donc avec sec chef sac "
              "lac parc truc choc bloc mec bol fil sel sol vol mal cap clip club pub web job gaz jazz quiz as os mars "
              "ours sens vis bis virus bonus campus tennis atlas brut dot zut chut script concept direct correct "
              "contact impact strict fils bus sud net cet").split()


@pytest.mark.parametrize("word", PRONOUNCED)
def test_the_final_consonant_of_these_words_is_kept(word):
    assert mm_lang.sound_fr(word)[-1] == word[-1]
    assert not mm_lang.same_word(word, word[:-1], "fr")


def test_the_plural_of_a_word_with_a_pronounced_final_keeps_it_too():
    for plural, singular, other in [("shorts", "short", "sorts"), ("raids", "raid", "rés"), ("buts", "but", "bus"),
                                    ("tests", "test", "tes"), ("starts", "start", "stars")]:
        assert mm_lang.same_word(plural, singular, "fr") and not mm_lang.same_word(plural, other, "fr"), plural
    assert mm_lang.same_word("mât", "ma", "fr") and mm_lang.same_word("bat", "bas", "fr")   # t muet : pas dans la liste


@pytest.mark.parametrize("word", "mer fer ver cher hier fier amer hiver enfer super vers divers travers univers".split())
def test_er_is_not_the_e_acute_sound_in_these_words(word):
    assert not mm_lang.same_word(word, word.rstrip("s")[:-2] + "é", "fr")


def test_er_words_keep_their_real_homophones():
    assert mm_lang.same_word("vers", "vert", "fr") and mm_lang.same_word("ver", "verre", "fr")
    assert mm_lang.same_word("rouler", "roulé", "fr") and mm_lang.same_word("premier", "premiers", "fr")
    for a, b in [("mer", "mes"), ("fer", "fée"), ("cher", "chez")]:
        assert not mm_lang.same_word(a, b, "fr"), (a, b)


NASAL = ("précédent résident sergent équivalent adhérent mécontent insolent patent moment vent dent cent lent argent "
         "agent accent accident client patient président talent urgent récent différent évident excellent violent "
         "prudent absent présent innocent fréquent apparent permanent intelligent événement mouvement souvent content "
         "parent serpent torrent couvent incident continent transparent adolescent").split()


@pytest.mark.parametrize("word", NASAL)
def test_these_words_in_ent_keep_their_nasal_sound(word):
    assert mm_lang.sound_fr(word).endswith("en")
    assert not mm_lang.same_word(word, word[:-3] + "e", "fr")                       # « président » n'est pas « préside »
    assert mm_lang.same_word(word, word + "s", "fr")                                # le pluriel se dit pareil


def test_a_verb_in_ent_still_joins_its_singular():
    for plural, singular in [("roulent", "roule"), ("passent", "passe"), ("tournent", "tourne"), ("voient", "voit"),
                             ("précèdent", "précède"), ("diffèrent", "diffère")]:
        assert mm_lang.same_word(plural, singular, "fr"), plural
    assert not mm_lang.same_word("précèdent", "précédent", "fr")                     # le verbe et le nom : l'accent ecrit


@pytest.mark.parametrize("rule,same,different", [
    ("h muet", ("hors", "or"), ("chou", "cou")),
    ("sh = ch", ("cash", "cache"), ("short", "sort")),
    ("ph = f", ("phare", "fard"), ("phare", "pare")),
    ("consonnes doubles", ("datte", "date"), ("poisson", "poison")),
    ("c doux en tete", ("cent", "sent"), ("coup", "sou")),
    ("c doux dans le mot", ("face", "fasse"), ("lac", "lasse")),
    ("ll = l", ("belle", "bel"), ("fille", "fil")),
    ("ai = é", ("mais", "mes"), ("bail", "bêle")),
    ("ei = é", ("reine", "rêne"), ("soleil", "sole")),
    ("eau, au = o", ("mot", "maux"), ("peau", "peu")),
    ("œu = eu", ("vœu", "veut"), ("vœu", "vu")),
    ("e final muet", ("roue", "roux"), ("porte", "port")),
])
def test_each_sound_rule_joins_the_same_sound_and_nothing_else(rule, same, different):
    assert mm_lang.sound_fr(same[0]) == mm_lang.sound_fr(same[1]), rule
    assert mm_lang.sound_fr(different[0]) != mm_lang.sound_fr(different[1]), rule


def test_rare_apostrophes_are_apostrophes():
    assert mm_lang.words("aujourd‘hui lʼété c′est", "fr") == ["aujourd'hui", "l", "été", "c", "est"]
    assert vc.word_problems("L'été, c'est aujourd'hui.", "Lʼété, c′est aujourd‘hui.", "fr") == []


# ───────────────────────── une autre ecriture n'est jamais invisible ─────────────────────────

@pytest.mark.parametrize("tail,words", [("شكرا للمشاهدة", "شكرا للمشاهدة"), ("Спасибо.", "спасибо"), ("谢谢", "谢谢")])
def test_a_tail_in_another_script_is_reported_in_french(tail, words):
    assert vc.word_problems(TAIT, f"{TAIT} {tail}", "fr") == [f"mot(s) en trop : « {words} »"]


def test_a_tail_in_another_script_is_reported_in_arabic():
    assert vc.word_problems("الطريق أمامك.", "الطريق امامك Спасибо", "ar") == ["mot(s) en trop : « спасибо »"]
    assert vc.word_problems("الطريق أمامك.", "الطريق امامك 谢谢", "ar") == ["mot(s) en trop : « 谢谢 »"]
    assert vc.word_problems("الطريق أمامك.", "الطريق امامك Thanks", "ar") == ["mot(s) en trop : « thanks »"]


def test_any_run_of_letters_or_digits_is_a_word_in_french_and_arabic():
    assert mm_lang.words("señor Łódź straße", "fr") == ["señor", "łódź", "straße"]
    assert mm_lang.words("Привет 你好 123", "ar") == ["привет", "你好", "123"]


# ───────────────────────── arabe ─────────────────────────

@pytest.mark.parametrize("text,words", [
    ("مَرْحَبًا بِكُمْ", ["مرحبا", "بكم"]),                                                # tashkeel retire
    ("مـــرحبا", ["مرحبا"]),                                                          # tatweel retire
    ("أَحْمَد إِلَى آخِر ٱلطريق", ["احمد", "الي", "اخر", "الطريق"]),                          # alef unifie, alef maqsura -> ya
    ("٣ دراجات و ١٢٠ كيلومتر", ["3", "دراجات", "و", "120", "كيلومتر"]),                  # chiffres arabes -> latins
    ("الطريق، أمامك!", ["الطريق", "امامك"]),                                           # ponctuation arabe ignoree
])
def test_arabic_words_are_normalised(text, words):
    assert mm_lang.words(text, "ar") == words


def test_arabic_takes_are_compared_without_the_vowel_marks():
    assert vc.word_problems("الطَّرِيقُ أَمَامَكَ.", "الطريق امامك", "ar") == []
    assert any("repetition" in p for p in vc.word_problems("الطريق أمامك.", "الطريق امامك امامك", "ar"))
    assert any("entendu" in p for p in vc.word_problems("الطريق أمامك.", "الطريق خلفك", "ar"))
    assert mm_lang.same_word("الطريق", "الطريق", "ar") and not mm_lang.same_word("امامك", "خلفك", "ar")


LAM_ALEF = chr(0xFEFB)          # ligature « lam-alef » (forme de presentation) : deux lettres ordinaires apres NFKC


def test_an_arabic_presentation_ligature_is_two_ordinary_letters():
    assert mm_lang.words(LAM_ALEF + " تتوقف", "ar") == ["لا", "تتوقف"]
    assert vc.word_problems(LAM_ALEF + " تتوقف", "تتوقف", "ar") == ["mot(s) manquant(s) : « لا »"]
    assert vc.word_problems(LAM_ALEF + " تتوقف", "لا تتوقف", "ar") == []


def test_persian_digits_are_read_like_arabic_and_latin_ones():
    assert mm_lang.words("۳ دراجات و ۱۲۰", "ar") == ["3", "دراجات", "و", "120"] == mm_lang.words("٣ دراجات و ١٢٠", "ar")


# ───────────────────────── langue par defaut, reference par langue ─────────────────────────

def test_default_language_is_the_environment_then_local_paths_then_english(monkeypatch):
    monkeypatch.delenv("MM_VOICE_LANG", raising=False)
    monkeypatch.setattr(mm_paths, "_L", {})
    assert mm_lang.default_lang() == "en"
    monkeypatch.setattr(mm_paths, "_L", {"voice_lang": "ar"})
    assert mm_lang.default_lang() == "ar"
    monkeypatch.setenv("MM_VOICE_LANG", "fr")
    assert mm_lang.default_lang() == "fr"
    assert mm_lang.LANGS == ("en", "fr", "ar")


def test_an_unknown_language_names_the_allowed_values(monkeypatch):
    monkeypatch.setenv("MM_VOICE_LANG", "de")
    with pytest.raises(ValueError, match="en.*fr.*ar"):
        mm_lang.default_lang()
    with pytest.raises(ValueError, match="en.*fr.*ar"):
        mm_lang.words("Hallo", "de")


def test_the_default_language_setting_is_trimmed_and_lower_cased(monkeypatch):
    monkeypatch.setenv("MM_VOICE_LANG", "  FR ")
    assert mm_lang.default_lang() == "fr"
    monkeypatch.delenv("MM_VOICE_LANG")
    monkeypatch.setattr(mm_paths, "_L", {"voice_lang": "Ar\n"})
    assert mm_lang.default_lang() == "ar"


def test_the_voice_reference_is_looked_up_per_language(monkeypatch, tmp_path):
    for name in ("MM_VOICE_REF", "MM_VOICE_REF_EN", "MM_VOICE_REF_FR", "MM_VOICE_REF_AR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mm_paths, "_L", {})
    assert mm_paths.voice_ref("en") == mm_paths.VOICE_REF                             # anglais : celle d'avant
    monkeypatch.setattr(mm_paths, "_L", {"voice_ref_fr": str(tmp_path / "local_fr.wav")})
    assert mm_paths.voice_ref("fr") == tmp_path / "local_fr.wav"
    monkeypatch.setenv("MM_VOICE_REF_FR", str(tmp_path / "env_fr.wav"))
    assert mm_paths.voice_ref("fr") == tmp_path / "env_fr.wav"                        # l'environnement l'emporte
    assert mm_paths.voice_ref("FR") == tmp_path / "env_fr.wav"
    assert mm_paths.voice_ref("en") == mm_paths.VOICE_REF


def test_another_language_never_gets_the_default_english_recording(monkeypatch, tmp_path):
    for name in ("MM_VOICE_REF", "MM_VOICE_REF_EN", "MM_VOICE_REF_FR", "MM_VOICE_REF_AR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mm_paths, "_L", {})
    assert mm_paths.voice_ref("fr") is None and mm_paths.voice_ref("ar") is None      # rien de regle : pas de reference
    monkeypatch.setattr(mm_paths, "_L", {"voice_ref": str(tmp_path / "common.wav")})
    assert mm_paths.voice_ref("fr") == tmp_path / "common.wav"                        # reference commune CHOISIE
    monkeypatch.setenv("MM_VOICE_REF", str(tmp_path / "env_common.wav"))
    assert mm_paths.voice_ref("ar") == tmp_path / "env_common.wav" == mm_paths.voice_ref("en")
    monkeypatch.setenv("MM_VOICE_REF_AR", str(tmp_path / "ar.wav"))
    assert mm_paths.voice_ref("ar") == tmp_path / "ar.wav"                            # celle de la langue d'abord


# ───────────────────────── client et serveur Whisper ─────────────────────────

class FakePipe:
    def __init__(self, replies=()):
        self.sent, self.replies = [], list(replies)

    def write(self, text):
        self.sent.append(text)

    def flush(self):
        pass

    def readline(self):
        return self.replies.pop(0) if self.replies else ""

    def close(self):
        pass


class FakeProc:
    """Faux serveur : repond les lignes prevues, garde ce que le client lui ecrit."""

    def __init__(self, replies):
        self.stdin, self.stdout = FakePipe(), FakePipe(replies)

    def poll(self):
        return 0


def test_the_request_line_carries_the_language():
    asr = vc.ASR(python="python", model="large-v3")
    reply = json.dumps({"words": [[0.0, 0.2, "Et", 0.9], [0.2, 0.5, "roule.", 0.8]]}) + "\n"
    asr.proc = FakeProc([reply, reply, reply])
    assert asr.words("a.wav", lang="fr") == [(0.0, 0.2, "Et", 0.9), (0.2, 0.5, "roule.", 0.8)]
    assert asr.text("b.mp4", clip_end=3.5, lang="ar") == "Et roule."
    asr.words("c.wav")                                                               # ancien appel : pas de langue
    sent = [json.loads(line) for line in asr.proc.stdin.sent]
    assert sent == [{"path": "a.wav", "end": None, "lang": "fr"}, {"path": "b.mp4", "end": 3.5, "lang": "ar"},
                    {"path": "c.wav", "end": None, "lang": None}]


@pytest.mark.parametrize("ready,device", [("READY cuda\n", "cuda"), ("READY cpu\n", "cpu"), ("READY\n", None)])
def test_the_client_accepts_a_ready_line_with_or_without_the_device(monkeypatch, ready, device):
    monkeypatch.setattr(vc.subprocess, "Popen", lambda *a, **k: FakeProc([ready]))
    with vc.ASR(python="python", model="large-v3") as asr:
        assert asr.model == "large-v3" and asr.device == device


def test_the_client_still_refuses_a_server_that_is_not_ready(monkeypatch):
    monkeypatch.setattr(vc.subprocess, "Popen", lambda *a, **k: FakeProc(["ERREUR MemoryError: trop gros\n"]))
    with pytest.raises(RuntimeError, match="ASR indisponible.*large-v3: ERREUR MemoryError: trop gros"):
        vc.ASR(python="python", model="large-v3").__enter__()


def test_a_server_that_dies_at_load_without_a_word_is_reported_as_such(monkeypatch):
    monkeypatch.setattr(vc.subprocess, "Popen", lambda *a, **k: FakeProc([]))        # fin de fichier : aucune ligne
    with pytest.raises(RuntimeError) as err:
        vc.ASR(python="python", model="large-v3").__enter__()
    msg = str(err.value)
    assert "ASR indisponible (python)" in msg and msg.count("arrete sans message") == 2   # large-v3 puis medium
    assert "MM_ASR_DEVICE=cpu" in msg


def fake_servers(monkeypatch, *scripts):
    """Faux Popen : un faux serveur par lancement, dans l'ordre ; garde les serveurs lances et leur environnement."""
    procs, envs, todo = [], [], list(scripts)

    def popen(cmd, **kw):
        procs.append(FakeProc(todo.pop(0)))
        envs.append(kw.get("env"))
        return procs[-1]

    monkeypatch.setattr(vc.subprocess, "Popen", popen)
    return procs, envs


REPLY = json.dumps({"words": [[0.0, 0.2, "Et", 0.9], [0.2, 0.5, "roule.", 0.8]]}) + "\n"


def test_a_server_that_dies_after_ready_is_restarted_once_on_the_cpu(monkeypatch, capsys):
    monkeypatch.setenv("MM_ASR_DEVICE", "auto")
    procs, envs = fake_servers(monkeypatch, ["READY cuda\n"], ["READY cpu\n", REPLY, REPLY])
    with vc.ASR(python="python", model="large-v3") as asr:
        assert asr.device == "cuda"
        assert asr.words("a.wav", lang="fr") == [(0.0, 0.2, "Et", 0.9), (0.2, 0.5, "roule.", 0.8)]   # pas d'erreur JSON
        assert asr.device == "cpu" and asr.model == "large-v3" and len(procs) == 2
        assert envs[0] is None and envs[1]["MM_ASR_DEVICE"] == "cpu"                  # 2e lancement : CPU impose
        assert procs[1].stdin.sent == procs[0].stdin.sent                             # la MEME requete est redite
        assert json.loads(procs[1].stdin.sent[0]) == {"path": "a.wav", "end": None, "lang": "fr"}
        assert asr.text("b.wav") == "Et roule." and len(procs) == 2
    assert "cpu" in capsys.readouterr().err.lower()                                   # la relance est annoncee


def test_a_server_that_dies_twice_names_the_two_settings(monkeypatch, capsys):
    procs, _ = fake_servers(monkeypatch, ["READY cuda\n"], ["READY cpu\n"])
    asr = vc.ASR(python="python", model="large-v3").__enter__()
    with pytest.raises(RuntimeError, match="MM_ASR_DEVICE=cpu.*MM_ASR_PYTHON"):
        asr.words("a.wav")
    assert len(procs) == 2                                                            # une seule relance
    with pytest.raises(RuntimeError, match="MM_ASR_DEVICE=cpu.*MM_ASR_PYTHON"):
        asr.words("a.wav")                                                            # ni JSONDecodeError, ni 3e lancement
    assert len(procs) == 2
    capsys.readouterr()


def test_a_second_death_after_a_good_restart_is_not_restarted_again(monkeypatch, capsys):
    procs, _ = fake_servers(monkeypatch, ["READY cuda\n"], ["READY cpu\n", REPLY])
    asr = vc.ASR(python="python", model="large-v3").__enter__()
    assert len(asr.words("a.wav")) == 2
    with pytest.raises(RuntimeError, match="MM_ASR_DEVICE=cpu.*MM_ASR_PYTHON"):
        asr.words("b.wav")
    assert len(procs) == 2
    capsys.readouterr()


def test_a_restart_that_does_not_come_up_gives_its_reason(monkeypatch, capsys):
    fake_servers(monkeypatch, ["READY cuda\n"], ["ERREUR MemoryError: trop gros\n"])
    asr = vc.ASR(python="python", model="large-v3").__enter__()
    with pytest.raises(RuntimeError, match="MemoryError: trop gros.*MM_ASR_DEVICE=cpu.*MM_ASR_PYTHON"):
        asr.words("a.wav")
    capsys.readouterr()


def test_a_broken_pipe_counts_as_a_dead_server(monkeypatch, capsys):
    procs, _ = fake_servers(monkeypatch, ["READY cuda\n"], ["READY cpu\n", REPLY])
    asr = vc.ASR(python="python", model="large-v3").__enter__()

    def broken(text):
        raise BrokenPipeError(32, "Broken pipe")

    procs[0].stdin.write = broken
    assert asr.text("a.wav") == "Et roule." and asr.device == "cpu" and len(procs) == 2
    capsys.readouterr()


def fake_whisper(monkeypatch, fail_cuda=False):
    """Faux faster_whisper : note chaque chargement et la langue de chaque transcription."""
    loads, langs = [], []

    class WhisperModel:
        def __init__(self, name, device, compute_type):
            loads.append((name, device, compute_type))
            if device == "cuda" and fail_cuda:
                raise RuntimeError("CUDA failed with error out of memory")

        def transcribe(self, path, language=None, **kw):
            langs.append(language)
            return [], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=WhisperModel))
    return loads, langs


def fake_torch(monkeypatch, tmp_path, with_dll, dlls=("cublas64_12.dll", "cudnn_ops64_9.dll")):
    """Faux dossier torch (jamais le vrai) : torch/lib, avec ou sans les bibliotheques (cuBLAS 12 et cuDNN 9) que
    CTranslate2 exige."""
    lib = tmp_path / "torch" / "lib"
    lib.mkdir(parents=True)
    for name in dlls if with_dll else ():
        (lib / name).write_bytes(b"")
    spec = types.SimpleNamespace(submodule_search_locations=[str(tmp_path / "torch")],
                                 origin=str(tmp_path / "torch" / "__init__.py"))
    monkeypatch.setattr(vc, "find_spec", lambda name: spec if name == "torch" else None)
    added = []
    monkeypatch.setattr(os, "add_dll_directory", added.append, raising=False)
    monkeypatch.setenv("PATH", "old_path")
    return lib, added


def test_the_server_transcribes_in_the_requested_language_and_in_english_by_default(monkeypatch, capsys):
    loads, langs = fake_whisper(monkeypatch)
    monkeypatch.setenv("MM_ASR_DEVICE", "cpu")
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"path": "a.wav", "end": null, "lang": "fr"}\n'
                                                  '{"path": "b.wav", "end": 2.5}\n'
                                                  '{"path": "c.wav", "end": null, "lang": null}\n'))
    assert vc._serve("large-v3") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "READY cpu" and [json.loads(line) for line in out[1:]] == [{"words": []}] * 3
    assert langs == ["fr", "en", "en"] and loads == [("large-v3", "cpu", "int8")]


@pytest.mark.parametrize("wanted", ["cuda", "auto"])
def test_cuda_is_refused_when_the_cublas_dll_is_absent(monkeypatch, tmp_path, wanted):
    loads, _ = fake_whisper(monkeypatch)
    _, added = fake_torch(monkeypatch, tmp_path, with_dll=False)
    monkeypatch.setenv("MM_ASR_DEVICE", wanted)
    assert vc.cuda_dll_dir() is None and vc.asr_device() == ("cpu", "int8", None)
    _, device = vc.load_whisper("large-v3")
    assert device == "cpu" and loads == [("large-v3", "cpu", "int8")]                 # cuda jamais tente
    assert added == [] and os.environ["PATH"] == "old_path"


@pytest.mark.parametrize("dlls", [
    ("cublas64_12.dll",),                                  # cuDNN absent : la carte tomberait a la 1re transcription
    ("cudnn_ops64_9.dll", "cudnn64_9.dll"),                # cuBLAS absent
    ("cublas64_12.dll", "cudnn_ops64_8.dll"),              # cuDNN 8 : pas la version que CTranslate2 charge
    ("cublas64_12.dll", "cudnn64_9.dll.txt"),
])
def test_cuda_needs_both_cublas_12_and_cudnn_9(monkeypatch, tmp_path, dlls):
    loads, _ = fake_whisper(monkeypatch)
    _, added = fake_torch(monkeypatch, tmp_path, with_dll=True, dlls=dlls)
    monkeypatch.setenv("MM_ASR_DEVICE", "cuda")
    assert vc.cuda_dll_dir() is None and vc.asr_device() == ("cpu", "int8", None)
    assert vc.load_whisper("large-v3")[1] == "cpu" and loads == [("large-v3", "cpu", "int8")] and added == []


@pytest.mark.parametrize("cudnn", ["cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_engines_precompiled64_9.dll"])
def test_any_cudnn_9_library_counts(monkeypatch, tmp_path, cudnn):
    lib, _ = fake_torch(monkeypatch, tmp_path, with_dll=True, dlls=("cublas64_12.dll", cudnn))
    assert vc.cuda_dll_dir() == lib


def test_cuda_is_refused_when_torch_is_not_installed(monkeypatch):
    loads, _ = fake_whisper(monkeypatch)
    monkeypatch.setattr(vc, "find_spec", lambda name: None)
    monkeypatch.setenv("MM_ASR_DEVICE", "cuda")
    assert vc.load_whisper("large-v3")[1] == "cpu" and loads == [("large-v3", "cpu", "int8")]


@pytest.mark.parametrize("wanted", ["cuda", "auto", None])
def test_cuda_is_used_when_torch_brings_the_cublas_dll(monkeypatch, tmp_path, wanted):
    loads, _ = fake_whisper(monkeypatch)
    lib, added = fake_torch(monkeypatch, tmp_path, with_dll=True)
    if wanted:
        monkeypatch.setenv("MM_ASR_DEVICE", wanted)
    else:
        monkeypatch.delenv("MM_ASR_DEVICE", raising=False)                            # defaut : auto
    assert vc.cuda_dll_dir() == lib and vc.asr_device() == ("cuda", "float16", lib)
    _, device = vc.load_whisper("large-v3")
    assert device == "cuda" and loads == [("large-v3", "cuda", "float16")]
    assert added == [str(lib)] and os.environ["PATH"].split(os.pathsep) == [str(lib), "old_path"]


def test_cpu_can_be_forced_even_with_the_dll(monkeypatch, tmp_path):
    loads, _ = fake_whisper(monkeypatch)
    _, added = fake_torch(monkeypatch, tmp_path, with_dll=True)
    monkeypatch.setenv("MM_ASR_DEVICE", "cpu")
    assert vc.load_whisper("medium")[1] == "cpu" and loads == [("medium", "cpu", "int8")] and added == []


def test_a_failed_cuda_load_falls_back_to_cpu(monkeypatch, tmp_path, capsys):
    loads, _ = fake_whisper(monkeypatch, fail_cuda=True)
    fake_torch(monkeypatch, tmp_path, with_dll=True)
    monkeypatch.setenv("MM_ASR_DEVICE", "auto")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert vc._serve("large-v3") == 0
    assert loads == [("large-v3", "cuda", "float16"), ("large-v3", "cpu", "int8")]
    assert capsys.readouterr().out.splitlines() == ["READY cpu"]


def test_an_unknown_device_names_the_allowed_values(monkeypatch):
    monkeypatch.setenv("MM_ASR_DEVICE", "gpu")
    with pytest.raises(ValueError, match="cpu.*cuda.*auto"):
        vc.asr_device()


def test_the_server_interpreter_is_the_setting_then_this_python_then_social2shorts(monkeypatch):
    monkeypatch.setenv("MM_ASR_PYTHON", "C:/venvs/asr/python.exe")
    monkeypatch.setattr(vc, "find_spec", lambda name: object())
    assert vc.default_python() == "C:/venvs/asr/python.exe"
    monkeypatch.delenv("MM_ASR_PYTHON")
    assert vc.default_python() == sys.executable                                      # faster_whisper est ici
    monkeypatch.setattr(vc, "find_spec", lambda name: None)
    other = vc.default_python().replace("\\", "/")
    assert other != sys.executable.replace("\\", "/") and "/.venv/" in other and str(mm_paths.S2S_ROOT.name) in other


# ───────────────────────── un essai complet ─────────────────────────

class LangASR:
    def __init__(self, words):
        self._words, self.langs = words, []

    def words(self, path, clip_end=None, lang=None):
        self.langs.append(lang)
        return self._words


def test_check_take_passes_the_language_to_whisper_and_to_the_comparison(tmp_path):
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    sr = 24000
    w = (0.5 * np.sin(2 * np.pi * 180 * np.arange(sr) / sr)).astype(np.float32)
    w[-int(0.05 * sr):] *= np.linspace(1, 0, int(0.05 * sr), dtype=np.float32)
    path = tmp_path / "v.wav"
    sf.write(path, w, sr)
    said = [(0.0, 0.1, "Et", 0.9), (0.1, 0.2, "d", 0.9), (0.2, 0.3, "'un", 0.9), (0.3, 0.5, "coup,", 0.9),
            (0.5, 0.6, "le", 0.9), (0.6, 0.75, "monde", 0.9), (0.75, 0.85, "se", 0.9), (0.85, 0.95, "tait.", 0.9)]
    asr = LangASR(said)
    problems, heard = vc.check_take(w, sr, path, TAIT, asr, lang="fr")
    assert problems == [] and heard == "Et d 'un coup, le monde se tait." and asr.langs == ["fr"]
    twice = LangASR(said + [(0.95, 0.96, "Le", 0.9), (0.96, 0.97, "monde", 0.9), (0.97, 0.98, "se", 0.9),
                            (0.98, 0.99, "tait.", 0.9)])
    problems, _ = vc.check_take(w, sr, path, TAIT, twice, lang="fr")
    assert any("repetition" in p for p in problems)
    assert vc.check_take(w, sr, path, TAIT, asr)[0]                               # en anglais, « d 'un » ne passe pas
