import logging

from config import get_config_path
from ui import App


def _configurar_logging():
    log_path = get_config_path().parent / "app.log"
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main():
    _configurar_logging()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
