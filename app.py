import streamlit as st
import requests
from bs4 import BeautifulSoup
from readability import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import re
import pandas as pd
import xml.etree.ElementTree as ET
import io

# --- Helper Functions ---
def clean_text(html):
    doc = Document(html)
    summary = doc.summary()
    soup = BeautifulSoup(summary, "html.parser")
    text = soup.get_text(separator=' ', strip=True)
    return re.sub(r'\s+', ' ', text.lower())

def fetch_content(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return clean_text(response.text)
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {e}"

def compare_texts(texts):
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(texts)
    similarity = cosine_similarity(tfidf_matrix)
    return similarity

def highlight_diff(text1, text2):
    d = difflib.HtmlDiff()
    return d.make_table(text1.split(), text2.split(), context=True, numlines=2)

def extract_urls_from_sitemap(sitemap_url, limit=5):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            tree = ET.fromstring(response.content)
            urls = [elem.text for elem in tree.iter() if 'loc' in elem.tag]
            return urls[:limit]
        else:
            return []
    except Exception as e:
        return []

# --- Streamlit App ---
st.title("🔍 Duplicate Content Checker")

st.write("You can enter a sitemap URL or manually input individual URLs to compare their content.")

use_sitemap = st.checkbox("Use Sitemap.xml to load URLs")
urls = []

if use_sitemap:
    sitemap_url = st.text_input("Sitemap URL")
    if sitemap_url:
        urls = extract_urls_from_sitemap(sitemap_url)
        st.success(f"Loaded {len(urls)} URLs from sitemap.")
else:
    url_inputs = [st.text_input(f"URL {i+1}") for i in range(5)]
    urls = [url for url in url_inputs if url]

if st.button("Compare Content"):
    if len(urls) < 2:
        st.warning("Please enter at least two URLs.")
    else:
        with st.spinner("Fetching and comparing content..."):
            texts = [fetch_content(url) for url in urls]
            similarity_matrix = compare_texts(texts)
            df = pd.DataFrame(similarity_matrix, index=urls, columns=urls)

        st.subheader("🔗 Similarity Matrix")
        st.dataframe(df.style.background_gradient(cmap='YlOrRd'))

        threshold = 0.8
        st.subheader(f"🧬 Pairs with Similarity > {threshold}")

        # Collect data for export
        export_rows = []

        for i in range(len(urls)):
            for j in range(i + 1, len(urls)):
                sim_score = similarity_matrix[i][j]
                if sim_score >= threshold:
                    st.markdown(f"**{urls[i]} ↔ {urls[j]}**")
                    diff_html = highlight_diff(texts[i], texts[j])
                    st.components.v1.html(diff_html, height=400, scrolling=True)

                    # Find overlapping phrases
                    seq_matcher = difflib.SequenceMatcher(None, texts[i], texts[j])
                    matching_blocks = seq_matcher.get_matching_blocks()
                    matched_content = " ".join([texts[i][block.a:block.a + block.size] for block in matching_blocks if block.size > 50])

                    export_rows.append({
                        "URL 1": urls[i],
                        "URL 2": urls[j],
                        "Similarity Score": round(sim_score, 4),
                        "Duplicated Content": matched_content
                    })

        # Export button
        if export_rows:
            export_df = pd.DataFrame(export_rows)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Duplicates')
            st.download_button(
                label="📥 Download Duplicates Excel Report",
                data=buffer.getvalue(),
                file_name="duplicate_content_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

st.markdown("---")
st.caption("Built with ❤️ using Streamlit and NLP")
