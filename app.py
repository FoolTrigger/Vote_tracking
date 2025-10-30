import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import streamlit as st

st.set_page_config(page_title="Мониторинг проектов vam.golosza.ru", layout="wide")
st.title("📊 Мониторинг проектов vam.golosza.ru")

BASE_URL = "https://vam.golosza.ru/vote/list?page=&mo-search=бор&filter%5Baddress%5D%5B%5D=1&search=undefined"
PROJECT_BASE = "https://vam.golosza.ru/vote/"

@st.cache_data(ttl=600)
def get_projects_info():
    session = requests.Session()  # Используем одну сессию
    response = session.get(BASE_URL, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # Получаем ссылки на проекты
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

        try:
            project_response = session.get(link, timeout=10)
            project_soup = BeautifulSoup(project_response.text, "html.parser")

            title_tag = project_soup.find("p", class_="title")
            title = title_tag.text.strip() if title_tag else "Без названия"

            votes_tag = project_soup.find("div", class_="took-part-banner_count")
            votes = int(re.findall(r'\d+', votes_tag.text)[0]) if votes_tag and re.findall(r'\d+', votes_tag.text) else 0

            projects.append({
                "Название проекта": title,
                "Ссылка на проект": link,
                "Количество голосов": votes
            })

            time.sleep(0.2)  # небольшая задержка

        except Exception as e:
            print(f"Ошибка при обработке {link}: {e}")
            continue

    session.close()

    df = pd.DataFrame(projects)
    if not df.empty:
        df = df.sort_values(by="Количество голосов", ascending=False).reset_index(drop=True)
        df.index += 1
        df.index.name = "№"
    return df

def display_table(df, top_n=None):
    df_display = df.copy()
    df_display["Ссылка на проект"] = df_display["Ссылка на проект"].apply(
        lambda x: f"<a href='{x}' target='_blank'>Ссылка</a>"
    )
    if top_n:
        df_display = df_display.head(top_n)
    st.write(df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

# --- Streamlit интерфейс ---
if st.button("🔄 Обновить данные с сайта"):
    df_projects = get_projects_info()
    st.session_state["df_projects"] = df_projects
    st.success(f"Загружено {len(df_projects)} проектов.")

df_projects = st.session_state.get("df_projects", pd.DataFrame())

if not df_projects.empty:
    st.subheader("🔥 Топ-10 проектов по голосам")
    display_table(df_projects, top_n=10)

    st.subheader("📋 Все проекты")
    display_table(df_projects)
else:
    st.info("Нажми кнопку, чтобы загрузить список проектов 🚀")
