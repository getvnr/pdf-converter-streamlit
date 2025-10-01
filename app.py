import streamlit as st
import PyPDF2
import pdfplumber
from pdf2image import convert_from_bytes
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfutils
from reportlab.lib.utils import ImageReader
from io import BytesIO
import zipfile
import os

# Page range parser (adapted from your JS)
def parse_page_range(page_str, max_pages):
    pages = set()
    if not page_str:
        return list(range(max_pages))
    for part in page_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            for i in range(max(start, 1), min(end, max_pages) + 1):
                pages.add(i - 1)  # 0-based for PyPDF2
        else:
            num = int(part)
            if 1 <= num <= max_pages:
                pages.add(num - 1)
    return sorted(pages)

# Sidebar for navigation
st.sidebar.title("PDF Converter")
page = st.sidebar.selectbox("Choose a tool:", [
    "Merge PDFs", "Split PDF", "PDF to PNG", "PDF to Text",
    "Image to PDF", "Text to PDF"
])

if page == "Merge PDFs":
    st.header("Merge PDFs (with optional page range)")
    uploaded_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type="pdf")
    page_range = st.text_input("Page range (e.g., 1-3,5)", placeholder="All pages")
    
    if st.button("Merge") and len(uploaded_files) >= 2:
        merged_pdf = PyPDF2.PdfWriter()
        for pdf_file in uploaded_files:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pages_to_copy = parse_page_range(page_range, len(pdf_reader.pages))
            for page_num in pages_to_copy:
                merged_pdf.add_page(pdf_reader.pages[page_num])
        
        output = BytesIO()
        merged_pdf.write(output)
        st.download_button("Download Merged PDF", output.getvalue(), "merged.pdf", "application/pdf")

elif page == "Split PDF":
    st.header("Split PDF into Pages")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    
    if st.button("Split") and uploaded_file:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        for i, page in enumerate(pdf_reader.pages):
            split_pdf = PyPDF2.PdfWriter()
            split_pdf.add_page(page)
            output = BytesIO()
            split_pdf.write(output)
            st.download_button(f"Download Page {i+1}", output.getvalue(), f"page-{i+1}.pdf", "application/pdf")

elif page == "PDF to PNG":
    st.header("PDF to PNG Images")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    page_range = st.text_input("Page range (e.g., 1-3,5)", placeholder="All pages")
    
    if st.button("Convert to PNG") and uploaded_file:
        pdf_bytes = uploaded_file.read()
        pages_to_convert = parse_page_range(page_range, len(PyPDF2.PdfReader(BytesIO(pdf_bytes)).pages))
        images = convert_from_bytes(pdf_bytes, first_page=min(pages_to_convert)+1, last_page=max(pages_to_convert)+1)
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for idx, img in enumerate(images):
                img_buffer = BytesIO()
                img.save(img_buffer, format='PNG')
                zip_file.writestr(f"page-{pages_to_convert[idx]+1}.png", img_buffer.getvalue())
        
        st.download_button("Download ZIP of PNGs", zip_buffer.getvalue(), "pdf-to-png.zip", "application/zip")

elif page == "PDF to Text":
    st.header("PDF to Text")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    page_range = st.text_input("Page range (e.g., 1-3,5)", placeholder="All pages")
    
    if st.button("Extract Text") and uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            pages_to_extract = parse_page_range(page_range, len(pdf.pages))
            full_text = ""
            for page_num in pages_to_extract:
                page = pdf.pages[page_num]
                full_text += f"--- Page {page_num + 1} ---\n{page.extract_text()}\n\n"
        
        st.download_button("Download Text File", full_text, "extracted-text.txt", "text/plain")
        st.text_area("Preview", full_text, height=200)

elif page == "Image to PDF":
    st.header("Image(s) to PDF")
    uploaded_files = st.file_uploader("Upload Images", accept_multiple_files=True, type=["png", "jpg", "jpeg"])
    
    if st.button("Convert to PDF") and uploaded_files:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter
        for img_file in uploaded_files:
            img = Image.open(img_file)
            img_width, img_height = img.size
            scale = min(width / img_width, height / img_height)
            can.drawImage(ImageReader(img_file), 0, 0, width=img_width * scale, height=img_height * scale)
            can.showPage()
        can.save()
        packet.seek(0)
        st.download_button("Download PDF", packet.getvalue(), "images-to-pdf.pdf", "application/pdf")

elif page == "Text to PDF":
    st.header("Text to PDF")
    text_input = st.text_area("Enter text", height=200)
    
    if st.button("Convert to PDF") and text_input:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawString(72, 750, text_input[:1000])  # Simple; truncate for demo (extend for multi-page)
        can.save()
        packet.seek(0)
        st.download_button("Download PDF", packet.getvalue(), "text-to-pdf.pdf", "application/pdf")

st.sidebar.markdown("---")
st.sidebar.info("Built with Streamlit. Deployed on Streamlit Cloud.")
