# wikidata_edit_rates
This is a command line tool to monitor Wikidata edit rates in real-time. It is helpful to identify accounts/bots that ignore the maxlag parameter when editing while the servers experience high server load.

## Configuration
Configuration: copy `./config-sample.json` to `./config.json` and modify it accordingly. You can go with most of the default values, but you are supposed to provide a Wikimedia username and your email address. Both will be exposed to the Wikidata API through the HTTP user agent and are thus visible to WMF server admins.

A full list of config variables in `./config.json`:
* `sleep_per_step` – integer; update frequency for output on the command line in seconds
* `top_user_num` – integer; top number of users reported
* `timeframe` – integer; time period for which the edit rate is computed (usually 60 sec)
* `maxlag_refresh` – integer; update frequency for maxlag updates in seconds; do not use values lower than 60 sec
* `username` – string; your Wikimedia username; will be exposed to the Wikidata API
* `email` – string; your email address; will be exposed to the Wikidata API
* `rc_stream_source` – string; see docs at [wikitechwiki](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams) for details
* `wikidata_api_endpoint` – string; value "https://www.wikidata.org/w/api.php" will likely never change