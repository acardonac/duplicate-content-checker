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
    d = difflib.HtmlDiff(wrapcolumn=80)
    html_table = d.make_table(text1.split(), text2.split(), context=True, numlines=2)
    styled_html = f"""
    <style>
    table {{
        width: 100%;
        border-collapse: collapse;
        font-family: Arial, sans-serif;
        font-size: 14px;
    }}
    th, td {{
        padding: 8px;
        text-align: left;
        border: 1px solid #ccc;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    tr:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    .diff_add {{ background-color: #d4f7dc; }}
    .diff_chg {{ background-color: #fff3cd; }}
    .diff_sub {{ background-color: #f8d7da; }}
    </style>
    {html_table}
    """
    return styled_html

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
st.set_page_config(page_title="Duplicate Content Checker", layout="wide")
st.sidebar.title("🔍 Duplicate Content Checker")
st.sidebar.write("Compare content across webpages and export duplicate findings.")

page = st.sidebar.radio("Navigate", ["Input & Analysis", "📊 Report Viewer"])

if page == "Input & Analysis":
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

            st.session_state['comparison_results'] = []

            for i in range(len(urls)):
                for j in range(i + 1, len(urls)):
                    sim_score = similarity_matrix[i][j]
                    diff_html = highlight_diff(texts[i], texts[j])
                    seq_matcher = difflib.SequenceMatcher(None, texts[i], texts[j])
                    matching_blocks = seq_matcher.get_matching_blocks()
                    matched_content = [texts[i][block.a:block.a + block.size] for block in matching_blocks if block.size > 30]
                    matched_text = "\n\n".join([f"...{chunk.strip()}..." for chunk in matched_content if chunk.strip()])

                    st.session_state['comparison_results'].append({
                        "URL 1": urls[i],
                        "URL 2": urls[j],
                        "Similarity Score": round(sim_score, 4),
                        "Highlighted Duplicate Phrases": matched_text,
                        "Diff HTML": diff_html
                    })

            st.success("✅ Content comparison complete. View the results in the Report Viewer tab.")

elif page == "📊 Report Viewer":
    if 'comparison_results' in st.session_state and st.session_state['comparison_results']:
        st.header("📊 Comparison Report")
        for result in st.session_state['comparison_results']:
            with st.expander(f"{result['URL 1']} ↔ {result['URL 2']} (Score: {result['Similarity Score']})"):
                st.markdown("### Highlighted Duplicate Phrases")
                st.code(result['Highlighted Duplicate Phrases'], language='text')
                st.markdown("### Side-by-Side Diff Viewer")
                st.components.v1.html(result['Diff HTML'], height=500, scrolling=True)

        export_df = pd.DataFrame([{
            "URL 1": r["URL 1"],
            "URL 2": r["URL 2"],
            "Similarity Score": r["Similarity Score"],
            "Highlighted Duplicate Phrases": r["Highlighted Duplicate Phrases"]
        } for r in st.session_state['comparison_results']])

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, index=False, sheet_name='Duplicates')
        st.download_button(
            label="📥 Download Duplicates Excel Report",
            data=buffer.getvalue(),
            file_name="duplicate_content_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No comparison results available yet. Go to 'Input & Analysis' to start.")

st.markdown("---")
st.caption("Built with ❤️ using Streamlit and NLP. Coming soon: multilingual support + AI paraphrase detection!")
