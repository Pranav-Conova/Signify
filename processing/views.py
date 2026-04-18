import os
import fitz  # PyMuPDF
import subprocess
import logging
from django.conf import settings
from django.shortcuts import render
from .forms import UploadFileForm
from .models import UploadedFile
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
import json
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
def save_gestures(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            request.session['gesture_config'] = data
            request.session.modified = True
            return JsonResponse({"message": "Gestures saved successfully!"})
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
    return JsonResponse({"error": "Invalid request"}, status=400)


def index(request):
    return render(request, "index.html")


def upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save()
            try:
                process_file(uploaded_file.file.path, uploaded_file.id)
                output_dir = os.path.join(
                    settings.MEDIA_ROOT, "uploads", str(uploaded_file.id)
                )
                request.session["presentation_file"] = output_dir
                return HttpResponseRedirect(reverse("index") + f"?file_id={uploaded_file.id}")
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                form.add_error(
                    None,
                    "An error occurred while processing the file. Please try again.",
                )
    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


def process_file(file_path, file_id):
    output_dir = os.path.join(settings.MEDIA_ROOT, "uploads", str(file_id))
    os.makedirs(output_dir, exist_ok=True)

    if file_path.lower().endswith(".pdf"):
        process_pdf(file_path, output_dir)
    elif file_path.lower().endswith((".ppt", ".pptx")):
        process_ppt(file_path, output_dir)
    else:
        logger.error(f"Unsupported file format: {file_path}")
        raise ValueError("Unsupported file format")


def process_pdf(file_path, output_dir):
    try:
        pdf_document = fitz.open(file_path)
        for page_number in range(len(pdf_document)):
            page = pdf_document.load_page(page_number)
            # Higher resolution for better slide quality
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_path = os.path.join(output_dir, f"slide_{page_number + 1}.png")
            pix.save(image_path)
            logger.info(f"Saved PDF page {page_number + 1} as {image_path}")
    except Exception as e:
        logger.error(f"An error occurred while processing PDF: {e}")
        raise


def process_ppt(file_path, output_dir):
    """Convert PPT/PPTX to images using LibreOffice (works on Linux/Render)."""
    try:
        # First convert PPTX to PDF using LibreOffice
        result = subprocess.run(
            [
                'libreoffice', '--headless', '--convert-to', 'pdf',
                '--outdir', output_dir, file_path
            ],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

        # Find the generated PDF
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Converted PDF not found at {pdf_path}")

        # Convert PDF pages to images
        process_pdf(pdf_path, output_dir)

        # Clean up the intermediate PDF
        os.remove(pdf_path)
        logger.info(f"Successfully converted PPT to slide images")

    except FileNotFoundError:
        logger.error(
            "LibreOffice not found. Install it with: apt-get install -y libreoffice"
        )
        raise
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out")
        raise
    except Exception as e:
        logger.error(f"An error occurred while converting PPT: {e}")
        raise
