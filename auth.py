
import streamlit as st
from supabase import create_client


def get_supabase_client():
    """Kreira klijenta zasebno za trenutnu Streamlit sesiju."""
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )

    return st.session_state.supabase_client


def render_authentication():
    """Prikazuje prijavu i registraciju. Vraća True ako je korisnik prijavljen."""

    if st.session_state.get("user_id"):
        return True

    st.title("⚛️ FizikaAI")
    st.subheader("Dobro došao/la!")

    st.write(
        "Prijavi se da pristupiš svojim kvizovima "
        "i sačuvanom napretku."
    )

    try:
        client = get_supabase_client()
    except Exception:
        st.error(
            "Nedostaje konfiguracija baze podataka. "
            "Provjeri SUPABASE_URL i SUPABASE_KEY."
        )
        st.stop()

    login_tab, register_tab = st.tabs(
        ["🔑 Prijava", "📝 Registracija"]
    )

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            password = st.text_input(
                "Lozinka",
                type="password"
            )

            login_clicked = st.form_submit_button(
                "Prijavi se",
                use_container_width=True
            )

        if login_clicked:
            if not email.strip() or not password:
                st.warning("Unesi e-mail i lozinku.")
            else:
                try:
                    response = client.auth.sign_in_with_password({
                        "email": email.strip(),
                        "password": password
                    })

                    user = response.user

                    if user is None:
                        st.error("Prijava nije uspjela.")
                    else:
                        st.session_state.user_id = str(user.id)
                        st.session_state.user_email = user.email
                        st.rerun()

                except Exception:
                    st.error(
                        "Prijava nije uspjela. Provjeri podatke "
                        "ili potvrdi e-mail ako je to potrebno."
                    )

    with register_tab:
        with st.form("register_form"):
            email_new = st.text_input(
                "E-mail adresa",
                key="register_email"
            )
            password_new = st.text_input(
                "Nova lozinka",
                type="password",
                key="register_password"
            )
            password_confirm = st.text_input(
                "Ponovi lozinku",
                type="password",
                key="register_password_confirm"
            )

            register_clicked = st.form_submit_button(
                "Kreiraj račun",
                use_container_width=True
            )

        if register_clicked:
            if not email_new.strip():
                st.warning("Unesi e-mail adresu.")
            elif len(password_new) < 8:
                st.warning(
                    "Lozinka treba imati najmanje 8 znakova."
                )
            elif password_new != password_confirm:
                st.warning("Lozinke se ne podudaraju.")
            else:
                try:
                    response = client.auth.sign_up({
                        "email": email_new.strip(),
                        "password": password_new
                    })

                    if response.session and response.user:
                        st.session_state.user_id = str(
                            response.user.id
                        )
                        st.session_state.user_email = (
                            response.user.email
                        )
                        st.success("Račun je kreiran.")
                        st.rerun()
                    else:
                        st.success(
                            "Registracija je zaprimljena. "
                            "Provjeri e-mail i potvrdi račun, "
                            "a zatim se prijavi."
                        )

                except Exception:
                    st.error(
                        "Registracija nije uspjela. "
                        "Provjeri e-mail i pravila registracije."
                    )

    return False


def logout():
    """Odjavljuje korisnika i uklanja podatke prijavljene sesije."""
    client = st.session_state.get("supabase_client")

    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass

    for key in (
        "user_id",
        "user_email",
        "supabase_client",
        "quiz_history",
        "active_quizzes",
        "quiz_counter",
        "progress"
    ):
        st.session_state.pop(key, None)
