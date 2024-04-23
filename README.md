# hacs-aladdin-legacy

## Summary
[Genie Aladdin Connect](https://www.geniecompany.com/aladdin-connect-by-genie) legacy plugin for Home Assistant via HACS.

A workaround to use the legacy mechanisms while Aladdin works on their new API.

## Install
- Go to HACS -> Integrations
- Click the three dots on the top right and select Custom Repositories
- Enter https://github.com/andyrak/hacs-aladdin-legacy.git as repository, select the category Integration and click Add
- A new custom integration shows up for installation (Aladdin Connect Legacy) - install it
- Restart Home Assistant

## Configuration
TODO

## Debugging
To aquire debug-logs, add the following to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.aladdin_connect_legacy: debug
```

Logs should now be available in `home-assistant.log`.

## Thanks
- [@derek-miller](https://github.com/derek-miller) for his [homebridge-genie-aladdin-connect](https://github.com/derek-miller/homebridge-genie-aladdin-connect) Homebridge plugin that this work is based on
- Original authors of core Home Assistant Aladdin Connect integration
    - mkmer
    - Franck Nijhof
    - Erik Montnemery
    - Paulus Schoutsen
    - epenet
    - Marc Mueller
    - J. Nick Koston
    - Joost Lekkerkerker
    - Sid
    - springstan
    - Josh Shoemaker
    - Michael
    - Robert Hillis
    - Tobias Sauerwein
    - Trinnik
    - bouni
    - cgtobi

