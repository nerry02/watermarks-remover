# Nerry's Marks Cleaner

This responsive web interface calls the repository's existing HTTP service. The service and its cleaning pipeline are unchanged.

## Run locally

Start the cleaner service from the repository root:

```sh
make serve
```

In another terminal, start the web app:

```sh
export WATERMARKS_SERVICE_URL=http://127.0.0.1:8765
# If the cleaner service uses WATERMARKS_SERVER_API_KEY, set the same value here.
export WATERMARKS_SERVER_API_KEY='your-server-side-key'
python3 web/server.py
```

Then open http://127.0.0.1:8080. On Windows, use `py` instead of `python3` and start the core service with `py service/scripts/server.py --host 127.0.0.1 --port 8765`.

The browser sends files only to the same-origin `/api/inspect` and `/api/clean` routes. The Python server adds the bearer key when forwarding requests to the cleaner. Never put the key in `index.html`, a browser setting, or a public client bundle. The web server binds to loopback by default. For a remote deployment, use TLS and place it behind an access-controlled reverse proxy; configure `WATERMARKS_SERVICE_URL` for the address reachable from the web server.

Uploads are limited to 100 MB. Inspection and cleaning use the formats and capabilities supported by the existing service. Cleaning returns a separate download and does not overwrite the source file.
