import streamlit as st
import re
import pandas as pd
import altair as alt

from auth import (
    render_authentication,
    get_supabase_client,
    logout
)

from database import (
    save_quiz_attempt,
    load_quiz_attempts
)

from chatbot import (
    generate_response,
    generate_lesson,
    generate_quiz
)

from config import (
    TOPICS,
    TOPIC_GRADES
)

from quiz_data import QUIZZES


def clean_math_format(text):
    """Popravlja uobičajene LaTeX formate u AI odgovorima."""

    if not isinstance(text, str):
        return text

    # Pretvori LaTeX delimitere u Markdown formate.
    text = re.sub(
        r"\\\((.*?)\\\)",
        r"$\1$",
        text,
        flags=re.DOTALL
    )

    text = re.sub(
        r"\\\[(.*?)\\\]",
        r"$$\n\1\n$$",
        text,
        flags=re.DOTALL
    )

    # Prepoznaj formule koje je AI stavio u obične zagrade,
    # ali ih nije označio znakom $.
    def fix_parenthesized_math(match):
        expression = match.group(1).strip()

        math_indicators = (
            r"\\text",
            r"\\frac",
            r"\\sqrt",
            r"\\mathrm",
            r"\\cdot",
            r"\\times",
            "^",
            "_",
            "="
        )

        if any(indicator in expression for indicator in math_indicators):
            return f"${expression}$"

        return match.group(0)

    text = re.sub(
        r"(?<!\$)\(([^()\n]*?(?:\\text|\\frac|\\sqrt|\\mathrm|\\cdot|\\times|\^|_|=)[^()\n]*?)\)(?!\$)",
        fix_parenthesized_math,
        text
    )

    return text

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="FizikaAI",
    page_icon="⚛️",
    layout="wide"
)

if not render_authentication():
    st.stop()

supabase = get_supabase_client()
user_id = st.session_state.user_id
user_email = st.session_state.get("user_email", "")

# Učitaj trajnu historiju prijavljenog učenika.
try:
    quiz_history_db = load_quiz_attempts(
        client=supabase,
        user_id=user_id
    )
except Exception as error:
    st.error(
        "Ne mogu učitati historiju iz baze. "
        "Provjeri Supabase konekciju i pokušaj ponovo."
    )
    st.stop()

# Pripremi rezultate za postojeće grafove i prikaz kvizova.
db_history_by_topic = {topic: [] for topics in TOPICS.values() for topic in topics}

for row in quiz_history_db:
    topic = row["topic"]

    if topic not in db_history_by_topic:
        continue

    saved_questions = row.get("questions") or []

    # Prilagodi format pitanja formatu koji koristi aplikacija.
    normalized_questions = [
        {
            "question": q.get("question", ""),
            "options": q.get("options", []),
            "answer": q.get("correct_answer", ""),
            "explanation": q.get("explanation", "")
        }
        for q in saved_questions
    ]

    db_history_by_topic[topic].append({
        "quiz_id": row["id"],
        "quiz_number": len(db_history_by_topic[topic]) + 1,
        "score": row["score"],
        "total": row["total"],
        "percentage": float(row["percentage"]),
        "questions": normalized_questions,
        "created_at": row["created_at"]
    })

# Statistika se uvijek računa iz trajno sačuvanih rezultata.
st.session_state.quiz_history = db_history_by_topic
st.session_state.progress = {}

for topic, attempts in db_history_by_topic.items():
    st.session_state.progress[topic] = {
        "attempts": sum(item["total"] for item in attempts),
        "correct": sum(item["score"] for item in attempts)
    }

with st.sidebar:
    st.caption(f"Prijavljen/a: {user_email}")

    if st.button("Odjavi se", use_container_width=True):
        logout()
        st.rerun()


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = "Kinematika"


if "chats" not in st.session_state:
    st.session_state.chats = {}


if "lessons" not in st.session_state:
    st.session_state.lessons = {}


if "progress" not in st.session_state:
    st.session_state.progress = {}

if "quiz_history" not in st.session_state:
    st.session_state.quiz_history = {}

for topic_list in TOPICS.values():
    for topic in topic_list:
        if topic not in st.session_state.quiz_history:
            st.session_state.quiz_history[topic] = []

if "active_quizzes" not in st.session_state:
    st.session_state.active_quizzes = {}

if "quiz_history" not in st.session_state:
    st.session_state.quiz_history = {}

if "quiz_counter" not in st.session_state:
    st.session_state.quiz_counter = 0

for grade, topic_list in TOPICS.items():

    for topic in topic_list:

        if topic not in st.session_state.chats:
            st.session_state.chats[topic] = []

        if topic not in st.session_state.progress:

            st.session_state.progress[topic] = {
                "attempts": 0,
                "correct": 0
            }
        if topic not in st.session_state.quiz_history:
            st.session_state.quiz_history[topic] = []


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.title("⚛️ FizikaAI")

    st.caption(
        "AI tutor za srednjoškolsku fiziku"
    )

    st.divider()

    st.subheader("📚 Razredi i oblasti")

    for grade, topic_list in TOPICS.items():

        current_grade = TOPIC_GRADES.get(
            st.session_state.selected_topic
        )

        with st.expander(
            grade,
            expanded=(grade == current_grade)
        ):

            for topic in topic_list:

                if st.button(
                    topic,
                    key=f"topic_{grade}_{topic}",
                    use_container_width=True
                ):

                    st.session_state.selected_topic = topic

                    st.rerun()

    st.divider()

    st.subheader("📊 Moj napredak")

    current_topic = (
        st.session_state.selected_topic
    )

    stats = (
        st.session_state
        .progress[current_topic]
    )

    if stats["attempts"] > 0:

        percentage = (
            stats["correct"]
            /
            stats["attempts"]
            * 100
        )

        st.metric(
            "Tačnost",
            f"{percentage:.0f}%"
        )

        st.progress(
            min(
                percentage / 100,
                1.0
            )
        )

        st.caption(
            f"Tačnih odgovora: "
            f"{stats['correct']} / "
            f"{stats['attempts']}"
        )

    else:

        st.caption(
            "Još nema rezultata za ovu oblast."
        )

    st.divider()

    if st.button(
        "🗑️ Očisti razgovor",
        use_container_width=True
    ):

        st.session_state.chats[
            current_topic
        ] = []

        st.rerun()


# --------------------------------------------------
# CURRENT TOPIC
# --------------------------------------------------

current_topic = (
    st.session_state.selected_topic
)

current_grade = TOPIC_GRADES[
    current_topic
]


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.caption(current_grade)

st.title(
    f"📖 {current_topic}"
)

st.caption(
    "Uči iz nastavnih materijala, "
    "postavljaj pitanja i provjeri znanje."
)

st.divider()


# --------------------------------------------------
# TABS
# --------------------------------------------------

tab_chat, tab_lesson, tab_quiz, tab_progress = st.tabs(
    [
        "💬 Pitaj tutora",
        "📖 Lekcija",
        "📝 Provjera znanja",
        "📊 Moj napredak"
    ]
)


# ==================================================
# CHAT
# ==================================================

with tab_chat:

    current_chat = (
        st.session_state
        .chats[current_topic]
    )

    if not current_chat:

        st.info(
            "Postavi pitanje iz ove oblasti. "
            "FizikaAI će koristiti nastavne "
            "materijale kao osnovu za odgovor."
        )

    for message in current_chat:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

    prompt = st.chat_input(
        f"Postavi pitanje iz oblasti: "
        f"{current_topic}",
        key=f"chat_input_{current_topic}"
    )

    if prompt:

        current_chat.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):

            st.markdown(prompt)

        with st.chat_message("assistant"):

            with st.spinner(
                "FizikaAI razmišlja..."
            ):

                response = (
                    generate_response(
                        question=prompt,
                        topic=current_topic,
                        chat_history=
                            current_chat[:-1]
                    )
                )

            st.markdown(response)

        current_chat.append({
            "role": "assistant",
            "content": response
        })

        st.rerun()


# ==================================================
# LESSON
# ==================================================

with tab_lesson:

    st.subheader(
        f"📖 Lekcija: {current_topic}"
    )

    st.caption(
        "Lekcija se generiše na osnovu "
        "nastavnih materijala za ovu oblast."
    )

    if current_topic in (
        st.session_state.lessons
    ):

        lesson_text = st.session_state.lessons[current_topic]

        st.markdown(
            clean_math_format(lesson_text)
        )

    else:

        if st.button(
            "✨ Generiši lekciju",
            key=f"lesson_{current_topic}"
        ):

            with st.spinner(
                "Pripremam lekciju..."
            ):

                lesson = generate_lesson(
                    current_topic
                )

            st.session_state.lessons[
                current_topic
            ] = lesson

            st.rerun()


# ==================================================
# QUIZ
# ==================================================


with tab_quiz:
    st.subheader(f"📝 Provjera znanja: {current_topic}")

    st.write(
        "Pokreni novi kviz kad god želiš. "
        "Pitanja se generišu na osnovu nastavnih materijala."
    )

    # Izbor broja pitanja.
    num_questions = st.radio(
        "Koliko pitanja želiš?",
        [5, 10],
        horizontal=True,
        key=f"quiz_length_{current_topic}"
    )

    active_quiz = st.session_state.active_quizzes.get(
        current_topic
    )

    # Pokretanje novog kviza.
    if st.button(
        "✨ Generiši novi kviz",
        key=f"generate_quiz_{current_topic}",
        use_container_width=True
    ):
        previous_questions = [
            question["question"]
            for attempt in st.session_state.quiz_history[current_topic]
            for question in attempt.get("questions", [])
        ]

        with st.spinner("Pripremam nova pitanja..."):
            questions = generate_quiz(
                topic=current_topic,
                num_questions=num_questions,
                previous_questions=previous_questions
            )

        if questions:
            st.session_state.quiz_counter += 1

            st.session_state.active_quizzes[current_topic] = {
                "id": st.session_state.quiz_counter,
                "questions": questions,
                "submitted": False,
                "result": None
            }

            st.rerun()
        else:
            st.error(
                "Nisam uspjela pripremiti ispravan kviz. "
                "Pokušaj ponovo."
            )

    # Ponovo učitaj aktivni kviz nakon eventualnog rerun-a.
    active_quiz = st.session_state.active_quizzes.get(
        current_topic
    )

    if active_quiz is None:
        st.info(
            "Odaberi broj pitanja i klikni na "
            "„Generiši novi kviz“ da počneš."
        )

    else:
        questions = active_quiz["questions"]
        quiz_id = active_quiz["id"]

        st.divider()
        st.caption(
            f"Kviz #{quiz_id} · {len(questions)} pitanja"
        )

        # Ako je kviz već predan, prikaži sačuvane rezultate.
        if active_quiz["submitted"]:
            result = active_quiz["result"]

            st.metric(
                "Rezultat",
                f"{result['score']}/{result['total']}"
            )
            st.progress(result["score"] / result["total"])

            st.subheader("Pregled odgovora")

            for index, item in enumerate(
                result["review"], start=1
            ):
                st.markdown(
                    f"**{index}. {item['question']}**"
                )

                if item["correct"]:
                    st.success("Tačno!")
                else:
                    st.error("Netačno")

                    st.write(
                        "**Tvoj odgovor:**",
                        item["user_answer"] or "Nije odgovoreno"
                    )

                    st.write(
                        "**Tačan odgovor:**",
                        item["answer"]
                    )

                st.info(item["explanation"])

            st.button(
                "🔄 Započni novi kviz",
                key=f"next_quiz_{current_topic}_{quiz_id}",
                on_click=lambda: st.session_state.active_quizzes.pop(
                    current_topic, None
                ),
                use_container_width=True
            )

        else:
            with st.form(key=f"quiz_form_{current_topic}_{quiz_id}"):
                answers = []

                for index, question in enumerate(questions):
                    st.markdown(
                        f"### {index + 1}. {question['question']}"
                    )

                    answer = st.radio(
                        "Odaberi odgovor:",
                        question["options"],
                        index=None,
                        key=f"answer_{current_topic}_{quiz_id}_{index}"
                    )

                    answers.append(answer)

                submitted = st.form_submit_button(
                    "✅ Završi kviz",
                    use_container_width=True
                )

            if submitted:
                score = 0
                review = []

                for index, question in enumerate(questions):
                    user_answer = answers[index]
                    is_correct = user_answer == question["answer"]

                    if is_correct:
                        score += 1

                    review.append({
                        "question": question["question"],
                        "user_answer": user_answer,
                        "answer": question["answer"],
                        "correct": is_correct,
                        "explanation": question.get("explanation", "")
                    })

                total = len(questions)
                percentage = score / total * 100

                result = {
                    "score": score,
                    "total": total,
                    "percentage": percentage,
                    "review": review
                }

                # Prvo sačuvaj rezultat u trajnu bazu.
                try:
                    save_quiz_attempt(
                        client=supabase,
                        user_id=user_id,
                        topic=current_topic,
                        score=score,
                        total=total,
                        questions=questions,
                        answers=answers
                    )

                except Exception:
                    st.error(
                        "Rezultat nije potvrđeno sačuvan. "
                        "Provjeri konekciju i pokušaj ponovo. "
                        "Nemoj zatvarati stranicu dok ne riješiš problem."
                    )

                else:
                    # Označi kviz završenim tek nakon uspješnog spremanja.
                    active_quiz["submitted"] = True
                    active_quiz["result"] = result

                    st.session_state.progress[current_topic]["attempts"] += total
                    st.session_state.progress[current_topic]["correct"] += score

                    st.success("Rezultat je sačuvan u tvojoj historiji.")
                    st.rerun()


    # Historija završenih kvizova za trenutnu oblast.
    history = st.session_state.quiz_history[current_topic]

    if history:
        st.divider()
        st.subheader("📈 Historija kvizova")

        for attempt in reversed(history):
            st.write(
                f"Kviz #{attempt.get('quiz_id', attempt.get('quiz_number', '?'))}: "
                f"{attempt['score']}/{attempt['total']} "
                f"({attempt['percentage']:.0f}%)"
            )


# ==================================================
# PROGRESS DASHBOARD
# ==================================================

with tab_progress:

    st.subheader("📊 Moj napredak")
    st.caption(
        "Ovdje možeš pratiti rezultate kvizova po oblastima "
        "i vidjeti šta bi bilo korisno ponoviti."
    )

    # Collect totals across all available topics.
    all_topics = [topic for topic_list in TOPICS.values() for topic in topic_list]
    total_attempts = sum(
        st.session_state.progress[topic]["attempts"]
        for topic in all_topics
    )
    total_correct = sum(
        st.session_state.progress[topic]["correct"]
        for topic in all_topics
    )
    topics_attempted = sum(
        1 for topic in all_topics
        if st.session_state.progress[topic]["attempts"] > 0
    )

    overall_accuracy = (
        total_correct / total_attempts * 100
        if total_attempts > 0 else 0
    )

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Ukupna tačnost", f"{overall_accuracy:.0f}%")
    metric2.metric("Tačnih odgovora", f"{total_correct} / {total_attempts}")
    metric3.metric("Vježbane oblasti", f"{topics_attempted} / {len(all_topics)}")

    st.progress(overall_accuracy / 100 if total_attempts else 0.0)
    st.divider()
    st.markdown("### 📚 Rezultati po oblastima")

    topic_results = []
    for topic in all_topics:
        stats = st.session_state.progress[topic]
        attempts = stats["attempts"]
        correct = stats["correct"]
        accuracy = correct / attempts * 100 if attempts else 0
        topic_results.append({
            "topic": topic,
            "attempts": attempts,
            "correct": correct,
            "accuracy": accuracy,
        })

        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"**{topic}**")
            if attempts == 0:
                right.caption("Još nema rezultata")
                left.progress(0.0)
                left.caption("Riješi kviz iz ove oblasti da bi se prikazao napredak.")
            else:
                if accuracy >= 80:
                    status = "🟢 Dobro usvojeno"
                elif accuracy >= 50:
                    status = "🟡 Potrebno još vježbe"
                else:
                    status = "🔴 Ponoviti gradivo"
                right.metric("Tačnost", f"{accuracy:.0f}%")
                left.progress(accuracy / 100)
                left.caption(f"{correct} tačnih od {attempts} odgovora · {status}")

        st.divider()
    st.markdown("### 📈 Kako napredujem kroz kvizove?")

    selected_topic = st.selectbox(
        "Odaberi oblast za pregled napretka:",
        all_topics,
        key="progress_chart_topic"
    )

    history = st.session_state.quiz_history.get(
        selected_topic, []
    )

    if len(history) >= 1:
        chart_data = {
            "Kviz": [
                f"Kviz {item.get('quiz_number', item.get('quiz_id', i + 1))}"
                for i, item in enumerate(history)
            ],
            "Rezultat (%)": [
                item["percentage"]
                for item in history
            ]
        }

        chart_df = pd.DataFrame(chart_data)

        chart = (
            alt.Chart(chart_df)
            .mark_line(
                point=alt.OverlayMarkDef(size=90),
                strokeWidth=3
            )
            .encode(
                x=alt.X(
                    "Kviz:N",
                    title="Redni broj kviza",
                    sort=None,
                    axis=alt.Axis(labelAngle=0)
                ),
                y=alt.Y(
                    "Rezultat (%):Q",
                    title="Rezultat (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(values=[0, 20, 40, 60, 80, 100])
                ),
                tooltip=[
                    alt.Tooltip("Kviz:N", title="Kviz"),
                    alt.Tooltip(
                        "Rezultat (%):Q",
                        title="Rezultat",
                        format=".0f"
                    )
                ]
            )
            .properties(height=320)
        )

        st.altair_chart(chart, use_container_width=True)

        latest = history[-1]["percentage"]

        if len(history) >= 2:
            previous = history[-2]["percentage"]
            difference = latest - previous

            if difference > 0:
                st.success(
                    f"📈 Napreduješ! Rezultat ti je porastao "
                    f"za {difference:.0f} procentnih poena "
                    f"u odnosu na prethodni kviz."
                )
            elif difference < 0:
                st.info(
                    "Svaki kviz je prilika za učenje. "
                    "Pogledaj koja pitanja su ti bila teška "
                    "i pokušaj ponovo."
                )
            else:
                st.info(
                    "Rezultat ti je stabilan. Pokušaj "
                    "primijeniti znanje na zahtjevnija pitanja."
                )
        else:
            st.info(
                "Odlično, zabilježen je prvi rezultat! "
                "Riješi još kvizova da bi mogao/la pratiti "
                "promjenu rezultata."
            )
    else:
        st.info(
            "Ovdje će se prikazati tvoj napredak "
            "kada završiš prvi kviz iz ove oblasti."
        )

        st.divider()
    st.markdown("### 🎯 U čemu sam trenutno najjači/a?")

    chart_rows = []

    for topic in all_topics:
        history = st.session_state.quiz_history.get(topic, [])

        if history:
            # Prosjek svih završenih kvizova iz oblasti
            average = sum(
                item["percentage"] for item in history
            ) / len(history)

            chart_rows.append({
                "Oblast": topic,
                "Prosječan rezultat (%)": average
            })

    if chart_rows:
        st.bar_chart(
            chart_rows,
             x="Oblast",
            y="Prosječan rezultat (%)"
        )
    else:
        st.info(
            "Kada završiš kvizove iz različitih oblasti, "
            "ovdje ćeš moći uporediti svoje rezultate."
        )

    st.divider()
    st.markdown("### 🎯 Preporuka za dalje učenje")

    attempted_results = [item for item in topic_results if item["attempts"] > 0]
    if not attempted_results:
        st.info(
            "Još nema dovoljno podataka za preporuku. Otvori karticu "
            "‘Provjera znanja’, riješi prvi kviz, a rezultati će se pojaviti ovdje."
        )
    else:
        weakest = min(attempted_results, key=lambda item: item["accuracy"])
        if weakest["accuracy"] >= 80:
            st.success(
                "Odličan rezultat! Za sada nema oblasti s niskom tačnošću. "
                "Nastavi vježbati i provjeri znanje i iz drugih oblasti."
            )
        else:
            st.warning(
                f"Preporuka: ponovi oblast **{weakest['topic']}**. "
                f"Trenutna tačnost je {weakest['accuracy']:.0f}% "
                f"({weakest['correct']} od {weakest['attempts']} odgovora)."
            )
            st.write(
                "Možeš otvoriti ovu oblast u meniju s lijeve strane, "
                "pregledati lekciju ili pitati tutora za dodatno objašnjenje, "
                "a zatim ponovo riješiti kviz."
            )

    st.caption(
        "Rezultati završenih kvizova čuvaju se na tvom računu. "
        "Možeš im pristupiti nakon ponovne prijave."
    )

