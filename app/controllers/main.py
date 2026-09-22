from flask import Blueprint, render_template, jsonify, request
from app.services.doctor_service import DoctorService

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Public landing page."""
    return render_template("index.html")


@main_bp.route("/health")
def health_check():
    """
    Health check endpoint for staging/production monitoring, Docker, and CI/CD pipelines.
    Returns HTTP 200 with application status metadata.
    """
    return jsonify({
        "status": "healthy",
        "service": "Hospital Management System",
        "version": "1.0.0",
        "module": "Module 3 - Doctor Management"
    }), 200


@main_bp.route("/doctors", methods=["GET"])
def doctor_directory():
    """Hospital Doctor Directory with search and specialization filter."""
    search_query = request.args.get("search", "").strip()
    specialization_filter = request.args.get("specialization", "").strip()
    page = request.args.get("page", 1, type=int)

    # In public/general directory, list only active doctors
    query = DoctorService.list_doctors(
        search_query=search_query,
        specialization_filter=specialization_filter,
        status_filter="active"
    )
    pagination = query.paginate(page=page, per_page=9, error_out=False)
    doctors = pagination.items

    return render_template(
        "doctors/directory.html",
        doctors=doctors,
        pagination=pagination,
        search_query=search_query,
        specialization_filter=specialization_filter,
        specializations=DoctorService.VALID_SPECIALIZATIONS
    )
