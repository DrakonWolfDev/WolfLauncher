# WolfLauncher roadmap

Planned features below have no assigned release date.

## Server queue counts

Show the number of players waiting to join alongside the current player count,
for example **60/60 · Queue: 12**.

- Read the separate queue count exposed by the DayZ live query response.
- Update queue information during automatic live server checks and selected-server
  checks, and display it in the Server Browser and server details.
- Distinguish an empty queue from unavailable or stale information; do not infer
  queue size from player count or treat a missing queue value as zero.

## Direct server links

Let communities share a link such as `https://wolf-forge.co.uk/join/...` in
Discord or on their website. Clicking the link opens WolfLauncher, identifies
the intended server, checks requirements, and prepares the connection.

- Provide shareable links from the launcher using a stable server identity where
  available, with a defined endpoint fallback.
- Add website handling and Windows/Linux launcher link registration, including
  delivery to an already running launcher.
- Resolve the server, refresh its status, identify the required DayZ edition and
  Workshop mods, and run the existing installation and launch readiness checks.
- Present the target server and readiness results before connecting, retaining
  existing confirmation for Workshop subscriptions or downloads.
- Offer installation guidance when WolfLauncher is not installed, and useful
  messages for invalid links, unavailable servers, or unmet requirements.
- Validate incoming link data and pass only supported server information into
  the existing connection flow.
