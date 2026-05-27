"""Bootstrap for the generic Shopify connector example.

Run with:
    vested-connect worker --bootstrap=./bootstrap.py
"""

from vested_connect import ConnectorApp

app = ConnectorApp.create().scan_module("shopify_app")
