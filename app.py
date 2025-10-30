import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import re
import os
import time
from datetime import datetime, date

st.set_page_config(page_title="Мониторинг проектов vam.golosza.ru", layout="wide")
st.title("Мониторинг проектов")

BASE_URL = "https://vam.golosza.ru"
HISTORY_FILE = "history.xlsx"

@st.cache_data(ttl=600)
def get_projects_info():
    url = "https://vam.golosza.ru"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    projects = []
    seen_links = set()
    session = requests.Session()

    for a_tag in soup.find_all("a", href=True):
        link = a_tag["href"]
        if not link.startswith("/vote/"):
            continue
        full_link = f"{BASE_URL}{link}"
        if full_link in seen_links:
            continue

        seen_links.add(full_link)

        try:
            project_response = session.get(full_link, timeout=10)
            project_soup = BeautifulSoup(project_response.text, "html.parser")

            title_tag = project_soup.find("p", class_="title")
            title = title_tag.get_text(strip=True) if title_tag else "Без названия"

            votes_tag = project_soup.find("span", class_="voting-count")
            votes = int(votes_tag.get_text(strip=True)) if votes_tag else 0

            projects.append({
                "Название проекта": title,
                "Ссылка на проект": full_link,
                "Количество голосов": votes
            })

            time.sleep(0.2)

        except Exception as e:
            print(f"Ошибка при обработке {full_link}: {e}")

    session.close()

    # 🟢 Преобразуем в DataFrame и сортируем
    df = pd.DataFrame(projects)
    if not df.empty:
        df = df.sort_values(by="Количество голосов", ascending=False).reset_index(drop=True)
    return df

def save_history(df):
    today = date.today().isoformat()
    df_save = df.copy()
    df_save["Дата"] = today
    if os.path.exists(HISTORY_FILE):
        old_df = pd.read_excel(HISTORY_FILE)
        df_save = pd.concat([old_df, df_save], ignore_index=True)
    df_save.to_excel(HISTORY_FILE, index=False)

def get_daily_diff(df_today: pd.DataFrame):
    if not os.path.exists(HISTORY_FILE):
        df_today["Изменение голосов"] = 0
        df_today.to_excel(HISTORY_FILE, index=False)
        return df_today

    df_old = pd.read_excel(HISTORY_FILE)

    # Очищаем и выравниваем ссылки
    df_old["Ссылка на проект"] = df_old["Ссылка на проект"].astype(str).str.extract(r'(https?://[^\s<]+)')[0]
    df_today["Ссылка на проект"] = df_today["Ссылка на проект"].astype(str).str.extract(r'(https?://[^\s<]+)')[0]

    df_today_compare = pd.merge(
        df_today,
        df_old[["Ссылка на проект", "Количество голосов"]],
        on="Ссылка на проект",
        how="left",
        suffixes=("", "_вчера")
    )

    df_today_compare["Изменение голосов"] = (
        df_today_compare["Количество голосов"] - df_today_compare["Количество голосов_вчера"].fillna(0)
    )

    df_today_compare.to_excel(HISTORY_FILE, index=False)
    df_today_compare = df_today_compare.sort_values(by="Изменение голосов", ascending=False).reset_index(drop=True)
    df_today_compare["Дата обновления"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return df_today_compare

def display_table(df, top_n=None):
    df_display = df.copy()
    df_display["Ссылка на проект"] = df_display["Ссылка на проект"].apply(
        lambda x: f"<a href='{x}' target='_blank'>Открыть</a>"
    )
    if top_n:
        df_display = df_display.head(top_n)
    st.write(df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

# --- Streamlit интерфейс ---
if st.button("🔄 Обновить данные с сайта"):
    df_today = get_projects_info()
    if df_today.empty:
        st.error("Не удалось получить данные. Возможно, сайт временно недоступен.")
    else:
        df_today = get_daily_diff(df_today)
        save_history(df_today)
        st.session_state["df_today"] = df_today
        st.success(f"Загружено {len(df_today)} проектов.")

df_today = st.session_state.get("df_today", pd.DataFrame())

if not df_today.empty:
    st.subheader("🔍 Поиск проектов")
    search_query = st.text_input("Введите название проекта").strip().lower()
    if search_query:
        df_filtered = df_today[df_today["Название проекта"].str.lower().str.contains(search_query)]
    else:
        df_filtered = df_today

    st.subheader("🔥 Топ-10 проектов по голосам")
    display_table(df_today, top_n=10)

    st.subheader("📋 Все проекты")
    display_table(df_filtered)
else:
    st.info("Нажми кнопку, чтобы загрузить список проектов 🚀")
