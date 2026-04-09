"""Compliance Troubleshooter backend.

A small FastAPI application that proxies Fleet's REST API, translates
compliance findings into plain English (via Claude or a static fallback),
and brokers remediation actions through Fleet's script execution API.

The package layout is intentionally flat: each module has exactly one
responsibility and they import each other in a star pattern from main.py.
This is small enough not to need a deeper hierarchy.
"""
