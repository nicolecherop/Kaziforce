"""Private originals; recruiters see copies attached to submitted applications."""

from pathlib import Path
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .access import candidate_required
from .document_forms import DocumentUploadForm
from .models import CandidateDocument


def document_response(file, original_name, inline=False):
    try:
        stream = file.open("rb")
    except FileNotFoundError as error:
        raise Http404("This file is no longer available.") from error
    content_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    content_type = content_types.get(
        Path(original_name).suffix.lower(), "application/octet-stream"
    )
    response = FileResponse(
        stream,
        as_attachment=not inline or content_type == "application/octet-stream",
        filename=original_name,
        content_type=content_type,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response


@candidate_required
@never_cache
@require_http_methods(["GET", "POST"])
def documents(request):
    kind = request.GET.get("kind", "cv")
    if kind not in CandidateDocument.Kind.values:
        kind = "cv"
    form = DocumentUploadForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        initial={"kind": kind},
    )
    if request.method == "POST" and form.is_valid():
        if request.user.documents.count() >= 20:
            form.add_error(
                None,
                "You have 20 saved documents. Delete one before uploading another.",
            )
        else:
            document = form.save(commit=False)
            document.user = request.user
            document.original_name = form.cleaned_data["file"].name
            try:
                document.save()
            except Exception:
                if document.file and document.file._committed:
                    document.file.storage.delete(document.file.name)
                raise
            messages.success(
                request,
                "Your document has been uploaded. Choose it when applying for a job.",
            )
            return redirect("candidates:documents")
    return render(
        request,
        "candidates/documents.html",
        {"form": form, "documents": request.user.documents.all()},
    )


@candidate_required
@never_cache
@require_GET
def document_file(request, document_id):
    document = get_object_or_404(CandidateDocument, pk=document_id, user=request.user)
    return document_response(
        document.file, document.original_name, inline=request.GET.get("view") == "1"
    )


@candidate_required
@never_cache
@require_POST
def document_delete(request, document_id):
    document = get_object_or_404(CandidateDocument, pk=document_id, user=request.user)
    document.file.delete(save=False)
    document.delete()
    messages.success(
        request,
        "Document deleted from your library. Copies already submitted with applications remain with those applications.",
    )
    return redirect("candidates:documents")
