import multiprocessing


def run() -> None:
    # PyInstaller requires this before application imports so spawned Workshop
    # helpers execute their multiprocessing payload instead of relaunching the GUI.
    multiprocessing.freeze_support()
    from wolflauncher.app import main

    main()


if __name__ == "__main__":
    run()
