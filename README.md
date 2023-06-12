# Powershaper-Monitor Integration

A Home Assistant integration for importing data from Carbon Co-op's Powershaper service into Home Assistant.
Provides three sensor entities:

- Gas meter (kWh)
- Electricity meter (kWh)
- Eletricity's carbon (kg)

The first two are available to be selected within the energy dashboard. (Future plans to address the display of carbon)

## Setting Up

To set-up the integration, please copy the whole of the _powershaper_ directory into your _custom_components_ directory - there are future plans to have this integration go through the process of having it verified by HA.

Once added, restart your HA instance and you should be able to search for 'powershaper-monitor' within HA.
Import your api_token from your Powershaper service and click **submit**
This will configure the integration and setup three sensor entities.

**NOTE**: Upon configuration (or any subsequent restart of HA), the three sensor entities get (re-)initialized, which pull all available historic data from the Powershaper API for the given meters. As such, for meters that have data going back 5+ years, the data may take up to 10 minutes to fully appear within the Energy Dashboard; it's best if you do not restart your HA instance before you can see the data.

## Credits

- Carbon Co-op's [Powershaper](https://powershaper.io/) API, which is used to fetch all the data from.
- Home Assistant's [Documentation](https://developers.home-assistant.io/docs/creating_component_index/) that helped in creating this integration.
- Home Assistant's [Community](https://community.home-assistant.io/) for the rich eco-system of folks with plenty of examples and willingness to help.
- Carbon Co-op's team who helped with guidance around the requirements of the integration.
