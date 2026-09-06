"""Forward the original package CLI without changing its arguments or authority."""

from .scripts.capability_package import main


if __name__ == "__main__":
    raise SystemExit(main())
