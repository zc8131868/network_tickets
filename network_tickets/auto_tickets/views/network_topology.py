from mimetypes import guess_type
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse


TOPOLOGY_DIR = Path("/netclaw/openclaw/custom/agent/network-topology")


def _get_topology_images():
    """Build a sorted list of PNG files under the topology directory."""
    if not TOPOLOGY_DIR.exists() or not TOPOLOGY_DIR.is_dir():
        return []

    images = []
    for image_path in sorted(TOPOLOGY_DIR.rglob("*.png")):
        if not image_path.is_file():
            continue
        rel_path = image_path.relative_to(TOPOLOGY_DIR).as_posix()
        images.append(
            {
                "filename": rel_path,
                "title": image_path.stem.replace("_", " ").replace("-", " ").title(),
                "url": reverse("network_topology_image", kwargs={"image_path": rel_path}),
            }
        )
    return images


def network_topology(request):
    return render(
        request,
        "network_topology.html",
        {
            "topology_images": _get_topology_images(),
            "topology_source_path": str(TOPOLOGY_DIR),
        },
    )


def network_topology_image(request, image_path):
    """Serve PNG files from the topology directory with path safety checks."""
    base_dir = TOPOLOGY_DIR.resolve()

    try:
        candidate = (base_dir / image_path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise Http404("Topology image not found.") from exc

    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise Http404("Invalid topology image path.") from exc

    if not candidate.is_file() or candidate.suffix.lower() != ".png":
        raise Http404("Only PNG topology images are supported.")

    content_type = guess_type(str(candidate))[0] or "image/png"
    return FileResponse(candidate.open("rb"), content_type=content_type)
