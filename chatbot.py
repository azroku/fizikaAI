import os
from functools import lru_cache
import json

from dotenv import load_dotenv
from groq import Groq

from config import KNOWLEDGE_BASES
from rag.retriever import PhysicsRetriever

import re


load_dotenv()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# --------------------------------------------------
# RETRIEVER CACHE
# --------------------------------------------------

@lru_cache(maxsize=10)
def get_retriever(topic):

    knowledge_base_path = (
        KNOWLEDGE_BASES.get(topic)
    )

    if not knowledge_base_path:
        return None

    return PhysicsRetriever(
        knowledge_base_path
    )


# --------------------------------------------------
# RAG CONTEXT
# --------------------------------------------------

def get_rag_context(
    question,
    topic,
    top_k=4
):

    retriever = get_retriever(topic)

    if retriever is None:
        return "", []

    results = retriever.search(
        question,
        top_k=top_k
    )

    # If retrieval is extremely weak,
    # don't pretend that the material contains
    # the answer.
    if (
        not results
        or results[0]["score"] < 0.30
    ):
        return "", results

    context_parts = []

    for i, result in enumerate(
        results,
        start=1
    ):

        context_parts.append(
            f"""
IZVOR {i}
Dokument: {result["source"]}

{result["text"]}
"""
        )

    return (
        "\n".join(context_parts),
        results
    )


# --------------------------------------------------
# CHAT
# --------------------------------------------------
def clean_model_response(text):
    """
    Cleans LLM output before displaying it in Streamlit.
    """

    # --------------------------------------------------
    # 1. Convert LaTeX delimiters to Streamlit-friendly
    # --------------------------------------------------

    # \( ... \)  ->  $ ... $
    text = re.sub(
        r"\\\((.*?)\\\)",
        r"$\1$",
        text,
        flags=re.DOTALL
    )

    # \[ ... \]  ->  $$ ... $$
    text = re.sub(
        r"\\\[(.*?)\\\]",
        r"$$\1$$",
        text,
        flags=re.DOTALL
    )

    # --------------------------------------------------
    # 2. Fix common Serbian / Ekavian forms
    # --------------------------------------------------

    replacements = {
        "svetlost": "svjetlost",
        "Svetlost": "Svjetlost",

        "vreme": "vrijeme",
        "Vreme": "Vrijeme",

        "telo": "tijelo",
        "Telo": "Tijelo",

        "primer": "primjer",
        "Primer": "Primjer",

        "sledeći": "sljedeći",
        "Sledeći": "Sljedeći",

        "promena": "promjena",
        "Promena": "Promjena",

        "rešenje": "rješenje",
        "Rešenje": "Rješenje",

        "smer": "smjer",
        "Smer": "Smjer",

        "deo": "dio",
        "Deo": "Dio",

        "uslov": "uvjet",
        "Uslov": "Uvjet",

        "tačka gledišta": "gledište",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def generate_response(
    question,
    topic,
    chat_history=None
):

    rag_context, results = (
        get_rag_context(
            question,
            topic
        )
    )

    if rag_context:

        material_instruction = f"""
Relevantni dijelovi nastavnih materijala:

----------------------------
{rag_context}
----------------------------
"""

    else:

        material_instruction = """
Za ovo pitanje nije pronađen dovoljno
relevantan sadržaj u dostupnim nastavnim
materijalima.
"""

    system_prompt = f"""
Ti si FizikaAI, AI tutor za učenike
srednje škole.

Trenutna oblast učenika je:

{topic}

{material_instruction}

Tvoj cilj je pomoći učeniku da razumije
fiziku, a ne samo dati konačan odgovor.

PRAVILA:

1. Odgovaraj isključivo na standardnom bosanskom jeziku.

Koristi ijekavski oblik riječi.

Primjeri pravilnog izražavanja:

- svjetlost, NE svetlost
- vrijeme, NE vreme
- tijelo, NE telo
- primjer, NE primer
- sljedeći, NE sledeći
- promjena, NE promena
- rješenje, NE rešenje
- smjer, NE smer
- dio, NE deo
- uvjet, NE uslov

Ako nastavni materijal koristi drugačiji jezički oblik,
prilikom objašnjavanja učeniku preformuliši ga na bosanski
jezik, ali nemoj mijenjati fizičko značenje.

2. Kada nastavni materijal sadrži odgovor,
koristi ga kao glavni izvor.

3. Nemoj kopirati nastavne materijale
riječ po riječ. Objasni svojim riječima.

4. Nemoj tvrditi da nešto postoji u
nastavnom materijalu ako nije pronađeno
u dostavljenom kontekstu.

5. Ako pitanje nije vezano za trenutnu
oblast ili dostupni materijal nije dovoljan,
reci učeniku da dostupna baza za tu oblast
nema dovoljno informacija.

6. Objašnjenja prilagodi srednjoškolcu.

7. Kada objašnjavaš pojam:
- daj kratku definiciju,
- objasni značenje,
- navedi formulu ako je potrebna,
- daj jednostavan primjer.

8. Kod računskih zadataka:
- napiši poznate veličine,
- napiši traženu veličinu,
- izaberi formulu,
- uvrsti vrijednosti,
- računaj korak po korak,
- napiši mjernu jedinicu,
- na kraju jasno napiši rezultat.

9. Ako učenik napravi grešku, nemoj samo
reći da je odgovor pogrešan. Objasni gdje
je greška i kako doći do ispravnog
razmišljanja.

10. Ohrabri učenika da razmišlja
samostalno.

FORMATIRANJE MATEMATIKE JE OBAVEZNO:

Svaki matematički izraz, formula, broj sa mjernom jedinicom
ili matematička varijabla mora biti napisana u LaTeX formatu.

Za kratke formule unutar rečenice koristi isključivo:

$formula$

Primjer:

Sila se računa kao $F = ma$.

Za važnije ili duže formule koristi zaseban red:

$$
v = \frac{{s}}{{t}}
$$

NIKADA nemoj pisati:

(F = ma)

\(F = ma\)

[F = ma]

ili:

v = s / t

ako se radi o matematičkoj formuli.

Umjesto toga napiši:

$F = ma$

i:

$$
v = \frac{{s}}{{t}}
$$

Mjerne jedinice također moraju biti dio LaTeX izraza.

Ispravno:

$v = 10\,\text{{m/s}}$

$a = 3\,\text{{m/s}}^2$

$F = 20\,\text{{N}}$

Pogrešno:

v = (10 m/s)

(3 m/s²)

F = 20 N

Kada rješavaš zadatak, koristi ovaj izgled:

**Poznato:**

$s = 100\,\text{{m}}$

$t = 20\,\text{{s}}$

**Formula:**

$$
v = \frac{{s}}{{t}}
$$

**Uvrštavanje:**

$$
v = \frac{{100\,\text{{m}}}}{{20\,\text{{s}}}}
$$

**Rezultat:**

$$
v = 5\,\text{{m/s}}
$$ """

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    if chat_history:

        for message in chat_history[-8:]:

            messages.append({
                "role":
                    message["role"],

                "content":
                    message["content"]
            })

    messages.append({
        "role": "user",
        "content": question
    })

    response = (
        client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.3,
            max_tokens=2000
        )
    )

    raw_response = (
    response
    .choices[0]
    .message
    .content
)

    return clean_model_response(raw_response)


# --------------------------------------------------
# LESSON GENERATOR
# --------------------------------------------------


def generate_lesson(topic):
    question = (
        f"Napravi kratku, preglednu lekciju iz oblasti: {topic}. "
        "Uključi najvažnije pojmove, definicije, formule i primjere."
    )

    context, results = get_rag_context(
        question,
        topic,
        top_k=6
    )

    if not context or not context.strip():
        return (
            f"Za oblast '{topic}' trenutno nema dovoljno "
            "dostupnog nastavnog materijala za generisanje lekcije."
        )

    prompt = f"""
Ti si FizikaAI, obrazovni asistent za fiziku u
gimnazijama u Bosni i Hercegovini.

TVOJ ZADATAK:
Odmah napiši kratku, jasnu i preglednu lekciju
za učenika srednje škole.

IZABRANA OBLAST:
{topic}

VAŽNA PRAVILA:
- Oblast je već izabrana. Nemoj pitati korisnika
  koju oblast želi učiti.
- Nastavni materijali su već dostavljeni ispod.
  Nemoj tražiti od korisnika da ih ponovo šalje.
- Piši na bosanskom jeziku i koristi ijekavicu.
- Koristi izraze uobičajene u nastavi fizike u BiH.
- Koristi dostavljene materijale kao glavni izvor.
- Nemoj izmišljati činjenice niti pripisivati
  materijalima informacije koje u njima ne postoje.
- Objašnjenja prilagodi učeniku gimnazije.
- Nemoj izostaviti važne definicije i formule
  koje su prisutne u dostavljenim materijalima.
- Ako materijali ne sadrže dovoljno informacija
  za neki dio lekcije, jasno naznači ograničenje.

STRUKTURA LEKCIJE:

# Najvažniji pojmovi
Objasni ključne pojmove jednostavnim riječima.

# Objašnjenje
Objasni fizičke pojave i veze između pojmova.

# Formule
Navedi relevantne formule iz nastavnih materijala.
Objasni svaki simbol i navedi njegovu mjernu jedinicu
kada je primjenjiva.

# Obrađeni primjer
Prikaži primjer zadatka i postupak rješavanja
korak po korak, ako materijali omogućavaju takav primjer.

# Zapamti
Izdvoji najvažnije činjenice za ponavljanje.

FORMATIRANJE MATEMATIKE — OBAVEZNO:

1. Sve matematičke izraze piši u LaTeX formatu
   koji podržava Streamlitov prikaz Markdowna.

2. Kratke formule piši između jednostrukih znakova $.
   Primjer: $v = \\frac{{s}}{{t}}$

3. Formule koje trebaju biti u zasebnom redu piši
   između dvostrukih znakova $$, na primjer:

   $$
   v = \\frac{{s}}{{t}}
   $$

4. Mjerne jedinice piši pravilno, na primjer:
   $3\\,\\text{{m/s}}$ ili $3\\,\\text{{m/s}}^2$.

5. Nemoj prikazivati matematičke formule samo
   u običnim zagradama.

6. Nemoj koristiti delimitere \\(...\\) ni \\[...\\].
   Koristi isključivo $...$ i $$...$$.

7. Nemoj stavljati Markdown podebljavanje unutar
   LaTeX naredbi. Ispravno je $\\frac{{s}}{{t}}$,
   a ne $**\\frac{{s}}{{t}}**$.

8. Ne stavljaj matematičke formule u obične
   jednostruke navodnike ili kodne blokove.

9. Nakon svake važne formule objasni značenje simbola
   i odgovarajuće mjerne jedinice.

10. Ne prikazuj sirovi LaTeX korisniku ako ga možeš
    zapisati ispravnim matematičkim formatiranjem.

NASTAVNI MATERIJALI:
--------------------
{context}
--------------------

Sada odmah generiši lekciju za oblast "{topic}".
Nemoj postavljati pitanja korisniku.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=2500
    )

    return response.choices[0].message.content

def generate_quiz(topic, num_questions=5, previous_questions=None):
    """
    Generiše novi kviz na osnovu nastavnih materijala
    za izabranu oblast.
    """

    previous_questions = previous_questions or []

    question = (
        f"Generiši {num_questions} pitanja za kviz iz oblasti "
        f"'{topic}'. Obuhvati različite pojmove iz oblasti."
    )

    context, results = get_rag_context(
        question,
        topic,
        top_k=6
    )

    if not context or not context.strip():
        return []

    previous_text = "\n".join(
        f"- {q}" for q in previous_questions[-30:]
    )

    prompt = f"""
Ti si stručni nastavnik fizike u gimnaziji u Bosni i Hercegovini.

Na osnovu dostavljenih nastavnih materijala napravi tačno
{num_questions} pitanja za kviz iz oblasti: {topic}.

JEZIK — OBAVEZNO:
- Cijeli kviz mora biti napisan na bosanskom jeziku,
  ijekavicom.
- Ovo pravilo važi za pitanje, sva četiri ponuđena
  odgovora i objašnjenje.
- Nemoj koristiti engleske riječi kao odgovore.
- Koristi stručne izraze iz nastave fizike u BiH.
- Primjeri:
  distance -> pređeni put
  displacement -> pomak
  velocity -> brzina
  acceleration -> ubrzanje
  time -> vrijeme
  systematic error -> sistematska greška
  random error -> slučajna greška
  gross error -> gruba greška
  instrumental error -> instrumentalna greška
- Formule, fizičke oznake i SI jedinice ostavi
  u standardnom zapisu.

OBLAST:
- Svako pitanje mora pripadati isključivo oblasti:
  {topic}
- Nemoj postavljati pitanja iz drugih oblasti fizike.
- Ako dostavljeni materijali ne sadrže dovoljno
  različitih pitanja, nemoj izmišljati sadržaj.

SADRŽAJ:
- Pitanja moraju biti zasnovana na dostavljenim materijalima.
- Napravi kombinaciju lakših, srednje teških i težih pitanja.
- Obuhvati različite pojmove, definicije i primjene formula
  koje su prisutne u materijalima.
- Koristi pitanja sa četiri ponuđena odgovora.
- Samo jedan odgovor smije biti tačan.
- Pogrešni odgovori trebaju biti uvjerljivi, ali nedvosmisleno pogrešni.
- Ne pravi pitanja na koja se može odgovoriti bez razumijevanja
  gradiva, ako materijali omogućavaju konceptualna pitanja.
- Nemoj izmišljati činjenice koje nisu podržane materijalima.
- Nemoj uključivati odgovore ili objašnjenja unutar teksta pitanja.

IZBJEGAVANJE PONAVLJANJA:
Pokušaj izbjeći sljedeća pitanja iz ranijih kvizova:
{previous_text if previous_text else "Nema ranijih pitanja."}

FORMAT ODGOVORA:
Vrati isključivo validan JSON niz. Nemoj dodavati Markdown,
uvod, komentar ili tekst izvan JSON-a.

Svaki element mora imati ovaj oblik:
{{
  "question": "Tekst pitanja",
  "options": [
    "Odgovor A",
    "Odgovor B",
    "Odgovor C",
    "Odgovor D"
  ],
  "answer": "Tačan odgovor, identičan jednoj opciji",
  "explanation": "Kratko objašnjenje zašto je odgovor tačan"
}}

VAŽNO:
- Polje "answer" mora biti potpuno identično jednoj od opcija.
- Svako pitanje mora biti različito od ostalih pitanja u ovom kvizu.
- Vrati tačno {num_questions} pitanja.

NASTAVNI MATERIJALI:
{context}
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=3500
        )

        raw = response.choices[0].message.content.strip()

        # Ukloni eventualne JSON code fence oznake.
        if raw.startswith("```"):
            raw = re.sub(
                r"^```(?:json)?\s*",
                "",
                raw
            )
            raw = re.sub(r"\s*```$", "", raw)

        questions = json.loads(raw)

        if not isinstance(questions, list):
            return []

        # Provjera formata pitanja prije prikaza učeniku.
        valid_questions = []

        for item in questions:
            if not isinstance(item, dict):
                continue

            text = item.get("question")
            options = item.get("options")
            answer = item.get("answer")
            explanation = item.get("explanation")

            if not (
                isinstance(text, str)
                and isinstance(options, list)
                and len(options) == 4
                and all(isinstance(x, str) for x in options)
                and isinstance(answer, str)
                and isinstance(explanation, str)
                and answer in options
                and len(set(options)) == 4
            ):
                continue

            valid_questions.append({
                "question": text,
                "options": options,
                "answer": answer,
                "explanation": explanation
            })

        # Ne prikazuj kviz ako nije dobijen traženi broj
        # ispravno formatiranih pitanja.
        if len(valid_questions) != num_questions:
            return []

        # Ukloni ponovljena pitanja unutar istog kviza.
        normalized = [
            q["question"].strip().casefold()
            for q in valid_questions
        ]

        if len(set(normalized)) != len(normalized):
            return []

        return valid_questions

    except Exception as error:
        print(f"Greška pri generisanju kviza: {error}")
        return []

