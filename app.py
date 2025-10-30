import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import time
import os
from datetime import datetime, date

# --- Настройки страницы ---
st.set_page_config(page_title="Мониторинг проектов vam.golosza.ru", layout="wide")
st.title("📊 Мониторинг проектов vam.golosza.ru")

BASE_URL = "https://vam.golosza.ru/vote/list?page=&mo-search=бор&filter%5Baddress%5D%5B%5D=1&search=undefined"
PROJECT_BASE = "https://vam.golosza.ru/vote/"
HISTORY_FILE = "votes_history.xlsx"

# --- Загрузка данных с сайта ---
@st.cache_data(ttl=600)
def get_projects_info():
    session = requests.Session()
    response = session.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    projects = []
    seen_links = set()

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
            if votes_tag:
                votes_text = votes_tag.get_text(strip=True)
                votes_num = int("".join(filter(str.isdigit, votes_text)))
            else:
                votes_num = 0

            projects.append({
                "Название проекта": title,
                "Ссылка на проект": full_link,
                "Количество голосов": votes_num
            })

            time.sleep(0.25)
        except Exception as e:
            print(f"Ошибка при обработке {full_link}: {e}")

    session.close()
    df = pd.DataFrame(projects)
    df = df.sort_values(by="Количество голосов", ascending=False).reset_index(drop=True)
    return df

# --- Сохранение истории ---
def save_history(df):
    df = df.copy()
    df["Дата"] = date.today().isoformat()

    if not os.path.exists(HISTORY_FILE):
        df.to_excel(HISTORY_FILE, index=False)
    else:
        old_df = pd.read_excel(HISTORY_FILE)
        combined = pd.concat([old_df, df], ignore_index=True)
        combined.to_excel(HISTORY_FILE, index=False)

# --- Подсчёт разницы голосов ---
def get_daily_diff(df_today: pd.DataFrame):
    if not os.path.exists(HISTORY_FILE):
        df_today["Изменение голосов"] = 0
        return df_today

    df_old = pd.read_excel(HISTORY_FILE)
    if "Ссылка на проект" not in df_old.columns or "Количество голосов" not in df_old.columns:
        df_today["Изменение голосов"] = 0
        return df_today

    df_today["Ссылка на проект"] = df_today["Ссылка на проект"].astype(str)
    df_old["Ссылка на проект"] = df_old["Ссылка на проект"].astype(str)

    merged = pd.merge(
        df_today,
        df_old[["Ссылка на проект", "Количество голосов"]],
        on="Ссылка на проект",
        how="left",
        suffixes=("", "_вчера")
    )

    merged["Изменение голосов"] = (
        merged["Количество голосов"] - merged["Количество голосов_вчера"].fillna(0)
    )

    merged["Дата обновления"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return merged

# --- Отображение таблицы ---
def display_table(df, top_n=None):
    df_display = df.copy()
    df_display["Ссылка на проект"] = df_display["Ссылка на проект"].apply(
        lambda x: f"<a href='{x}' target='_blank'>Ссылка</a>"
    )
    if top_n:
        df_display = df_display.head(top_n)
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# --- Интерфейс Streamlit ---
if st.button("🔄 Обновить данные с сайта"):
    with st.spinner("Загрузка данных..."):
        df_today = get_projects_info()
        df_today = get_daily_diff(df_today)
        save_history(df_today)
        st.session_state["df_today"] = df_today
    st.success(f"✅ Загружено {len(df_today)} проектов.")

df_today = st.session_state.get("df_today", pd.DataFrame())

if not df_today.empty:
    st.subheader("🔍 Поиск проектов")
    search_query = st.text_input("Введите часть названия").strip().lower()

    if search_query:
        df_filtered = df_today[df_today["Название проекта"].str.lower().str.contains(search_query, na=False)]
    else:
        df_filtered = df_today

    st.markdown("### 🏆 Топ-10 проектов")
    display_table(df_today.sort_values(by="Количество голосов", ascending=False), top_n=10)

    st.markdown("### 📋 Все проекты")
    display_table(df_filtered)
else:
    st.info("Нажмите кнопку, чтобы загрузить список проектов 🚀")
