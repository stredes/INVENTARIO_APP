from database.connection import initialize_database
from ui.app import FacturionApp


def main() -> None:
    initialize_database()
    app = FacturionApp()
    app.mainloop()


if __name__ == "__main__":
    main()
