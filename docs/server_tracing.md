# Server request tracing

Every `/api/...` request produces structured JSON lines in the Render service
logs. The server returns the same value in the `X-Request-ID` response header,
so one browser request can be matched to its server-side work.

## Watching a live road-network request

1. Open the Render dashboard, choose `sih26137-backend`, then open **Logs**.
2. In the deployed app, open browser developer tools and select **Network**.
3. Load a real road network, select the `generate` request, and copy its
   `X-Request-ID` response header.
4. Filter the Render logs by that value. The events appear in order:
   `api.request_started`, geocoding/cache events, Overpass attempts, then
   `api.request_completed` or `api.request_failed`.

Road-network events state only provider host, outcome, status and duration.
They do not log request bodies, credentials, access tokens, or the entered
location text.
