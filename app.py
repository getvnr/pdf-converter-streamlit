import streamlit as st
import PyPDF2
import pdfplumber
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from io import BytesIO
import zipfile
import base64

# Page range parser (for other features)
def parse_page_range(page_str, max_pages):
    pages = set()
    if not page_str:
        return list(range(max_pages))
    for part in page_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            for i in range(max(start, 1), min(end, max_pages) + 1):
                pages.add(i - 1)
        else:
            num = int(part)
            if 1 <= num <= max_pages:
                pages.add(num - 1)
    return sorted(pages)

# Helper to generate and encode thumbnails with error handling
def generate_thumbnails(pdf_file):
    try:
        pdf_bytes = pdf_file.read()
        images = convert_from_bytes(pdf_bytes, size=(195, None))  # 30% larger: 150px * 1.3 = 195px
        thumbnails = []
        for img in images:
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            thumbnails.append(img_str)
        return thumbnails, None
    except PDFPageCountError as e:
        return [], f"Error: Unable to process {pdf_file.name}. The PDF may be corrupted or invalid. Details: {str(e)}"
    except PDFSyntaxError:
        return [], f"Error: {pdf_file.name} has invalid PDF syntax. Please upload a valid PDF."
    except Exception as e:
        return [], f"Error processing {pdf_file.name}: {str(e)}"

# Sidebar for navigation
st.sidebar.title("PDF Converter")
page = st.sidebar.selectbox("Choose a tool:", [
    "Merge PDFs", "Split PDF", "PDF to PNG", "PDF to Text",
    "Image to PDF", "Text to PDF"
])

if page == "Merge PDFs":
    st.header("Merge PDFs with Page Selection")
    uploaded_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type="pdf")
    
    if uploaded_files:
        st.subheader("Select Pages to Merge")
        selected_pages = {}
        valid_files = True
        
        # Display thumbnails and checkboxes for each PDF
        for idx, pdf_file in enumerate(uploaded_files):
            st.write(f"**File: {pdf_file.name}**")
            try:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                pdf_file.seek(0)  # Reset file pointer for thumbnail generation
                thumbnails, error = generate_thumbnails(pdf_file)
                
                if error:
                    st.error(error)
                    valid_files = False
                    continue
                
                # Create a grid of thumbnails with checkboxes
                cols_per_row = 4
                for i in range(0, num_pages, cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        page_idx = i + j
                        if page_idx < num_pages:
                            with cols[j]:
                                st.image(f"data:image/png;base64,{thumbnails[page_idx]}", caption=f"Page {page_idx + 1}")
                                is_selected = st.checkbox(f"Include Page {page_idx + 1}", key=f"page_{idx}_{page_idx}")
                                selected_pages.setdefault(idx, []).append(is_selected)
            except PyPDF2.errors.PdfReadError:
                st.error(f"Error: {pdf_file.name} is encrypted or corrupted. Please upload a valid PDF.")
                valid_files = False
                continue
        
        if st.button("Merge Selected Pages") and valid_files:
            if not any(sum(pages) > 0 for pages in selected_pages.values()):
                st.error("Please select at least one page to merge!")
            else:
                merged_pdf = PyPDF2.PdfWriter()
                for file_idx, pdf_file in enumerate(uploaded_files):
                    try:
                        pdf_file.seek(0)  # Reset file pointer
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        for page_idx, is_selected in enumerate(selected_pages.get(file_idx, [])):
                            if is_selected:
                                merged_pdf.add_page(pdf_reader.pages[page_idx])
                    except PyPDF2.errors.PdfReadError:
                        st.error(f"Error: {pdf_file.name} could not be merged (possibly encrypted or corrupted).")
                        valid_files = False
                
                if valid_files and merged_pdf.pages:
                    output = BytesIO()
                    merged_pdf.write(output)
                    st.download_button(
                        "Download Merged PDF",
                        output.getvalue(),
                        "merged.pdf",
                        "application/pdf"
                    )
                else:
                    st.error("No valid pages were merged. Please check your selections and files.")

elif page == "Split PDF":
    st.header("Split PDF into Pages")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    
    if uploaded_file:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            num_pages = len(pdf_reader.pages)
            uploaded_file.seek(0)  # Reset for thumbnails
            thumbnails, error = generate_thumbnails(uploaded_file)
            
            if error:
                st.error(error)
            else:
                st.subheader("Page Previews")
                cols_per_row = 4
                for i in range(0, num_pages, cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        page_idx = i + j
                        if page_idx < num_pages:
                            with cols[j]:
                                st.image(f"data:image/png;base64,{thumbnails[page_idx]}", caption=f"Page {page_idx + 1}")
            
            if st.button("Split"):
                for i, page in enumerate(pdf_reader.pages):
                    split_pdf = PyPDF2.PdfWriter()
                    split_pdf.add_page(page)
                    output = BytesIO()
                    split_pdf.write(output)
                    st.download_button(f"Download Page {i+1}", output.getvalue(), f"page-{i+1}.pdf", "application/pdf")
        except PyPDF2.errors.PdfReadError:
            st.error("Error: The uploaded PDF is encrypted or corrupted. Please upload a valid PDF.")

elif page == "PDF to PNG":
    st.header("PDF to PNG Images")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    page_range = st.text_input("Page range (e.g., 1-3,5)", placeholder="All pages")
    
    if uploaded_file:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            num_pages = len(pdf_reader.pages)
            pages_to_convert = parse_page_range(page_range, num_pages)
            uploaded_file.seek(0)  # Reset for thumbnails
            thumbnails, error = generate_thumbnails(uploaded_file)
            
            if error:
                st.error(error)
            else:
                st.subheader("Selected Page Previews")
                cols_per_row = 4
                for i in range(0, len(pages_to_convert), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        page_idx = i + j
                        if page_idx < len(pages_to_convert):
                            with cols[j]:
                                st.image(f"data:image/png;base64,{thumbnails[pages_to_convert[page_idx]]}", 
                                         caption=f"Page {pages_to_convert[page_idx] + 1}")
            
            if st.button("Convert to PNG"):
                pdf_bytes = uploaded_file.read()
                images = convert_from_bytes(pdf_bytes, first_page=min(pages_to_convert)+1, last_page=max(pages_to_convert)+1)
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    for idx, img in enumerate(images):
                        img_buffer = BytesIO()
                        img.save(img_buffer, format='PNG')
                        zip_file.writestr(f"page-{pages_to_convert[idx]+1}.png", img_buffer.getvalue())
                
                st.download_button("Download ZIP of PNGs", zip_buffer.getvalue(), "pdf-to-png.zip", "application/zip")
        except (PDFPageCountError, PDFSyntaxError) as e:
            st.error(f"Error converting PDF to PNG: {str(e)}. The PDF may be corrupted or invalid.")
        except PyPDF2.errors.PdfReadError:
            st.error("Error: The uploaded PDF is encrypted or corrupted. Please upload a valid PDF.")

elif page == "PDF to Text":
    st.header("PDF to Text")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    page_range = st.text_input("Page range (e.g., 1-3,5)", placeholder="All pages")
    
    if uploaded_file:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            num_pages = len(pdf_reader.pages)
            pages_to_extract = parse_page_range(page_range, num_pages)
            uploaded_file.seek(0)  # Reset for thumbnails
            thumbnails, error = generate_thumbnails(uploaded_file)
            
            if error:
                st.error(error)
            else:
                st.subheader("Selected Page Previews")
                cols_per_row = 4
                for i in range(0, len(pages_to_extract), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        page_idx = i + j
                        if page_idx < len(pages_to_extract):
                            with cols[j]:
                                st.image(f"data:image/png;base64,{thumbnails[pages_to_extract[page_idx]]}", 
                                         caption=f"Page {pages_to_extract[page_idx] + 1}")
            
            if st.button("Extract Text"):
                with pdfplumber.open(uploaded_file) as pdf:
                    full_text = ""
                    for page_num in pages_to_extract:
                        page = pdf.pages[page_num]
                        full_text += f"--- Page {page_num + 1} ---\n{page.extract_text()}\n\n"
                
                st.download_button("Download Text File", full_text, "extracted-text.txt", "text/plain")
                st.text_area("Preview", full_text, height=200)
        except PyPDF2.errors.PdfReadError:
            st.error("Error: The uploaded PDF is encrypted or corrupted. Please upload a valid PDF.")
        except Exception as e:
            st.error(f"Error extracting text: {str(e)}. The PDF may be corrupted or encrypted.")

elif page == "Image to PDF":
    st.header("Image(s) to PDF")
    uploaded_files = st.file_uploader("Upload Images", accept_multiple_files=True, type=["png", "jpg", "jpeg"])
    
    if st.button("Convert to PDF") and uploaded_files:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        width, height = letter
        for img_file in uploaded_files:
            try:
                img = Image.open(img_file)
                img_width, img_height = img.size
                scale = min(width / img_width, height / img_height)
                can.drawImage(ImageReader(img_file), 0, 0, width=img_width * scale, height=img_height * scale)
                can.showPage()
            except Exception as e:
                st.error(f"Error processing image {img_file.name}: {str(e)}")
        can.save()
        packet.seek(0)
        st.download_button("Download PDF", packet.getvalue(), "images-to-pdf.pdf", "application/pdf")

elif page == "Text to PDF":
    st.header("Text to PDF")
    text_input = st.text_area("Enter text", height=200)
    
    if st.button("Convert to PDF") and text_input:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawString(72, 750, text_input[:1000])  # Simple; truncate for demo
        can.save()
        packet.seek(0)
        st.download_button("Download PDF", packet.getvalue(), "text-to-pdf.pdf", "application/pdf")

st.sidebar.markdown("---")
st.sidebar.info("Built with Streamlit. Deployed on Streamlit Cloud.")
