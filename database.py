
def save_quiz_attempt(
    client,
    user_id,
    topic,
    score,
    total,
    questions,
    answers
):
    """Trajno sprema završeni kviz za prijavljenog učenika."""

    if not user_id:
        raise ValueError("Korisnik nije prijavljen.")

    if total <= 0:
        raise ValueError("Kviz mora sadržavati barem jedno pitanje.")

    if score < 0 or score > total:
        raise ValueError("Broj tačnih odgovora nije validan.")

    if len(questions) != total:
        raise ValueError("Broj pitanja ne odgovara ukupnom broju pitanja.")

    percentage = round(score / total * 100, 2)

    question_records = []

    for index, question in enumerate(questions):
        question_records.append({
            "question": question["question"],
            "options": question["options"],
            "correct_answer": question["answer"],
            "user_answer": (
                answers[index]
                if index < len(answers)
                else None
            ),
            "explanation": question.get("explanation", "")
        })

    record = {
        "user_id": user_id,
        "topic": topic,
        "score": score,
        "total": total,
        "percentage": percentage,
        "questions": question_records
    }

    response = (
        client.table("quiz_attempts")
        .insert(record)
        .execute()
    )

    if not response.data:
        raise RuntimeError("Rezultat nije sačuvan u bazi.")

    return response.data[0]


def load_quiz_attempts(client, user_id):
    """Učitava historiju prijavljenog učenika, od najnovije."""

    response = (
        client.table("quiz_attempts")
        .select(
            "id, topic, score, total, percentage, "
            "questions, created_at"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        .execute()
    )

    return response.data or []
