from flask import Blueprint, render_template, jsonify

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
        "module": "Module 1 - Authentication & RBAC"
    }), 200
