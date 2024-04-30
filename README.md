![HACS Badge](https://img.shields.io/badge/hacs-custom-orange?link=https%3A%2F%2Fgithub.com%2Fhacs%2Fintegration)
![Build Status](https://img.shields.io/github/actions/workflow/status/andyrak/hacs-aladdin-legacy/release.yml)
![GitHub Release](https://img.shields.io/github/v/release/andyrak/hacs-aladdin-legacy)
![HACS Installs](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.aladdin_connect.total&suffix=%20installs&logo=home-assistant&label=usage&color=41BDF5&cacheSeconds=15600)


# hacs-aladdin-legacy

## Summary
[Aladdin Connect](https://www.geniecompany.com/aladdin-connect-by-genie) legacy plugin for Home Assistant via HACS.

A workaround to use the legacy mechanisms while Aladdin works on their new API.

## Install

### HACS Installation
- Go to HACS -> Integrations
- Click the three dots on the top right and select Custom Repositories
- Enter https://github.com/andyrak/hacs-aladdin-legacy.git as repository, select the category Integration and click Add
- A new custom integration shows up for installation (Aladdin Connect Legacy) - install it
- Restart Home Assistant

### Manual Installation
Copy the contents of the `custom_components` folder to your Home Assistant `config/custom_components`
folder and restart Home Assistant.

## Configuration
Configuration is managed entirely from the UI via `config_flow`.
Simply go to Settings -> Devices & services -> Add Integration and search for "Aladdin Connect Legacy"
in the search box.

## Notes
After installing, you will get the core Aladdin Connect integration deprecation warning; this can safely be ignored.

## Debugging
To aquire debug-logs, add the following to your `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.aladdin_connect: debug
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

