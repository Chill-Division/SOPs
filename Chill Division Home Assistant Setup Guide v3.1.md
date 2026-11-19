<!-- Company letterhead image goes here on export (see ChillDivision_Letterhead.docx) -->

**Cultivation Facility**
Home Assistant Setup Guide

v3.1
"The complete set"

---

## Introduction

This guide takes you from a brand new Home Assistant to your first live sensor
reading. It's for a Home Assistant Green, or a NUC running Home Assistant OS,
plugged into your network. You don't need any IT experience.

You'll set up Home Assistant, install the ESPHome app, add a Unit PoE-P4, and
plug in an SHT45 to read temperature, humidity and VPD.

We use one grow tent, GT1 (Grow Tent 1), as the example all the way through.
Use your own names, but keep the pattern.

What to click is outlined in orange on every screenshot. Where there's more
than one click on a screen, they're numbered in order. Click a screenshot to
see it full size.

Once your sensors are in, the [Automations Guide](automations-guide.html) shows
you what to do with them.

Copyright © Chill Division. Licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), with attribution and trademark terms set out in the [NOTICE](https://github.com/Chill-Division/SOPs/blob/main/NOTICE).

---

## What's what

- **Home Assistant** is the automation brain. It runs on your Green or NUC,
  keeps every reading and runs your automations.
- **ESPHome** is how we program the microcontrollers. It runs inside Home
  Assistant as an app called ESPHome Device Builder.
- **M5Stack** makes cost-effective, off-the-shelf parts for us to use. They're
  plug and play, with no soldering.
- **PoE** (Power over Ethernet) powers the microcontroller, and the sensors
  plugged into it, over a single network cable.
- **Unit PoE-P4** is the M5Stack microcontroller we use for every sensor and
  controller.
- **Grove** is the small four-wire plug on M5Stack parts and our boards. The
  PoE-P4 has one Grove port, on its side.
- **SHT45** is our temperature and humidity board. It plugs into the Grove
  port, and the PoE-P4 works out the VPD.
- **Area** is what Home Assistant calls a room. Make one for each grow space,
  like GT1.

## Before you start

You'll need:

- your Home Assistant Green or NUC, plugged into your network and switched on
- a computer on the same network, with a web browser
- a Unit PoE-P4. The ones we supply already have our firmware on them. If yours
  doesn't, do [section 6](#6-a-poe-p4-without-our-firmware) first.
- a PoE switch, and a network cable for the PoE-P4
- an SHT45 and a Grove lead

## 1. Set up Home Assistant

1. On your computer, open `http://homeassistant.local` in your web browser.
   Click **Create my smart home**.

   If the page won't load, give a new Home Assistant a few more minutes to
   start up, then try again.

   ![The Welcome screen, with Create my smart home outlined](images/home-assistant-setup-guide/02-welcome.png)

2. Type your name, then a password twice. Your username fills itself in. Click
   **Create account**.

   Keep the password somewhere safe. You'll need it to log in.

   ![Create user, with Name, Password, Confirm password and Create account outlined](images/home-assistant-setup-guide/03-create-user.png)

3. Search for your town and click it in the list. This sets your time zone and
   units.

   ![Home location, with the search box and the first result outlined](images/home-assistant-setup-guide/04-location-search.png)

4. Click **Next**.

   ![Home location, with Next outlined](images/home-assistant-setup-guide/05-location-next.png)

5. The analytics are up to you. They're all off to start with. Click **Next**.

   ![Help us to help you, with Next outlined](images/home-assistant-setup-guide/06-analytics.png)

6. Home Assistant shows what it's found on your network. Click **Finish**.

   ![We found compatible devices, with Finish outlined](images/home-assistant-setup-guide/07-devices-found.png)

7. You're in. This is your Overview dashboard.

   Home Assistant may say it's discovered devices on your network. Leave those
   for now.

   ![The Overview dashboard](images/home-assistant-setup-guide/08-overview.png)

## 2. Make an area for your grow tent

An area is what Home Assistant calls a room. Every device goes in one, which
makes them easy to find and to automate.

1. Click **Settings** in the sidebar.

   ![The sidebar, with Settings outlined](images/home-assistant-setup-guide/10-sidebar-settings.png)

2. Click **Areas, labels & zones**.

   ![Settings, with Areas, labels and zones outlined](images/home-assistant-setup-guide/11-settings-areas.png)

3. Click **Add**.

   ![Areas, with Add outlined](images/home-assistant-setup-guide/12-areas-add.png)

4. Click **Create area**.

   ![The Add menu, with Create area outlined](images/home-assistant-setup-guide/13-create-area.png)

5. Type `GT1` as the name, then click **Create**.

   ![Create area, with the name GT1 and Create outlined](images/home-assistant-setup-guide/14-area-gt1.png)

6. GT1 is now in your list of areas.

   Living Room, Kitchen and Bedroom come with Home Assistant. You can delete
   them if you like.

   ![Areas, with the new GT1 area outlined](images/home-assistant-setup-guide/15-areas-gt1.png)

## 3. Install the ESPHome app

1. In **Settings**, click **Apps**.

   ![Settings, with Apps outlined](images/home-assistant-setup-guide/20-settings-apps.png)

2. Click **Install app**.

   ![Apps, with Install app outlined](images/home-assistant-setup-guide/21-install-app.png)

3. Type `ESPHome` in the search box, then click **ESPHome Device Builder**. Not
   the beta or the dev one.

   ![The app store, with the search box and ESPHome Device Builder outlined](images/home-assistant-setup-guide/22-store-esphome.png)

4. Click **Install**. It takes a minute or so.

   ![ESPHome Device Builder, with Install outlined](images/home-assistant-setup-guide/23-app-install.png)

5. Turn on **Watchdog** and **Show in sidebar**, then click **Start**.

   ![The app page, with Watchdog, Show in sidebar and Start outlined](images/home-assistant-setup-guide/24-app-start.png)

6. When it says Running, click **Open Web UI**.

   ![The app running, with Open Web UI outlined](images/home-assistant-setup-guide/25-app-running.png)

7. The first time it opens, ESPHome asks a couple of questions. Click
   **Continue**.

   ![Welcome to ESPHome Device Builder, with Continue outlined](images/home-assistant-setup-guide/26-builder-welcome.png)

8. Click **New to ESPHome**, then **Continue**.

   ![Choose your experience, with New to ESPHome and Continue outlined](images/home-assistant-setup-guide/27-builder-experience.png)

9. Click **Maybe later**.

   ![You're ready to build, with Maybe later outlined](images/home-assistant-setup-guide/28-builder-ready.png)

From now on, open it with **ESPHome Builder** in the sidebar.

## 4. Add your first PoE-P4

Plug the PoE-P4 into your PoE switch with a network cable, and give it a minute
to start up.

1. In ESPHome Builder, the PoE-P4 shows up under Discovered. Click
   **Take control**.

   The six characters at the end of its name are different on every unit, so
   yours won't match the screenshot.

   ![Discovered 1 device, with Take control outlined](images/home-assistant-setup-guide/30-discovered.png)

2. Type `GT1 Climate 1` as the Friendly name. The Hostname fills itself in as
   `gt1-climate-1`. Leave **Enable encryption** ticked, and click
   **Take control**.

   ![Take control, with the Friendly name, Hostname and Take control outlined](images/home-assistant-setup-guide/31-take-control.png)

   > **Always give a device a number**, even the first one. "GT1 Climate 1",
   > not "GT1 Climate". When the second one turns up it slots straight in as
   > GT1 Climate 2, and nothing needs renaming.

3. ESPHome builds firmware with the new name and sends it to the PoE-P4. This
   takes a minute or two. When you see **Rename complete!**, click **Close**.

   ![Rename complete, with Close outlined](images/home-assistant-setup-guide/32-rename-complete.png)

4. Now add it to Home Assistant. Go to **Settings** and click
   **Devices & services**.

   ![Settings, with Devices and services outlined](images/home-assistant-setup-guide/34-settings-devices.png)

5. Under Discovered, find **GT1 Climate 1 (gt1-climate-1)** and click **Add**.
   If it isn't there yet, wait a minute and refresh the page.

   ![Devices and services, with Add on GT1 Climate 1 outlined](images/home-assistant-setup-guide/35-ha-discovered.png)

6. Click **Submit**.

   ![Discovered ESPHome device, with Submit outlined](images/home-assistant-setup-guide/36-ha-add-confirm.png)

7. Click **Area** and choose **GT1**.

   ![Name and assign, with GT1 outlined in the area list](images/home-assistant-setup-guide/37-ha-area-pick.png)

8. Click **Finish**.

   ![Name and assign, with the GT1 area and Finish outlined](images/home-assistant-setup-guide/38-ha-area-finish.png)

## 5. Add the SHT45

1. Plug the SHT45 into the PoE-P4's Grove port with the Grove lead. There's
   only one, on the side.

   ![A PoE-P4 with an SHT45 plugged into its Grove port, which is outlined](images/home-assistant-setup-guide/50-hookup-photo.jpg)

2. In ESPHome Builder, click **Edit** on GT1 Climate 1.

   Don't worry about the orange dot next to its name. The install at the end
   of this section clears it.

   ![ESPHome Builder, with Edit on GT1 Climate 1 outlined](images/home-assistant-setup-guide/50a-builder-edit.png)

3. Click the **Show YAML editor only** button, top right.

   ![The editor, with Show YAML editor only outlined](images/home-assistant-setup-guide/52-yaml-only-button.png)

4. In a new browser tab, open our
   [SHT45 Environment Sensor file](https://github.com/Chill-Division/Chill-Division-ESPHome/blob/main/Chill%20Division%20SHT45%20Environment%20Sensor.yaml)
   on GitHub. Click the **Copy raw file** button.

   ![The SHT45 file on GitHub, with Copy raw file outlined](images/home-assistant-setup-guide/53-github-copy.png)

5. Back in ESPHome Builder, scroll to the bottom. Delete the greyed-out
   `# i2c:` lines outlined here. The example file already has i2c settings,
   and your configuration can only have one of those so that your device
   doesn't get confused.

   ![The bottom of the YAML, with the commented-out i2c lines outlined](images/home-assistant-setup-guide/54-yaml-bottom.png)

6. Click on the empty line at the very bottom, and paste (Ctrl+V).

7. Check the pins. The two lines outlined say which pins the Grove lead's
   yellow and white wires are on. The file is set up for the PoE-P4.

   ![The pasted YAML, with the sda and scl lines outlined](images/home-assistant-setup-guide/55-check-pins.png)

   ![A close-up of the sda and scl lines](images/home-assistant-setup-guide/55b-check-pins-zoom.png)

   You might be trying this on an Atom Lite first, rather than a PoE-P4. If
   so, change both lines to suit.

   | Controller | sda (yellow wire) | scl (white wire) |
   | --- | --- | --- |
   | Unit PoE-P4 | `GPIO53` | `GPIO54` |
   | Atom Lite | `GPIO26` | `GPIO32` |

   For any other controller, see the pin table in
   [Chill-Division-ESPHome](https://github.com/Chill-Division/Chill-Division-ESPHome#always-check-the-pins).

8. Click **Save**.

   ![The editor, with Save outlined](images/home-assistant-setup-guide/56-save.png)

9. Click **Install**.

   ![YAML saved, with Install outlined](images/home-assistant-setup-guide/57-install.png)

10. Click **On the network**.

    This will send the updated configuration (firmware) to the PoE-P4 across
    your network, so you never need to plug it into your PC ever again.

    ![How do you want to install the firmware, with On the network outlined](images/home-assistant-setup-guide/58-on-the-network.png)

11. ESPHome builds the firmware and installs it, which takes a minute or two.
    Then it shows the PoE-P4's logs, with a new reading every 10 seconds.
    Close the window with the **X**, top right.

    ![The logs, with the latest readings outlined](images/home-assistant-setup-guide/59-logs-readings.png)

12. In Home Assistant, go to **Settings**, then **Devices & services**, then
    **ESPHome**. Click **GT1 Climate 1**.

    ![The ESPHome integration, with the GT1 Climate 1 device outlined](images/home-assistant-setup-guide/60-esphome-integration.png)

13. That's it. Your temperature, humidity and VPD, in GT1.

    ![The GT1 Climate 1 device page, with the GT1 area and the Sensors card outlined](images/home-assistant-setup-guide/61-device-sensors.png)

## 6. A PoE-P4 without our firmware

The PoE-P4s we supply already have our firmware on them. A new one straight
from M5Stack doesn't, so put it on first, over USB-C. You only do this once per
unit.

You'll need a USB-C cable, and Chrome or Edge on your computer for ESPHome
Web.

1. Download `poep4-firmware.factory.bin` from the
   [latest release](https://github.com/Chill-Division/poep4-preprov/releases/latest)
   of our firmware.

   ![The firmware release on GitHub, with poep4-firmware.factory.bin outlined](images/home-assistant-setup-guide/40-release-download.png)

2. Plug the USB-C cable into the PoE-P4, in the port above the network socket,
   and into your computer. Then push and hold the button on the side of the
   PoE-P4 for 5 seconds. This puts it into flash mode.

3. Open [ESPHome Web](https://web.esphome.io) and click **Connect**.

   ![ESPHome Web, with Connect outlined](images/home-assistant-setup-guide/41-esphome-web.png)

4. Choose **USB JTAG/serial debug unit**, then click **Connect**.

   ![The serial port pop-up, with USB JTAG/serial debug unit and Connect outlined](images/home-assistant-setup-guide/41b-port-popup.png)

5. Click the **Install** button.

   ![ESPHome Web connected, with the Install button outlined](images/home-assistant-setup-guide/42-connected.png)

6. Click **Choose File** and pick the `poep4-firmware.factory.bin` you
   downloaded. Then click **Install**.

   ![Install your existing ESPHome project, with Choose File and Install outlined](images/home-assistant-setup-guide/43-flash-01.png)

7. Keep the window in front while it installs. It takes about 10 seconds.

   ![Installing](images/home-assistant-setup-guide/43-flash-04.png)

8. When it says **Installation complete**, unplug the USB-C cable. Plug the
   PoE-P4 into your PoE switch and carry on from
   [section 4](#4-add-your-first-poe-p4).

   ![Installation complete](images/home-assistant-setup-guide/43-flash-06.png)

## 7. Your next sensor

- A second sensor in the same tent is GT1 Climate 2, `gt1-climate-2`. Same
  steps, next number.
- A second tent gets its own area, GT2, with GT2 Climate 1 in it.
- Our other boards (relays, dimmers and level sensors) each have a file in
  [Chill-Division-ESPHome](https://github.com/Chill-Division/Chill-Division-ESPHome).
  It's the same every time. Copy, paste, check the pins.
- For even more sensors, have a look at
  [M5Stack-ESPHome](https://github.com/Chill-Division/M5Stack-ESPHome).
- Then head to the [Automations Guide](automations-guide.html).

---

## Changelog

* v3.1 new document. Step-by-step screenshots for setting up Home Assistant, the ESPHome app, a PoE-P4 and an SHT45.
