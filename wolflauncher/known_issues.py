"""User-facing notices for confirmed issues outside WolfLauncher control."""

NVIDIA_PRIME_TITLE = "NVIDIA PRIME Steam launch option"
NVIDIA_PRIME_OPTION = "__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%"
NVIDIA_PRIME_MESSAGE = (
    "DayZ may not start when this Steam launch option is set. WolfLauncher does not "
    "set, read, or change Steam launch options. Remove it in Steam while testing, "
    "then verify DayZ directly from Steam before retrying WolfLauncher."
)


def known_external_issues_text() -> str:
    return (
        "Known external issues\n\n"
        f"{NVIDIA_PRIME_TITLE}:\n"
        f"{NVIDIA_PRIME_OPTION}\n\n"
        f"{NVIDIA_PRIME_MESSAGE}"
    )
