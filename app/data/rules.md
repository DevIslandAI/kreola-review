# Kreola transcription rules: v1.0 (locked 27 Oct 2026)

Approved by the reviewer on 27 Oct 2026; v0.1 (21 Oct) is kept for history. These rules apply to the human review
(the 10 h golden set) **and** to every automatic correction of the myt drafts: both must produce the same kind of text.

**Golden rule: write exactly what is said, spelled the official way.** Don't correct grammar, don't translate, don't summarise.

Spelling reference: *Lortograf Kreol Morisien* (Akademi Kreol Morisien, April 2011, Dr Arnaud Carpooran).
Local copy: `vocabulary/reference/Lortograf_Kreol_Morisien_2011.pdf`. Individual words follow the *Diksioner Morisien* (Carpooran) and our `KREOLA_VOCABULARY.xlsx`.

---

## A. Kreol words: one sound, one letter (Lortograf, part 5)

| Write | Sound | Examples | Never |
|---|---|---|---|
| `ou` | [u] | dimounn, koulou, tou | ~~u~~ (`u` is only for English words: burger, rush) |
| `k` | [k] | lakaz, koz, kiksoz | ~~c, qu~~ (except CD, CV, Celsius) |
| `s` | [s] | lasal, fos, nasion | ~~ç, ss, c~~ |
| `z` | [z] and French "j" | zanfan, manze, biznes | ~~j, g~~ for that sound |
| `ch` / `sh` | [tʃ] / [ʃ] | chak, koucha / shoping, kash | |
| `j` | [dʒ] | baj, joukal | |
| `w` | [w] | trwa, lerwa, wit | ~~oi~~ |
| `y` | at start or end of a syllable | yer, karay, vwayel | inside a syllable use `i`: bien, nasion |
| `an` `on` `in` | nasal vowels | larzan, onz, dipin | ~~en, em, ain, ein~~ (but ansien, leng) |
| vowel + `nn` | vowel plus a pronounced n | bann, enn, dimounn, minn, semenn | |
| `x` | [ks] or [gz] | taxi, text, exak, exit | (but aksidan, aksepte: see Annex 1) |

- No accents and no silent letters (é becomes e).
- Words that merged with the article stay one word: **lakaz, lafnet, lipie, laport**. Never write ~~la case~~.

## B. Hyphens (Lortograf 6.2, Annex 2)

| Case | Write | But |
|---|---|---|
| Article "-la" right after the noun | tifi-la, papa-la | sa garson intelizan **la** (separated: no hyphen) |
| ti-/gro-/gran- used as a prefix | ti-baba, gran-dimounn, gro-pwa | enn ti loto (simple adjective: no hyphen) |
| Repeated words | vit-vit, ble-ble, ale-vini, bat-bate | |
| Hours and ages | enn-er, de-z-er, trwa-z-er, de-z-an | enn an, sink an |
| Long compounds | masinn-a-lave, sal-a-manze | |

## C. Contractions: write what was said (decided 27 Oct 2026)

The Lortograf prefers full forms in school writing, but gives the spelling of the short forms for transcribing speech
(section 6.6.4). **We write the form that was actually said**, because the model must learn the sound people make.

| Said | Write | Not | Why (Lortograf 6.6.4) |
|---|---|---|---|
| pa + ena (short) | **pena** | ~~p'ena~~ | frequent and no other word sounds the same: no apostrophe |
| pa + ankor (short) | **pankor** | ~~p'ankor~~ | same |
| pa + finn (short) | **pa'nn** | ~~pann~~ | *pann* already exists (breakdown): apostrophe avoids confusion |
| pa + oule (short) | **pa'le** | ~~pale~~ | *pale* already exists (to speak) |
| mo / li / to / nou / ki + inn | **mo'nn, li'nn, to'nn, nou'nn, ki'nn** | ~~monn, linn, tonn~~ | same principle (the Lortograf writes mo'nn, li'nn) |
| mo + oule | **mo'le** | | Lortograf form |
| li / ti + a (future) | **li'a, ti'a** | | Lortograf form |
| the full form was said | full form: **pa ena, pa finn, mo finn** | | never shorten what was said in full |

- The apostrophe is always the straight one: `'` (not `’`).
- A short form not in this table follows the same principle: no apostrophe if it is common and cannot be mistaken for
  another word, an apostrophe otherwise. Each new one is added to `KREOLA_VOCABULARY.xlsx` so it is always spelled the same.

## D. Numbers: written as words (Annex 3)

- Examples: de-mil, vint-e-enn, katrovin-dis, enn-er-edmi, sink-san roupi.
- Never digits or symbols (~~Rs 500~~), because the model must learn the sounds.
- If the number is said in French or English inside a French or English sentence, write it as a word in that language.

## E. French and English inside Kreol (code-switching): mixed rule (decided 27 Oct 2026)

| Situation | Write | Example |
|---|---|---|
| Single borrowed word that is in the Diksioner or our vocabulary sheet | Kreol spelling | miting, biznes, parking, lekonomi |
| Other single English word | normal English, **no quotation marks** | deal, save, email, delete |
| Speaker switches to a French **phrase** (French grammar) | normal French, with accents, **no quotation marks** | c'est vraiment important |
| Speaker switches to an English **phrase** | normal English, no quotation marks | at the end of the day |

- Example: *nou ti ena enn miting lor sa biznes la, c'est vraiment important*.
- The vocabulary sheet decides single words, so the same word is always spelled the same way. myt is inconsistent
  today (business 328 times, biznes 320; meeting 35, miting 29): the automatic correction aligns them on the sheet.
- A French phrase keeps French spelling even inside a Kreol sentence; a single French word that Kreol has adopted
  (in the Diksioner) takes Kreol spelling.

## F. Names, brands, acronyms (Lortograf 6.4)

- **People and places:** official spelling (Port-Louis, Rose-Hill, Curepipe).
- **Countries:** the established Kreol form (Moris, Lafrans, Langleter, Lenn, Larenion, Rodrig).
- **Acronyms:** capitals, no dots, as listed in `KREOLA_VOCABULARY.xlsx` (MCB, MRA, CEB).

## G. Capitals and punctuation (Lortograf 6.1)

- Punctuation is English style.
- Capital letter at the start of a sentence.
- Capitals on days, months, languages and peoples: Lindi, Zanvie, Kreol, Franse.
- Lower case when used as an adjective: lang kreol.

## H. Things that are not words: minimal (decided 27 Oct 2026)

**One tag only: `[inaudible]`**, when a word cannot be made out. Never guess. A clip containing `[inaudible]` is kept
in the dataset but left out of training.

Not written at all:
- hesitations (euh, hmm, ben used as a filler);
- laughter, music, noise, two people talking at once (the audio-side flags `music_bg` etc. already record these);
- a word the speaker cut off and restarted: write only the finished word.

Why so few: the automatic correction of the other ~84 h works from text and cannot hear these events. If only the
human-reviewed 10 h contained them, the training text would be inconsistent. myt writes none of them either (0 tags in 18,962 drafts).

---

### Decisions taken on 27 Oct 2026
1. Contractions: **as spoken**, in the Lortograf 6.6.4 spelling (section C).
2. Code-switching: **mixed rule** (section E): borrowed words from the vocabulary sheet in Kreol spelling, other
   English words in English, whole French/English phrases in that language.
3. Tags: **minimal** (section H): `[inaudible]` only; hesitations and sound events are not written.

### What the myt drafts need (measured 27 Oct 2026 on 18,962 drafts)
- 4,052 drafts contain digits, which must become words (section D).
- Short forms are spelled inconsistently (monn 489 vs mo'nn 2,207; pann 648 vs pa'nn 344, where *pann* can also be the noun).
- Borrowed words are spelled both ways (business/biznes, meeting/miting).
