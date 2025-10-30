import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import re
import os
from datetime import date

st.set_page_config(page_title="Мониторинг проектов vam.golosza.ru", layout="wide")
st.title("Мониторинг проектов")

BASE_URL = "https://vam.golosza.ru/vote/list?page=&mo-search=бор&filter%5Baddress%5D%5B%5D=1&search=undefined"
PROJECT_BASE = "https://vam.golosza.ru/vote/"
HISTORY_FILE = "votes_history.csv"

@st.cache_data(ttl=600)
def get_projects_info():
    url = "https://vam.golosza.ru"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    projects = []
    seen_links = set()

    session = requests.Session()  # 🔹 повторно используем одно соединение

    for a_tag in soup.find_all("a", href=True):
        link = a_tag["href"]
        if not link.startswith("/vote/"):
            continue
        full_link = f"https://vam.golosza.ru{link}"
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
                "Название": title,
                "Ссылка": full_link,
                "Голоса": votes
            })

            time.sleep(0.2)  # 🔹 замедляем, чтобы не перегружать сайт

        except Exception as e:
            print(f"Ошибка при обработке {full_link}: {e}")

    session.close()  # 🔹 закрываем сессию
    return projects

def save_history(df):
    today = date.today().isoformat()
    df_save = df.copy()
    df_save["Дата"] = today
    df_save.to_csv(HISTORY_FILE, mode="a", index=False, header=not os.path.exists(HISTORY_FILE))

def get_daily_diff(df_today):
    if not os.path.exists(HISTORY_FILE):
        df_today["Прирост голосов"] = 0
        return df_today

    df_history = pd.read_csv(HISTORY_FILE)
    yesterday = df_history["Дата"].max()
    df_yesterday = df_history[df_history["Дата"] == yesterday]

    df_today_compare = df_today.copy()
    df_today_compare["Ссылка на проект"] = df_today_compare["Ссылка на проект"].str.extract(r'(https://.*)')[0]

    df_merge = pd.merge(df_today_compare, df_yesterday,
                        left_on="Ссылка на проект", right_on="Ссылка на проект",
                        how="left", suffixes=("_today", "_yesterday"))

    df_today["Прирост голосов"] = (df_merge["Количество голосов_today"] - df_merge["Количество голосов_yesterday"].fillna(0)).astype(int)
    return df_today

def display_table(df, top_n=None):
    df_display = df.copy()
    df_display["Ссылка на проект"] = df_display["Ссылка на проект"].apply(
        lambda x: f"<a href='{x}' target='_blank'>Ссылка</a>"
    )
    if top_n:
        df_display = df_display.head(top_n)
    st.write(df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

# --- Streamlit интерфейс ---
# Получение данных с кнопкой
if st.button("🔄 Обновить данные с сайта"):
    df_today = get_projects_info()
    df_today = get_daily_diff(df_today)
    save_history(df_today)
    st.session_state["df_today"] = df_today
    st.success(f"Загружено {len(df_today)} проектов.")

# Используем данные из сессии, если они есть
df_today = st.session_state.get("df_today", pd.DataFrame())

if not df_today.empty:
    # Поиск в реальном времени
    st.subheader("🔍 Поиск проектов")
    search_query = st.text_input("Введите название проекта для поиска").strip().lower()

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

