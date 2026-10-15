"""Benneria Notebook: notes on Biblical verses. Bible text from BHSA, see bhsa.py."""


def main():
    # Imported here so importing the package (e.g. for bhsa.py) doesn't load the web app.
    from .server import main as server_main
    server_main()


__all__ = ["main"]
