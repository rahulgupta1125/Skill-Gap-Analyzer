import os
from datetime import date, datetime
from io import BytesIO

import streamlit as st
import PyPDF2
import docx
import google.generativeai as genai
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------------
# 1. Configure Gemini 2.0 Flash
# ------------------------------
# Replace with your actual Gemini API key:
GENIE_API_KEY    = "AIzaSyAgPuzZoBVz07-wv5kh9iIY1OX5tU6lG8w"
# If your account requires a server/organization key, place it here:
GENIE_SERVER_KEY = "30fba82b3a2ff67256ad2c4aece6d6ff76ea8cc8"

genai.configure(api_key=GENIE_API_KEY)
os.environ["GOOGLE_API_ORGANIZATION"] = GENIE_SERVER_KEY  # only needed if your account requires it

if not GENIE_API_KEY:
    st.error("🚨 Please set your Gemini API key (GENIE_API_KEY).")
    st.stop()

GEMINI_MODEL = "gemini-2.0-flash"

# --------------------------------
# 2. Streamlit App UI Definition
# --------------------------------
st.set_page_config(page_title="Skill-Gap Analyzer", layout="wide")
st.title("🛠 Personalized Skill-Gap Analyzer & Planner")

st.markdown(
    """
Use the **sidebar** to specify:
1. **Target Role Title**  
2. **Required Skills** (comma-separated)  
3. **Deadline** (date by which you need to be ready)  
4. Upload your **Résumé** (PDF, DOCX, or TXT) or paste it manually below.

Click **Generate Skill-Gap Report**.  
Gemini 2.0 Flash will output labeled plain-text sections that we display under each heading.
"""
)

# ------------------------------
# 3. Sidebar Inputs
# ------------------------------
with st.sidebar:
    st.header("📝 Inputs")

    target_role = st.text_input(
        "Target Role Title", placeholder="e.g. Data Scientist"
    )

    required_skills_txt = st.text_area(
        "Required Skills (comma-separated)",
        placeholder="e.g. python, sql, machine learning, pandas"
    )

    deadline = st.date_input(
        "Deadline (Be Ready By)",
        min_value=date.today(),
        max_value=date.today().replace(year=date.today().year + 1),
    )

    st.markdown("---")
    st.write("📂 Upload Résumé (PDF / DOCX / TXT) or skip to paste text manually:")
    uploaded_file = st.file_uploader("Choose file", type=["pdf", "docx", "txt"])
    st.markdown("---")
    generate_button = st.button("Generate Skill-Gap Report")

# If no file, allow manual paste:
if not uploaded_file:
    st.markdown("---")
    manual_text = st.text_area(
        "✍ Paste Résumé Text Below (if no file uploaded)",
        height=200,
        placeholder="Paste your résumé text here if you didn’t upload a file."
    )
    st.session_state["manual_text"] = manual_text

# ------------------------------
# 4. Helper: Extract Text from File
# ------------------------------
def extract_text_from_file(uploaded_file) -> str:
    """
    Read text from a Streamlit UploadedFile (PDF, DOCX, or TXT).
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(BytesIO(raw))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text
    elif name.endswith(".docx"):
        document = docx.Document(BytesIO(raw))
        return "\n".join(para.text for para in document.paragraphs)
    elif name.endswith(".txt"):
        return raw.decode("utf-8", errors="ignore")
    return ""

# ------------------------------
# 5. Main Logic: On Button Click
# ------------------------------
if generate_button:
    # 5A) Basic validation
    if not target_role.strip():
        st.error("❗ Please enter a target role title.")
    elif not required_skills_txt.strip():
        st.error("❗ Please list required skills (comma-separated).")
    elif not uploaded_file and not st.session_state.get("manual_text", "").strip():
        st.error("❗ Please upload a résumé file or paste résumé text manually.")
    elif deadline < date.today():
        st.error("❗ Deadline must be today or later.")
    else:
        # 5B) Extract résumé text
        if uploaded_file:
            résumé_text = extract_text_from_file(uploaded_file)
        else:
            résumé_text = st.session_state.get("manual_text", "").strip()

        if not résumé_text:
            st.error("⚠️ No résumé text found. Upload or paste text manually.")
        else:
            st.subheader("📄 Résumé Excerpt")
            st.write(résumé_text[:500] + " …")  # Show first 500 characters

            # 5C) Build a plain-text prompt that asks for labeled sections
            today_str = date.today().strftime("%Y-%m-%d")
            deadline_str = deadline.strftime("%Y-%m-%d")

            prompt = f"""
You are an educational AI assistant.  

The user wants to apply for a role, and you must output the following exactly as labeled plain‐text sections with no additional commentary:

Here is the résumé text (between triple quotes):
\"\"\"
{résumé_text}
\"\"\"

Target role title: "{target_role}"

Required skills for that role (comma-separated): {required_skills_txt}

Today’s date is {today_str}. The user needs to be ready by {deadline_str} (inclusive).

Please output exactly these five headings, each on its own line, followed by bullet points or numbered lists:

Current Skills:
• List each skill you detect in the résumé (lowercase), one per line, preceding each with “• ”.

Missing Skills:
• List each required skill not found in the résumé (lowercase), one per line, preceding each with “• ”.

Modules:
1. Python Basics
2. SQL Essentials
3. Pandas for Data Analysis
4. Statistics Primer
5. Linear Regression
6. Logistic Regression
7. TensorFlow Basics
8. PyTorch Introduction
9. Model Deployment
10. Git & GitHub
11. Docker Basics
12. Soft Skills & Interview Prep

Order them so prerequisites come first, using this graph:
• Python Basics → SQL Essentials → Pandas for Data Analysis
• Statistics Primer → Linear Regression
• Statistics Primer → Logistic Regression
• Linear Regression → TensorFlow Basics
• Linear Regression → PyTorch Introduction
• TensorFlow Basics & PyTorch Introduction → Model Deployment
• Git & GitHub → Docker Basics
• Soft Skills & Interview Prep (no prerequisites)

Timetable:
• Assign exactly one module per calendar day from {today_str} through {deadline_str}. If modules > days, put extras on {deadline_str}. Output as “YYYY-MM-DD: Module Name”, one per line.

Motivation:
Write a 3–4 sentence motivating paragraph explaining why this path prepares the user for the target role.
"""
            # 5D) Call Gemini 2.0 Flash
            with st.spinner("⏳ Querying Gemini 2.0 Flash…"):
                try:
                    model = genai.GenerativeModel(GEMINI_MODEL)
                    generation_config = {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_output_tokens": 800,
                    }
                    resp = model.generate_content(prompt, generation_config=generation_config)
                    output_text = resp.text.strip()
                except Exception as e:
                    st.error(f"🔴 Gemini error: {e}")
                    st.stop()

            # 5E) Split into labeled sections
            sections = {
                "Current Skills:": [],
                "Missing Skills:": [],
                "Modules:": [],
                "Timetable:": [],
                "Motivation:": []
            }
            current_label = None
            for line in output_text.splitlines():
                line = line.rstrip()
                if line in sections:
                    current_label = line
                    continue
                if current_label:
                    sections[current_label].append(line)

            # 5F) Render each section under its emoji‐headed heading

            # 🔍 Current Skills
            st.markdown("### 🔍 Current Skills")
            if sections["Current Skills:"]:
                for item in sections["Current Skills:"]:
                    st.markdown(f"- {item.strip()}")
            else:
                st.markdown("_None found._")

            # ❌ Missing Skills
            st.markdown("### ❌ Missing Skills")
            if sections["Missing Skills:"]:
                for item in sections["Missing Skills:"]:
                    st.markdown(f"- {item.strip()}")
            else:
                st.markdown("_None missing—congratulations!_")

            # 📚 Recommended Modules (Ordered)
            st.markdown("### 📚 Recommended Modules (Ordered)")
            if sections["Modules:"]:
                for item in sections["Modules:"]:
                    # The "Modules:" lines (Gemini will number them)
                    st.markdown(f"{item.strip()}")
            else:
                st.markdown("_No modules recommended._")

            # 🗓️ Day-by-Day Timetable
            st.markdown("### 🗓️ Day-by-Day Timetable")
            if sections["Timetable:"]:
                for item in sections["Timetable:"]:
                    st.markdown(f"- {item.strip()}")
            else:
                st.markdown("_No timetable generated._")

            # 💡 Motivation
            st.markdown("### 💡 Motivation")
            if sections["Motivation:"] and any(line.strip() for line in sections["Motivation:"]):
            # Join Gemini‐returned lines, but also capitalize the very first character
                raw_motivation = " ".join(line.strip() for line in sections["Motivation:"])
                st.markdown(raw_motivation[0].upper() + raw_motivation[1:])
                motivation_paragraph = raw_motivation[0].upper() + raw_motivation[1:]
            else:
    # Fallback: a brief, “firing” motivational paragraph
                fallback = (
        "This is your moment—start now and seize the opportunity! "
        "With dedication, each module you tackle brings you closer to your dream Data Scientist role. "
        "Dive in headfirst, master these skills, and build the confidence to shine in interviews. "
        "Your future team is waiting—make today count!"
    )
            st.markdown(fallback)
            motivation_paragraph = fallback
            # 5G) Build PDF report with the same sections
            tmp_dir = "tmp_reports"
            os.makedirs(tmp_dir, exist_ok=True)
            filename = (
                f"SkillGap_{os.path.splitext(uploaded_file.name if uploaded_file else 'manual')[0]}_"
                f"{datetime.now().strftime('%Y%m%d')}.pdf"
            )
            pdf_path = os.path.join(tmp_dir, filename)

            def build_pdf():
                doc = SimpleDocTemplate(pdf_path, pagesize=LETTER)
                styles = getSampleStyleSheet()
                story = []

                # Title
                title_style = ParagraphStyle(
                    name="TitleStyle",
                    fontSize=16,
                    leading=20,
                    alignment=1,  # center
                    spaceAfter=12
                )
                story.append(Paragraph("Skill-Gap & Planner Report", title_style))
                story.append(Spacer(1, 8))

                # 1) Current Skills
                story.append(Paragraph("<b>1. Current Skills:</b>", styles["Heading2"]))
                if sections["Current Skills:"]:
                    for line in sections["Current Skills:"]:
                        story.append(Paragraph(line, styles["Normal"]))
                else:
                    story.append(Paragraph("None found.", styles["Normal"]))
                story.append(Spacer(1, 8))

                # 2) Missing Skills
                story.append(Paragraph("<b>2. Missing Skills:</b>", styles["Heading2"]))
                if sections["Missing Skills:"]:
                    for line in sections["Missing Skills:"]:
                        story.append(Paragraph(line, styles["Normal"]))
                else:
                    story.append(Paragraph("None missing.", styles["Normal"]))
                story.append(Spacer(1, 8))

                # 3) Recommended Modules
                story.append(Paragraph("<b>3. Recommended Modules:</b>", styles["Heading2"]))
                if sections["Modules:"]:
                    for line in sections["Modules:"]:
                        story.append(Paragraph(line, styles["Normal"]))
                else:
                    story.append(Paragraph("No modules recommended.", styles["Normal"]))
                story.append(Spacer(1, 8))

                # 4) Day-by-Day Timetable
                story.append(Paragraph("<b>4. Day-by-Day Timetable:</b>", styles["Heading2"]))
                if sections["Timetable:"]:
                    for line in sections["Timetable:"]:
                        story.append(Paragraph(line, styles["Normal"]))
                else:
                    story.append(Paragraph("No timetable generated.", styles["Normal"]))
                story.append(Spacer(1, 8))

                # 5) Motivation
                story.append(Paragraph("<b>5. Motivation:</b>", styles["Heading2"]))
                if sections["Motivation:"]:
                    story.append(Paragraph(motivation_paragraph, styles["Normal"]))
                else:
                    story.append(Paragraph("No motivational paragraph provided.", styles["Normal"]))

                doc.build(story)

            with st.spinner("📄 Generating PDF…"):
                build_pdf()

            # 5H) Provide Download button
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="📥 Download PDF Report",
                    data=f,
                    file_name=filename,
                    mime="application/pdf"
                )

# --------------------------------
# 6. If not clicked yet, show info
# --------------------------------
elif not generate_button:
    st.info(
        "🔹 Fill in the sidebar fields (Target Role, Required Skills, Deadline), "
        "upload/paste résumé text, then click **Generate Skill-Gap Report**."
    )
