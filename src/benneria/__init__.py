def main():
    # Imported here so `python -m benneria.local` doesn't load the module twice.
    from .server import main as server_main
    server_main()


__all__ = ["main"]
