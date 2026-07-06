import streamlit as st
from seo_scan import normalize_url, analyze, score_and_grade, build_html_report, SHOPIFY_TIPS
import requests

st.set_page_config(page_title="SiteScan — SEO Diagnostic", page_icon="🔎", layout="centered")

st.markdown("""
<style>
.stApp { background:#101218; color:#EDEAE0; }
div[data-testid="stMetricValue"] { font-family: monospace; }
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;margin-right:8px;}
.badge.pass{background:#132622;color:#3fbf8f;}
.badge.warning{background:#2a2116;color:#e3a23c;}
.badge.critical{background:#2c1917;color:#e15b4f;}
.row{padding:8px 0;border-bottom:1px solid #21252d;}
.lbl{font-weight:600;}
.det{color:#9096a3;font-size:13px;margin-top:2px;}
.fix{color:#c9d0e0;font-size:12.5px;margin-top:6px;background:#1d2129;padding:7px 10px;border-left:2px solid #5b8cff;}
.mcard{border:1px solid #2a2f39;border-radius:8px;padding:12px 16px;margin-bottom:10px;}
.mcard.critical{border-left:3px solid #e15b4f;}
.mcard.warning{border-left:3px solid #e3a23c;}
.shopify{font-size:12px;color:#5b6170;margin-top:6px;}
</style>
""", unsafe_allow_html=True)

st.title("🔎 SiteScan — Automatic SEO Diagnostic")
st.caption("Domain daalo, on-page + technical SEO ka poora live scan mil jayega, mistakes aur fix guide ke saath.")

domain = st.text_input("Domain", placeholder="e.g. drivestylish.com")
run = st.button("Run scan", type="primary")

if run:
    url = normalize_url(domain)
    if not url:
        st.error("Valid domain daalo — e.g. drivestylish.com ya https://drivestylish.com")
    else:
        with st.spinner(f"Scanning {url} ..."):
            try:
                onpage, tech, is_shopify, final_url = analyze(url)
            except requests.exceptions.RequestException as e:
                st.error(f"Couldn't fetch this page: {e}")
                st.stop()

        score, grade, crit, warn, passed = score_and_grade(onpage, tech)
        color = "#3fbf8f" if score >= 65 else ("#e3a23c" if score >= 45 else "#e15b4f")

        st.markdown(f"### {final_url}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score", f"{score}/100")
        c2.metric("Critical", crit)
        c3.metric("Warnings", warn)
        c4.metric("Passed", passed)
        st.markdown(f"<div style='color:{color};font-weight:600'>{grade}</div>", unsafe_allow_html=True)

        def render_rows(checks):
            for c in checks:
                fix_html = f'<div class="fix">Fix: {c["fix"]}</div>' if c.get("fix") else ""
                st.markdown(
                    f'<div class="row"><span class="badge {c["status"]}">{c["status"].upper()}</span>'
                    f'<span class="lbl">{c["label"]}</span><div class="det">{c["detail"]}</div>{fix_html}</div>',
                    unsafe_allow_html=True
                )

        st.markdown("---")
        st.subheader("On-page SEO")
        render_rows(onpage)

        st.markdown("---")
        st.subheader("Technical SEO")
        render_rows(tech)

        st.markdown("---")
        st.subheader("Mistakes & fix guide")
        mistakes = [c for c in (onpage + tech) if c["status"] != "pass"]
        mistakes.sort(key=lambda c: 0 if c["status"] == "critical" else 1)
        if not mistakes:
            st.success("No major mistakes found in this scan.")
        else:
            for c in mistakes:
                tip = f'<div class="shopify">Shopify tip: {SHOPIFY_TIPS[c["label"]]}</div>' if is_shopify and c["label"] in SHOPIFY_TIPS else ""
                st.markdown(
                    f'<div class="mcard {c["status"]}"><span class="badge {c["status"]}">{c["status"].upper()}</span>'
                    f'<b>{c["label"]}</b><ol style="color:#9096a3;font-size:13px"><li>{c["detail"]}</li><li>{c["fix"]}</li></ol>{tip}</div>',
                    unsafe_allow_html=True
                )

        html_report = build_html_report(final_url, onpage, tech, is_shopify)
        st.download_button(
            "Download HTML report",
            data=html_report,
            file_name=f"seo_report_{final_url.split('//')[-1].split('/')[0].replace('.', '_')}.html",
            mime="text/html"
        )
