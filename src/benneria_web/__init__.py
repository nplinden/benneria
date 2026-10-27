"""Benneria: the combined web app (landing page, dictionary and notebook). See app.py."""


def main():
    # Imported here so importing the package doesn't load the Flask app.
    from .server import main as server_main
    server_main()


__all__ = ["main"]
