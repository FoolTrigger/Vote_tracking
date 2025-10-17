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
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].startswith(PROJECT_BASE) and PROJECT_BASE + "list" not in a["href"]
    ]

    projects = []
    seen_links = set()
    for link in links:
        if link in seen_links:
            continue
        seen_links.add(link)

        project_response = requests.get(link)
        project_soup = BeautifulSoup(project_response.text, "html.parser")

        title_tag = project_soup.find("p", class_="title")
        title = title_tag.text.strip() if title_tag else "Без названия"

        votes_tag = project_soup.find("div", class_="took-part-banner_count")
        if votes_tag:
            votes_numbers = re.findall(r'\d+', votes_tag.text)
            votes = int(votes_numbers[0]) if votes_numbers else 0
        else:
            votes = 0

        projects.append({
            "Название проекта": title,
            "Ссылка на проект": link,
            "Количество голосов": votes
        })

    df = pd.DataFrame(projects)
    df = df.sort_values(by="Количество голосов", ascending=False).reset_index(drop=True)
    df.index += 1
    df.index.name = "№"
    return df

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
