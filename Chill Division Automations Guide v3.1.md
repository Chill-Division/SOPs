<!-- Company letterhead image goes here on export (see ChillDivision_Letterhead.docx) -->

**Cultivation Facility**
Automations Guide

v3.1
"The complete set"

---

## Introduction

This guide assumes a locally-controlled [Home Assistant](https://www.home-assistant.io/)
(HA) install driving [ESPHome](https://esphome.io/) microcontrollers, consistent
with the Site Design Guidelines. Example per-device ESPHome YAML for the M5Stack
hardware referenced throughout lives in the Chill Division repository:
<https://github.com/Chill-Division/M5Stack-ESPHome>.

The automations here are written **generically**. Real facilities run multiple
grow rooms (GR1, GR2, and so on). Rather than repeat near-identical automations
per room, each example is shown **for a single grow room**. To add a second room,
duplicate the automation and re-suffix the entity IDs (e.g. `..._gr1` → `..._gr2`)
and the per-room helpers. Entity IDs in this guide are placeholders, so substitute
your own (see [Generic entity names](#appendix-generic-entity-names)).

Nothing here overrides the other three documents. Where an automation enforces a
requirement (photoperiod, door alarms, CO2 safety) the requirement itself lives
in the relevant SOP.

These are not GACP or GMP SOPs, and they won't get you either certification.
Neither is needed under NZMQS for a Cultivator to bring product through
verification, when it's dried / packed / verified in a 3rd party GMP facility.

All terminology follows [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119)
(MUST / SHOULD / MAY).

Copyright © Chill Division. Licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), with attribution and trademark terms set out in the [NOTICE](https://github.com/Chill-Division/SOPs/blob/main/NOTICE).

---

## 1. Design principles

### Where should logic live? (ESPHome vs Home Assistant)

A recurring decision is whether a piece of logic belongs on the microcontroller
(ESPHome) or on the automation server (Home Assistant). The rule of thumb:

- **Put it in ESPHome when** it is safety-critical, must react fast, or must keep
  working even if Home Assistant is restarting or unreachable. Examples: a relay
  that must switch off if a reading crosses a hard limit, a door auto-re-lock,
  debouncing a button, or computing VPD on the device from its own temperature and
  humidity so the value survives an HA outage.
- **Put it in Home Assistant when** it needs orchestration across several devices,
  scheduling, templating, notifications, or a helper / setpoint a human adjusts.
  Examples: photoperiod scheduling, the dosing sequence, "if VPD above the target
  helper then run the humidifier until it drops", and alerting.

A good pattern is **defence in depth**: ESPHome enforces the hard safety limit
locally (e.g. shut the CO2 solenoid above an absolute ceiling), and Home Assistant
runs the normal control loop and alerting on top. Several automations below are
explicitly *fallbacks*: they exist because the primary control lives in ESPHome
and HA is the backstop, or vice-versa.

> **VPD is calculated on the ESPHome device**, not in HA, so it remains valid
> during an HA restart. See the Site Design Guidelines (§2 Sensors) for the
> on-device VPD lambda.

### Designing for resilience

These rooms run CO2, humidification and irrigation under automation. Assume that
Home Assistant *will* restart, power *will* blink, and someone *will* unplug a
sensor by accident, and design so that none of those becomes a crop or safety
problem. The fallback automations later in this guide exist for exactly these
reasons.

- **Don't push updates or restarts during the light period.** An HA / add-on / OS
  update that restarts Home Assistant mid-day can interrupt an automation that
  currently has a relay energised, such as a CO2 solenoid, a humidifier, or an
  irrigation pump left on. Do updates during lights-off, and check afterwards that
  nothing was left running. Better still, enforce the hard cut-offs in ESPHome so a
  stuck relay switches *itself* off regardless of what HA is doing.

- **Write automations that fail safe if interrupted.** Prefer automations that
  leave the room in a safe state if they are cut off part-way through. Anything
  that turns a relay **on** and later turns it **off** after a `delay:` should have
  an *independent* fallback that turns it off unconditionally. A long delay holding
  a pump on is dangerous, because if the automation is killed mid-delay the "off"
  step never runs. The irrigation / pump / solenoid auto-off (§8.4) and the VPD-low
  humidifier cut-off (§7.2) are examples of exactly this backstop, so give every
  "energise then wait" action one.

- **Recover automatically after a power outage.** A 10-15 minute outage drops every
  device at once, and when they come back the room may be well outside its targets
  (for example humidity spiked while the dehumidifier was dead, and now needs to be
  pulled back down). Build the control loops to react to the *current reading*, not
  only to a schedule, so that as devices reconnect the humidification, dehumidifier
  and CO2 loops re-evaluate and correct themselves. The threshold-triggered
  automations (§6, §7) do this naturally, whereas time-only automations do not.
  Consider a small "on Home Assistant start" automation that re-reads the setpoints
  and nudges each loop once everything is back.

- **Survive a partial power trip.** Spread loads across circuits (Site Design
  Guidelines §7) so one breaker can't take out the whole room, and make sure one
  tripped circuit can't cascade into the automations. Don't write an automation
  that assumes every device is alive: put a `timeout:` on every `wait_for_trigger`
  so a loop can't hang forever waiting on a device that lost power, and let the
  independent safety fallbacks (door alarms, CO2 hard-off, reservoir / pump
  cut-offs) run on their own so a dead circuit elsewhere can't disable them.

- **Tolerate a missing sensor.** Someone will eventually knock a sensor loose or
  unplug it. A control loop reading a dead sensor can leave a humidifier or pump
  running indefinitely, and an automation that triggers on a sensor going
  `unavailable` / `unknown` can misfire. Guard against it: give templates sane
  defaults (e.g. `| float(0)`), keep a `timeout:` on every wait so nothing waits
  forever, and where a reading is safety-relevant back it with a second sensor or a
  hard time cap so one unplugged probe can't hold a relay on. Alert when a key
  sensor goes unavailable so it actually gets plugged back in.

---

## 2. Summary of automations

What each automation does, and (since this is a medicinal facility) why you would
run it. Automations are grouped, and each group has a section below with the YAML.

### Photoperiod & lighting

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| Photoperiod begin | At the "lights on" time, turns grow lights on, sets the day temperature target and AC mode, and resets the day's dosing / CO2 counters | Plants need a strict, repeatable light cycle. Drift stresses the crop and can cause hermaphroditism or uneven ripening. Daily counters give per-day accounting of feeds and CO2 |
| Photoperiod end | At "lights off", turns grow lights off and switches AC to overnight dry / night mode | Enforces the uninterrupted dark period (critical in flower) and moves to overnight dehumidification to prevent botrytis / bud rot |
| Light target from helper | Sets LED brightness to a percentage held in a helper | Lets the grower ramp PAR for acclimation and hit exact canopy targets, supporting the Ph. Eur ±10 % label-claim consistency |

### CO2

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| CO2 low → inject | When CO2 falls below the target, opens the CO2 solenoid until it rises past the target (with hysteresis) | Maintains enrichment (usually matched to PAR) for maximum photosynthesis and yield in a sealed room |
| CO2 very high → shut off + evacuate | On a dangerously high reading, closes the solenoid, sounds a spoken alarm, flashes room lights, and notifies staff | **Life safety**: CO2 is an asphyxiant. This protects anyone in the room |
| CO2 low alert | Warns when CO2 stays low despite injection | Flags an empty bottle or failed solenoid before the crop sits CO2-starved |

### VPD & humidity

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| VPD high → humidify | When VPD rises above the target, runs the humidifier until VPD drops back | Maintains target VPD (transpiration control) for healthy, even growth |
| VPD low → humidifier off (fallback) | Force-stops the humidifier if VPD drops too low | Safety net against over-humidification (mold / botrytis) if the main loop misbehaves |
| VPD high → danger alert | Notifies if VPD runs well above target | Prompts manual intervention before the crop is stressed |

### Irrigation, fertigation & crop steering

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| P1 morning saturation | At lights-on, runs multiple shots to re-saturate the substrate until the runoff EC target is met | Implements crop-steering Phase 1. Even saturation avoids channelling and sets the day's EC |
| P2 maintenance shot | A single timed / on-demand fertigation shot | Keeps VWC at its peak plateau through the day (Phase 2) |
| P3 dryback shot | A scheduled overnight shot (or none) | Controls the overnight dryback for generative vs vegetative steering (Phase 3) |
| Pump / solenoid fallback off | Force-stops the pump / solenoid if left on too long | Prevents a stuck relay from draining the tank or flooding the room |
| P4 failure fallback | On a substrate reading below a hard floor, fires an emergency shot and alerts | Rescues the crop if a dripper clogs or the tank empties |
| Reservoir low / empty alert | Notifies when the batch tank is low, and panics if it runs dry | Prompts a fresh batch and protects the pump from running dry |
| Batch tank auto-refill | When the tank is low, adds mains water then doses nutrients | Removes repetitive manual mixing and its human error |
| Doser - update amounts | Recalculates each nutrient part's dose (mL) from the batch size | Keeps mixing consistent with the feed-chart ratios |
| Doser - mix new batch | Runs the peristaltic dosing pumps in sequence with recirculation | Produces a correct, repeatable batch tank automatically |
| Mains water dose | Adds a fixed volume of filtered water on demand | Manual top-ups / batch building |
| Recirculate batch tank | Circulates the tank for a set time | Homogenises nutrients, and can also flush HOCl / PAA through the lines |

### Security, access & safety

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| Auto-lock door when closed | Re-locks a cannabis-room / external door shortly after it closes | Regulatory requirement that doors relock immediately |
| Door open too long → siren | Sounds a siren if a secure door stays open beyond ~60 s | Regulatory anti-diversion alarm that deters propping doors open |
| Duress / panic button | Silent alarm: snapshots the camera and notifies responsible persons | Protects staff coerced into opening the facility |
| Scan-in access (RFID / NFC) | A wearable / tag unlocks a room and logs entry | Convenient second factor that contributes to access logging |
| Gate auto re-lock (fallback) | Re-locks the perimeter gate if left unlocked | Backstop for the ESPHome gate logic |
| Antechamber light on entry | Turns the airlock / antechamber light on when a door opens, off after a delay | Practical airlock workflow that confirms entry |
| Camera motion via MQTT | Bridges NVR motion events into HA | Lets HA log / act on camera motion for perimeter monitoring |
| Siren test (audit) | Briefly sounds then silences the sirens | Supports the scheduled security-audit test regime |
| Server / network offline alert | Notifies if the HA server or its uplink drops | A sealed room going uncontrolled is catastrophic, so you need to know immediately |

### Housekeeping & labour

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| Sensor backlight auto-off | Turns a sensor's display backlight off after a minute | Stops stray light leaking into a dark room and corrupting the photoperiod |
| Defoliation pacer | Speaks "next plant" on a fixed interval | Paces defoliation so every plant gets equal time → a more uniform canopy |

### Advanced / optional (AI)

| Automation | What it does | Why a medicinal facility does it |
| --- | --- | --- |
| vWC analysis (AI) | An LLM reads a substrate-moisture graph and suggests irrigation tweaks | Advisory decision-support for crop steering. **Optional** |
| Licence-plate read (AI) | An LLM reads plates of approaching vehicles into a watchlist field | Perimeter awareness / known-vehicle logging. **Optional, privacy-sensitive** |
| Guest mode | Temporarily dims lights and lowers fans / music for a supervised visitor, auto-resets after an hour | Convenience for tours / inspections without disturbing the crop. **Optional** |

---

## 3. Before you begin: Helpers to create

Create these first under **Settings → Devices & services → Helpers → Create
helper**. Names below are the internal object IDs used in the YAML, so use
whatever friendly names you like. Items marked *(per room)* need one per grow room.

### Toggles (`input_boolean`)

| Helper | Purpose |
| --- | --- |
| `growroom_photoperiod_lights_on` *(per room)* | True while the room is in its "lights on" period, which other automations gate on |
| `growroom_maintenance_mode` *(per room)* | Suspends irrigation / climate automations while you work in the room |
| `growroom_guest_mode` *(per room)* | Puts the room into a visitor-friendly state (optional) |
| `growroom_generative_mode` *(per room)* | Marks the room as generatively steered (optional, for your own logic / dashboards) |
| `growroom_drying` *(per room)* | Marks the room as in drying mode (optional) |
| `start_dosing_cycle` | Momentary trigger to kick off the batch-mix sequence |
| `camera_motion_detected` | Toggled by the NVR-motion bridge (optional) |

### Numbers / setpoints (`input_number`)

| Helper | Purpose |
| --- | --- |
| `growroom_target_vpd` *(per room)* | VPD setpoint the humidification loop chases |
| `growroom_target_co2` *(per room)* | CO2 setpoint the injection loop chases |
| `growroom_target_temp_day` *(per room)* | Daytime AC temperature target |
| `growroom_target_temp_night` *(per room)* | Night AC temperature target |
| `growroom_light_target` *(per room)* | Grow-light brightness % |
| `doser_batchsize` | Batch tank size (L) that drives the doser maths |
| `doser1_hocl`, `doser2_bal`, `doser3_gb`, `doser4_cf` | Calculated per-part dose (mL) for the four nutrient channels |

### Counters (`counter`)

| Helper | Purpose |
| --- | --- |
| `growroom_daily_co2` *(per room)* | Counts CO2 injection events per day |
| `growroom_daily_humidification` *(per room)* | Counts humidification events per day |
| `growroom_irrigation_p1_doses`, `_p2_doses`, `_p3_doses` *(per room)* | Count shots per phase per day |
| `growroom_irrigation_cycle` *(per room)* | Tracks which phase the room is in |

### Buttons (`input_button`)

| Helper | Purpose |
| --- | --- |
| `growroom_p1_dose`, `growroom_p2_dose` *(per room)* | Fire a manual P1 / P2 shot |
| `growroom_manual_dose` *(per room)* | Generic manual fertigation shot |
| `growroom_recirc` *(per room)* | Recirculate the batch tank |
| `growroom_mainswater_dose` *(per room)* | Add a fixed volume of mains water |

### Text (`input_text`): only for the optional AI automations

| Helper | Purpose |
| --- | --- |
| `licenseplates` | Stores the last read plate(s) |
| `camera_motion_detected_entity` | Stores which camera last saw motion |

---

## 4. Before you begin: Devices & sensors

The automations expect these to exist as Home Assistant entities. Most are M5Stack
units flashed with ESPHome using the configs in the
[Chill Division M5Stack-ESPHome repo](https://github.com/Chill-Division/M5Stack-ESPHome).
Wire everything back over PoE where possible (see Site Design Guidelines §2).

| Role | Suggested hardware | Provides (entity) |
| --- | --- | --- |
| Room microcontroller | [M5Stack PoESP32](https://shop.m5stack.com/products/esp32-ethernet-unit-with-poe) (Ethernet + PoE) | Hosts the sensors / relays below and computes VPD on-device |
| CO2 | [SCD40 CO2 unit](https://shop.m5stack.com/products/co2-unit-with-temperature-and-humidity-sensor-scd40) | `sensor.growroom_co2` |
| Temp / humidity (canopy VPD) | SHT45 ([Chill Division custom PCB](https://chilldivision.co.nz/contact.html)) | `sensor.growroom_vpd_canopy` |
| Temp / humidity / pressure | ENV sensor (SHT + pressure) | `sensor.growroom_vpd_top`, room pressure |
| Relays (solenoids, pump, humidifier, CO2) | [M5Stack 4-Relay unit](https://shop.m5stack.com/products/4-relay-unit) / SSR | `switch.growroom_*` relays |
| Substrate moisture / EC | THC-S RS485 substrate sensor | `sensor.growroom_substrate_vwc`, `..._pwec` |
| Reservoir level | Ultrasonic distance unit on the tank lid | `sensor.growroom_reservoir_level` |
| Auto Batch Doser | [Chill Division Auto Batch Doser](https://github.com/Chill-Division/M5Stack-ESPHome) (peristaltic pumps) | `switch.growroom_doser_motor_1..4` |
| Particulate | [PM2.5 kit (PMSA003 + SHT30)](https://shop.m5stack.com/products/pm2-5-air-quality-kit-pmsa003-sht30) | `sensor.growroom_pm2_5`, backlight `light` |
| Bluetooth proxy / siren / buttons | [M5Stack Atom Lite](https://shop.m5stack.com/products/atom-lite-esp32-development-kit) | BLE proxy, `switch.growroom_siren`, panic / duress buttons |
| Air conditioning | IR / RS485-controlled mini-split via HA `climate` | `climate.growroom_ac_1/_2` |
| Doors / access | Zigbee contact sensors + smart locks | `binary_sensor.*_opening`, `lock.*` |

> ⚠ **pH / EC probes:** some facilities add inline pH / EC probes (e.g. Atlas
> Scientific) on the reservoir. None of the core automations below depend on them.
> Treat reservoir pH / EC as monitoring / dashboards unless you build your own
> control loop, and calibrate regularly (see Security Policies & Procedures §10).

### How to add an automation through the UI

Each automation below is ready-to-paste. To add one:

1. **Create the helpers and confirm the devices** it lists under *Needs* first,
   because an automation referencing a helper that doesn't exist yet will error.
2. Go to **Settings → Automations & scenes → Create automation → Start with an
   empty automation**.
3. Click the **⋮ menu (top-right) → Edit in YAML**.
4. Paste the YAML, then **Save** and give it a name.
5. Substitute the placeholder entity IDs for your own, then use the **Automations**
   list to test with **Run** (be careful with anything that moves water or CO2).

---

## 5. Photoperiod & lighting

### 5.1 Photoperiod begin

**Needs:** `light.growroom_fs` (grow light), `climate.growroom_ac_1/_2`,
helpers `growroom_photoperiod_lights_on`, `growroom_target_temp_day`, and the
daily counters. Reference for the on-device pieces:
[M5Stack-ESPHome](https://github.com/Chill-Division/M5Stack-ESPHome).

```yaml
alias: Growroom - Photoperiod begin - Lights on
description: Lights on, set day climate, reset the day's counters.
triggers:
  - trigger: time
    at: "07:00:00"
conditions: []
actions:
  - action: input_boolean.turn_on
    target:
      entity_id: input_boolean.growroom_photoperiod_lights_on
  - action: light.turn_on
    data:
      transition: 30
      brightness_pct: "{{ states('input_number.growroom_light_target') | int(80) }}"
    target:
      entity_id: light.growroom_fs
  - action: counter.set_value
    data:
      value: 0
    target:
      entity_id:
        - counter.growroom_daily_co2
        - counter.growroom_daily_humidification
        - counter.growroom_irrigation_p1_doses
        - counter.growroom_irrigation_p2_doses
  - action: climate.set_temperature
    data:
      temperature: "{{ states('input_number.growroom_target_temp_day') | float(24) }}"
    target:
      entity_id:
        - climate.growroom_ac_1
        - climate.growroom_ac_2
  - action: climate.set_hvac_mode
    data:
      hvac_mode: cool
    target:
      entity_id:
        - climate.growroom_ac_1
        - climate.growroom_ac_2
mode: single
```

### 5.2 Photoperiod end

**Needs:** the same entities as 5.1 plus `growroom_target_temp_night`.

```yaml
alias: Growroom - Photoperiod end - Lights off
description: Lights off, switch AC to overnight dry, set night temperature.
triggers:
  - trigger: time
    at: "20:00:00"
conditions: []
actions:
  - action: input_boolean.turn_off
    target:
      entity_id: input_boolean.growroom_photoperiod_lights_on
  - action: light.turn_off
    data:
      transition: 30
    target:
      entity_id: light.growroom_fs
  - action: climate.set_temperature
    data:
      temperature: "{{ states('input_number.growroom_target_temp_night') | float(22) }}"
    target:
      entity_id:
        - climate.growroom_ac_1
        - climate.growroom_ac_2
  - action: climate.set_hvac_mode
    data:
      hvac_mode: dry
    target:
      entity_id:
        - climate.growroom_ac_1
        - climate.growroom_ac_2
mode: single
```

> The dark period is uninterrupted for a reason, so do not add lights-on actions
> here. If you run undercanopy lighting, turn it off in the same automation.

### 5.3 Set grow-light brightness from a helper

**Needs:** `light.growroom_fs`, `input_number.growroom_light_target`.

```yaml
alias: Growroom - Lights - Apply brightness target
description: When the target changes, apply it to the grow lights if they're on.
triggers:
  - trigger: state
    entity_id: input_number.growroom_light_target
conditions:
  - condition: state
    entity_id: light.growroom_fs
    state: "on"
actions:
  - action: light.turn_on
    data:
      brightness_pct: "{{ states('input_number.growroom_light_target') | int }}"
    target:
      entity_id: light.growroom_fs
mode: single
```

---

## 6. CO2

### 6.1 CO2 low → inject

**Needs:** `sensor.growroom_co2`, `switch.growroom_co2_solenoid`,
`input_number.growroom_target_co2`, `counter.growroom_daily_co2`.

```yaml
alias: Growroom - CO2 - Low, inject to target
description: Open the CO2 solenoid until CO2 rises past the target (hysteresis via wait).
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_co2
    below: input_number.growroom_target_co2
conditions:
  - condition: state
    entity_id: input_boolean.growroom_photoperiod_lights_on
    state: "on"
actions:
  - action: counter.increment
    target:
      entity_id: counter.growroom_daily_co2
  - action: switch.turn_on
    target:
      entity_id: switch.growroom_co2_solenoid
  - wait_for_trigger:
      - trigger: numeric_state
        entity_id: sensor.growroom_co2
        above: "{{ states('input_number.growroom_target_co2') | float + 50 }}"
    timeout:
      minutes: 5
  - action: switch.turn_off
    target:
      entity_id: switch.growroom_co2_solenoid
mode: single
```

> The `+ 50` ppm overshoot gives hysteresis so the solenoid isn't chattering on
> and off at the setpoint. The 5-minute timeout is a safety cap in case the
> sensor never reaches target (empty bottle). See §6.3.

### 6.2 CO2 very high → shut off and evacuate

**Life-safety.** **Needs:** `sensor.growroom_co2`, `switch.growroom_co2_solenoid`,
a `media_player` for spoken alerts, room lights to flash, and a notify service.

> This is the Home Assistant layer. You **must also** enforce an absolute CO2
> ceiling in ESPHome and with standalone hardware, so shutoff still happens if HA
> is down.

```yaml
alias: Growroom - CO2 - Very high, shut off and evacuate
description: Emergency CO2 shutoff with spoken + push alerts and flashing lights.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_co2
    above: 2500
    for:
      minutes: 1
conditions: []
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.growroom_co2_solenoid
  - action: notify.notify
    data:
      title: CO2 DANGER
      message: CO2 high in the grow room. Solenoid shut off, ventilate and check.
  - action: media_player.play_media
    target:
      entity_id: media_player.growroom_speaker
    data:
      media_content_id: >-
        media-source://tts/google_translate?message=Danger.+CO2+is+high.+Please+leave+the+room.&language=en-nz
      media_content_type: provider
  - repeat:
      count: 60
      sequence:
        - action: light.turn_on
          data:
            brightness_pct: 100
            rgb_color: [255, 0, 0]
          target:
            entity_id: light.growroom_room
        - delay: "00:00:01"
        - action: light.turn_off
          target:
            entity_id: light.growroom_room
        - delay: "00:00:01"
mode: single
```

> ⚠ **TTS provider:** the spoken alert uses Google Translate TTS (cloud).
> If you keep everything local, swap it for a local TTS engine (e.g. Piper). The
> alarm still works without TTS via the push notification and flashing lights.

### 6.3 CO2 low alert (manual check)

**Needs:** `sensor.growroom_co2`, notify/`media_player`.

```yaml
alias: Growroom - CO2 - Low, needs checking
description: Warn if CO2 stays low despite injection (empty bottle / failed solenoid).
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_co2
    below: 1100
    for:
      minutes: 2
conditions:
  - condition: state
    entity_id: input_boolean.growroom_photoperiod_lights_on
    state: "on"
actions:
  - action: notify.notify
    data:
      title: CO2 low
      message: CO2 is low despite injection. Check the bottles and solenoid.
mode: single
```

---

## 7. VPD & humidity

### 7.1 VPD high → humidify

**Needs:** `sensor.growroom_vpd_canopy` (computed on the ESPHome device),
`switch.growroom_humidifier`, `input_number.growroom_target_vpd`,
`counter.growroom_daily_humidification`.

```yaml
alias: Growroom - VPD - Too high, humidify
description: Run the humidifier until VPD falls back below target.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_vpd_canopy
    above: input_number.growroom_target_vpd
conditions:
  - condition: state
    entity_id: light.growroom_fs
    state: "on"
    for:
      seconds: 10
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.growroom_humidifier
  - action: counter.increment
    target:
      entity_id: counter.growroom_daily_humidification
  - wait_for_trigger:
      - trigger: numeric_state
        entity_id: sensor.growroom_vpd_canopy
        below: input_number.growroom_target_vpd
    timeout:
      hours: 18
  - action: switch.turn_off
    target:
      entity_id: switch.growroom_humidifier
mode: single
```

### 7.2 VPD too low → humidifier off (fallback)

**Needs:** `sensor.growroom_vpd_canopy`, `switch.growroom_humidifier`.

```yaml
alias: Growroom - VPD - Too low, force humidifier off
description: Independent safety net so the humidifier can't over-run.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_vpd_canopy
    below: 0.4
conditions: []
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.growroom_humidifier
mode: single
```

### 7.3 VPD high → danger alert

```yaml
alias: Growroom - VPD - Danger zone alert
description: Secondary notify if VPD runs well above target.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_vpd_canopy
    above: 1.5
conditions: []
actions:
  - action: notify.notify
    data:
      title: VPD in the danger zone
      message: Go check the grow room immediately.
mode: single
```

---

## 8. Irrigation, fertigation & crop steering

These are the most facility-specific and the easiest to get wrong. **Test every
one with the pump primed but the feed lines diverted to a bucket first.** All shot
durations are examples, so calibrate to your pump, tubing length and dripper count.

Common entities: `switch.growroom_irrigation_pump`,
`switch.growroom_solenoid_fertigation`, `switch.growroom_solenoid_recirc`,
`switch.growroom_solenoid_mainswater`, `sensor.growroom_substrate_pwec`,
`sensor.growroom_substrate_vwc`, `sensor.growroom_reservoir_level`.

### 8.1 Manual fertigation shot (P1 / P2)

One parameterised pattern covers a manual P1 or P2 shot, with the only difference
being the run time. Bind each to its `input_button`.

**Needs:** the pump + fertigation solenoid, `input_button.growroom_p1_dose` (or
`_p2_dose`).

```yaml
alias: Growroom - Irrigation - Manual shot (P1/P2)
description: Fire a single fertigation shot on button press. Adjust the delay per phase.
triggers:
  - trigger: state
    entity_id: input_button.growroom_p2_dose  # or growroom_p1_dose
conditions:
  - condition: state
    entity_id: input_boolean.growroom_maintenance_mode
    state: "off"
actions:
  - action: switch.turn_on
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_fertigation
  - delay: "00:01:54"   # P2 example ~2 min, a P1 saturation shot is longer
  - action: switch.turn_off
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_fertigation
mode: restart
```

### 8.2 P1 morning saturation ramp

Re-saturates the substrate at lights-on: a few priming shots, then repeat until
pore-water EC drops to target, then a couple of settling shots. This is the crop
-steering P1 (see Cultivation Procedures §5 Crop steering).

**Needs:** pump, `sensor.growroom_substrate_pwec`, the P1 counter,
`input_boolean.growroom_photoperiod_lights_on`, `input_boolean.growroom_maintenance_mode`.

```yaml
alias: Growroom - Irrigation - P1 saturation
description: Saturate at lights-on until pore-water EC reaches target, with a dose safety cap.
triggers:
  - trigger: state
    entity_id: input_boolean.growroom_photoperiod_lights_on
    to: "on"
conditions:
  - condition: state
    entity_id: input_boolean.growroom_maintenance_mode
    state: "off"
actions:
  - action: counter.set_value
    data:
      value: 0
    target:
      entity_id: counter.growroom_irrigation_p1_doses
  # Prime: a few short shots spaced apart
  - repeat:
      count: 4
      sequence:
        - action: switch.turn_on
          target: { entity_id: switch.growroom_irrigation_pump }
        - action: counter.increment
          target: { entity_id: counter.growroom_irrigation_p1_doses }
        - delay: "00:01:00"
        - action: switch.turn_off
          target: { entity_id: switch.growroom_irrigation_pump }
        - delay: "00:20:00"
  # Saturate until pore-water EC comes down to target, capped at 30 doses
  - repeat:
      while:
        - condition: numeric_state
          entity_id: sensor.growroom_substrate_pwec
          above: 2
      sequence:
        - action: switch.turn_on
          target: { entity_id: switch.growroom_irrigation_pump }
        - action: counter.increment
          target: { entity_id: counter.growroom_irrigation_p1_doses }
        - delay: "00:00:45"
        - action: switch.turn_off
          target: { entity_id: switch.growroom_irrigation_pump }
        - delay: "00:20:00"
        - if:
            - condition: numeric_state
              entity_id: counter.growroom_irrigation_p1_doses
              above: 30
          then:
            - action: notify.notify
              data:
                title: Irrigation fault
                message: Too many P1 doses. Something is wrong, check now.
            - stop: Too many doses
mode: single
```

> ⚠ The EC target (`above: 2`) and dose counts are examples for a
> particular substrate / genetics. Dial them in during your first runs and watch
> runoff by hand (Cultivation Procedures §5).

### 8.3 P3 overnight dryback shot (scheduled)

**Needs:** the manual-shot automation (8.1) or its button, a schedule.

```yaml
alias: Growroom - Irrigation - P3 overnight shot
description: Fire a P3 shot at set times overnight. Disable if steering for a deep dryback.
triggers:
  - trigger: time
    at: "03:00:00"
conditions: []
actions:
  - action: input_button.press
    target:
      entity_id: input_button.growroom_manual_dose
mode: single
```

### 8.4 Pump / solenoid fallback auto-off (safety)

**Needs:** pump + fertigation solenoid.

```yaml
alias: Growroom - Irrigation - Fallback auto-off
description: Force everything off if the pump/solenoid is left on too long.
triggers:
  - trigger: state
    entity_id: switch.growroom_solenoid_fertigation
    to: "on"
    for:
      minutes: 7
      seconds: 5
  - trigger: state
    entity_id: switch.growroom_irrigation_pump
    to: "on"
    for:
      minutes: 15
conditions: []
actions:
  - action: switch.turn_off
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_fertigation
mode: single
```

### 8.5 P4 failure fallback + alert

**Needs:** a second substrate humidity / VWC sensor, pump, notify, maintenance-mode
helper.

```yaml
alias: Growroom - Irrigation - P4 failure fallback
description: Emergency shot + alert if the substrate drops below a hard floor.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_substrate_vwc
    below: 40
    for:
      seconds: 30
conditions:
  - condition: state
    entity_id: input_boolean.growroom_maintenance_mode
    state: "off"
actions:
  - action: switch.turn_on
    target: { entity_id: switch.growroom_irrigation_pump }
  - delay: "00:01:34"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_irrigation_pump }
  - action: notify.notify
    data:
      title: Irrigation emergency
      message: Substrate dropped below the floor. Fired a fallback shot, please check.
mode: single
```

### 8.6 Reservoir low / empty alerts

> ⚠ **Sensor polarity:** an ultrasonic level sensor measures *distance to
> the water*, so a **higher** reading means a **lower** tank. The examples below
> assume that. If your integration reports level as a percentage full, flip the
> comparisons to `below:`.

```yaml
alias: Growroom - Reservoir - Low, notify
description: Warn to mix a fresh batch. Ultrasonic distance rises as the tank empties.
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_reservoir_level
    above: 580
    for:
      minutes: 3
conditions: []
actions:
  - action: notify.notify
    data:
      title: Batch tank getting low
      message: Mix a fresh batch within the next 24 hours.
mode: single
```

```yaml
alias: Growroom - Reservoir - Empty, panic
description: Panic alert if the tank runs dry (protect the pump).
triggers:
  - trigger: numeric_state
    entity_id: sensor.growroom_reservoir_level
    below: 2          # if your sensor reports % full, invert for distance sensors
    for:
      minutes: 5
conditions: []
actions:
  - action: notify.notify
    data:
      title: Batch tank empty
      message: Reservoir appears dry. Check immediately before the pump runs dry.
mode: single
```

### 8.7 Doser - update per-part amounts from batch size

Recalculates the four channel volumes from the batch size using your feed-chart
ratios. The example ratios below are for an Athena-style 2-part + balance + cleanse
line, so **replace them with your own nutrient line's ratios.**

**Needs:** `input_number.doser_batchsize`, `doser1_hocl`, `doser2_bal`,
`doser3_gb`, `doser4_cf`.

```yaml
alias: Doser - Update amounts from batch size
description: Recompute the four channel doses (mL) whenever the batch size changes.
triggers:
  - trigger: state
    entity_id: input_number.doser_batchsize
conditions: []
actions:
  - variables:
      batch_size: "{{ states('input_number.doser_batchsize') | float(0) }}"
      doser4_cf_value: "{{ (batch_size * 5) | round(0) }}"
      doser3_gb_value: "{{ (doser4_cf_value * (5 / 3)) | round(0) }}"
      doser2_bal_value: "{{ (doser3_gb_value / 5) | round(0) }}"
      doser1_hocl_value: "{{ (doser2_bal_value / 2) | round(0) }}"
  - action: input_number.set_value
    data: { value: "{{ doser4_cf_value }}" }
    target: { entity_id: input_number.doser4_cf }
  - action: input_number.set_value
    data: { value: "{{ doser3_gb_value }}" }
    target: { entity_id: input_number.doser3_gb }
  - action: input_number.set_value
    data: { value: "{{ doser2_bal_value }}" }
    target: { entity_id: input_number.doser2_bal }
  - action: input_number.set_value
    data: { value: "{{ doser1_hocl_value }}" }
    target: { entity_id: input_number.doser1_hocl }
mode: single
```

### 8.8 Doser - mix a new batch tank

Runs the [Auto Batch Doser](https://github.com/Chill-Division/M5Stack-ESPHome)
peristaltic pumps in sequence, recirculating throughout, then stops. The dose
volumes (mL) are converted to run-time assuming the pumps move ~10 mL/s, so
**calibrate this for your pumps and change the `/ 10` divisor accordingly.**

**Needs:** `input_boolean.start_dosing_cycle`, the four doser motor switches, the
pump + recirc solenoid, and the four `doser*` numbers.

```yaml
alias: Doser - Mix a new batch tank
description: Sequential nutrient dosing with recirculation. Order matters (Cultivation Procedures §12).
triggers:
  - trigger: state
    entity_id: input_boolean.start_dosing_cycle
    to: "on"
conditions:
  - condition: state
    entity_id: switch.growroom_solenoid_fertigation
    state: "off"
actions:
  - if:
      - condition: state
        entity_id: switch.growroom_irrigation_pump
        state: "on"
    then:
      - stop: Pump already running, cannot start a batch now
  - action: switch.turn_on
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_recirc
  - delay: "00:00:30"
  # Balance / pH first, then Grow / Bloom, then Core / Fade, then cleanse last
  - action: switch.turn_on
    target: { entity_id: switch.growroom_doser_motor_2 }
  - delay: "{{ states('input_number.doser2_bal') | int(0) / 10 }}"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_doser_motor_2 }
  - delay: "00:00:30"
  - action: switch.turn_on
    target: { entity_id: switch.growroom_doser_motor_3 }
  - delay: "{{ states('input_number.doser3_gb') | int(0) / 10 }}"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_doser_motor_3 }
  - delay: "00:00:30"
  - action: switch.turn_on
    target: { entity_id: switch.growroom_doser_motor_4 }
  - delay: "{{ states('input_number.doser4_cf') | int(0) / 10 }}"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_doser_motor_4 }
  - delay: "00:00:30"
  - action: switch.turn_on
    target: { entity_id: switch.growroom_doser_motor_1 }
  - delay: "{{ states('input_number.doser1_hocl') | int(0) / 10 }}"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_doser_motor_1 }
  - delay: "00:02:30"
  - action: switch.turn_off
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_recirc
  - action: input_boolean.turn_off
    target: { entity_id: input_boolean.start_dosing_cycle }
mode: restart
```

> **Mix order matters**: pH / Silica first, base nutrients, then Cal / Core last, to
> avoid precipitation (Cultivation Procedures §12.7). The order above reflects that, so keep
> it if you re-map the channels.

### 8.9 Mains water dose (fixed volume)

**Needs:** `switch.growroom_solenoid_mainswater`, `input_button.growroom_mainswater_dose`.
Calibrate the delay to the volume you want at your mains pressure / flow.

```yaml
alias: Growroom - Add mains water
description: Open the mains-water solenoid for a fixed time (~a known volume).
triggers:
  - trigger: state
    entity_id: input_button.growroom_mainswater_dose
conditions: []
actions:
  - action: switch.turn_on
    target: { entity_id: switch.growroom_solenoid_mainswater }
  - delay: "00:09:40"   # example: ~140 L, calibrate!
  - action: switch.turn_off
    target: { entity_id: switch.growroom_solenoid_mainswater }
mode: single
```

### 8.10 Recirculate the batch tank

**Needs:** pump + recirc solenoid, `input_button.growroom_recirc`.

```yaml
alias: Growroom - Recirculate batch tank
description: Circulate the tank for 10 minutes to homogenise (or flush HOCl/PAA).
triggers:
  - trigger: state
    entity_id: input_button.growroom_recirc
conditions: []
actions:
  - action: switch.turn_on
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_recirc
  - delay: "00:10:00"
  - action: switch.turn_off
    target:
      entity_id:
        - switch.growroom_irrigation_pump
        - switch.growroom_solenoid_recirc
mode: restart
```

### 8.11 Batch tank auto-refill when low

Ties several of the above together: when the tank is low, add mains water then mix
a batch. Uses `automation.trigger` to call the mains-water and doser automations.

**Needs:** 8.8, 8.9, `sensor.growroom_reservoir_level`.

```yaml
alias: Growroom - Batch tank - Auto refill when low
description: Hourly check. If the tank is low, add water then dose a fresh batch.
triggers:
  - trigger: time_pattern
    hours: "/1"
    minutes: "15"
conditions: []
actions:
  - if:
      - condition: numeric_state
        entity_id: sensor.growroom_reservoir_level
        below: 15          # % full, invert for a distance sensor
        above: 2
    then:
      - action: input_button.press
        target: { entity_id: input_button.growroom_mainswater_dose }
      - delay: "00:01:00"
      - action: input_boolean.turn_on
        target: { entity_id: input_boolean.start_dosing_cycle }
mode: single
```

---

## 9. Security, access & safety

### 9.1 Auto-lock a door when it closes

**Needs:** a door `binary_sensor` (opening) and a `lock`.

```yaml
alias: Security - Door - Auto-lock when closed
description: Relock a secure door a few seconds after it closes.
triggers:
  - trigger: state
    entity_id: binary_sensor.growroom_door_opening
    to: "off"
    for:
      seconds: 3
conditions: []
actions:
  - action: lock.lock
    target:
      entity_id: lock.growroom_door
mode: single
```

### 9.2 Door open too long → siren

**Needs:** the door `binary_sensor`, a siren `switch`. (The SOPs require this on
external and cannabis-room doors.)

```yaml
alias: Security - Door - Alarm when open too long
description: Sound the siren if a secure door stays open beyond ~60 seconds.
triggers:
  - trigger: state
    entity_id: binary_sensor.growroom_door_opening
    to: "on"
    for:
      seconds: 60
conditions: []
actions:
  - action: switch.turn_on
    target: { entity_id: switch.growroom_siren }
  - wait_for_trigger:
      - trigger: state
        entity_id: binary_sensor.growroom_door_opening
        to: "off"
    timeout:
      seconds: 30
  - action: switch.turn_off
    target: { entity_id: switch.growroom_siren }
mode: single
```

### 9.3 Duress / panic button

**Needs:** a discreet button (Zigbee mini button, or an
[M5Stack button unit](https://github.com/Chill-Division/M5Stack-ESPHome) on an
Atom Lite), a camera, and a notify service to responsible persons.

```yaml
alias: Security - Duress button
description: Silent alarm - snapshot the camera and notify responsible persons.
triggers:
  - trigger: state
    entity_id: binary_sensor.duress_button
    to: "on"
conditions: []
actions:
  - action: camera.snapshot
    target:
      entity_id: camera.entrance
    data:
      filename: /config/www/camera/duress.jpg
  - action: notify.notify
    data:
      title: DANGER - Duress
      message: Someone pressed the duress button. Check the cameras now.
      data:
        priority: high
mode: single
```

> Keep the button **unmarked** and near the main entry (Site Design Guidelines
> §1). Do not add any local sound / light here. The whole point is that it's silent.

### 9.4 Scan-in access (RFID / NFC)

**Needs:** an RFID / NFC reader (M5Stack RFID / NFC unit) exposing a `binary_sensor`
per authorised tag, and the room `lock`.

```yaml
alias: Security - Scan-in unlock
description: A recognised tag / wearable unlocks the room and (optionally) greets.
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.access_tag_1
      - binary_sensor.access_tag_2
    from: "off"
    to: "on"
conditions: []
actions:
  - action: lock.unlock
    target:
      entity_id: lock.growroom_door
mode: single
```

> ⚠ **Access control is regulated.** A single tag must not be enough to
> reach cannabis, and 2-factor is required (Security SOP §13). Treat scan-in as *one*
> factor, log every use, and revoke lost tags promptly (Security SOP §14).

### 9.5 Gate auto re-lock (fallback)

> The gate should normally re-lock itself in ESPHome. This HA automation is only
> a backstop.

```yaml
alias: Security - Gate - Auto re-lock (fallback)
description: Backstop that re-locks the gate if it's left unlocked.
triggers:
  - trigger: state
    entity_id: lock.gate
    to: unlocked
    for:
      seconds: 20
conditions: []
actions:
  - action: lock.lock
    target: { entity_id: lock.gate }
mode: single
```

### 9.6 Antechamber / airlock light on entry

**Needs:** door `binary_sensor`(s), the antechamber light `switch`.

```yaml
alias: Security - Antechamber light on entry
description: Turn the airlock light on when a door opens, off after a delay.
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.antechamber_door_opening
      - binary_sensor.growroom_door_opening
    to: "on"
conditions: []
actions:
  - action: switch.turn_on
    target: { entity_id: switch.antechamber_light }
  - delay: "00:10:00"
  - action: switch.turn_off
    target: { entity_id: switch.antechamber_light }
mode: restart
```

### 9.7 Camera motion via MQTT (NVR bridge)

> ⚠ **NVR-specific.** This depends on your NVR publishing motion to MQTT
> (e.g. Blue Iris `/Status` topics). Adjust the topic / parse to your system, or
> delete it if your cameras integrate natively.

```yaml
alias: Security - Cameras - Motion from MQTT
description: Bridge NVR motion events into a helper for logging / automation.
triggers:
  - trigger: mqtt
    topic: NVR/+/Status
    variables:
      motion_camera: "{{ trigger.topic.split('/')[1] }}"
actions:
  - action: input_text.set_value
    data:
      value: "{{ motion_camera }}"
    target:
      entity_id: input_text.camera_motion_detected_entity
  - action: input_boolean.toggle
    target:
      entity_id: input_boolean.camera_motion_detected
mode: restart
```

### 9.8 Siren test (audit)

**Needs:** the siren `switch`(es). Trigger manually during the audit, or add a
schedule.

```yaml
alias: Security - Siren test
description: Briefly sound then silence the sirens for the audit regime.
triggers: []
conditions: []
actions:
  - action: switch.turn_on
    target: { entity_id: switch.growroom_siren }
  - delay: "00:00:05"
  - action: switch.turn_off
    target: { entity_id: switch.growroom_siren }
mode: single
```

### 9.9 Server / network offline alert

> ⚠ **Needs an *external* watchdog.** Home Assistant can't reliably tell
> you it's offline. Use an off-site uptime monitor (e.g. Uptime Kuma) that pings
> HA and notifies you when it stops responding. The automation below is the HA
> side that reports *its* view of connectivity, and the real safety net is the
> external monitor.

```yaml
alias: Monitoring - Server / network offline
description: Notify if the connectivity sensor reports the site offline.
triggers:
  - trigger: state
    entity_id: binary_sensor.site_online
    to: "off"
conditions: []
actions:
  - action: notify.notify
    data:
      title: Site is offline
      message: The facility server / network appears to be down. Investigate now.
mode: single
```

---

## 10. Housekeeping & labour

### 10.1 Sensor backlight auto-off

Stops a sensor's display leaking light into a dark room.

```yaml
alias: Housekeeping - Sensor backlight off
description: Turn a sensor display backlight off a minute after it comes on.
triggers:
  - trigger: state
    entity_id: light.growroom_pm2_5_backlight
    to: "on"
    for:
      minutes: 1
conditions: []
actions:
  - action: light.turn_off
    target: { entity_id: light.growroom_pm2_5_backlight }
mode: single
```

### 10.2 Defoliation pacer

Speaks "next plant" on a fixed interval so each plant gets equal defoliation time.

```yaml
alias: Labour - Defoliation pacer
description: TTS "next plant" every 60s, 30 times, to pace defoliation evenly.
triggers: []
conditions: []
actions:
  - repeat:
      count: 30
      sequence:
        - action: tts.speak
          data:
            cache: true
            media_player_entity_id: media_player.growroom_speaker
            message: Next plant
        - delay: "00:01:00"
mode: single
```

---

## 11. Advanced / optional: AI decision support

> ⚠ **Optional and cloud-dependent.** These use Home Assistant's *AI Task*
> feature with an external LLM provider. They are **advisory only**, so never let an
> LLM directly move water, CO2 or locks. They also send images / data off-site,
> which has privacy and (for a licensed facility) security implications. Treat
> them as experiments, keep a human in the loop, and consider a local model.

### 11.1 vWC analysis notification

Sends a substrate-moisture graph to an LLM and pushes back a short irrigation
suggestion. Requires the AI Task integration and a provider, plus a snapshot of
your substrate graph as an image.

```yaml
alias: AI - Substrate vWC analysis
description: Ask an LLM for an irrigation suggestion from the day's vWC graph. Advisory only.
triggers: []
conditions: []
actions:
  - action: ai_task.generate_data
    data:
      task_name: analyse_vwc
      attachments:
        media_content_id: media-source://media_source/local/substrate-graph.png
        media_content_type: image/png
      instructions: >-
        You are analysing 24 hours of substrate vWC data for a medicinal cannabis
        grow. The plants are in flower on a 13/11 schedule (lights on 07:00, off
        20:00). Give a brief plain-text suggestion for P1/P2/P3 shot size and
        frequency. No formatting, so it must read cleanly in a phone notification.
    response_variable: result
  - action: notify.notify
    data:
      title: Irrigation suggestion (AI, advisory)
      message: "{{ result.data }}"
mode: single
```

### 11.2 Licence-plate read

> ⚠ **Privacy / security sensitive.** Reads plates of vehicles a perimeter
> camera sees. Consider whether this is appropriate and lawful for your site
> before enabling, and store results securely.

```yaml
alias: AI - Read vehicle plate
description: On a vehicle detection, read the plate into a helper for a watchlist.
triggers:
  - trigger: state
    entity_id: binary_sensor.perimeter_camera_vehicle
    to: "on"
conditions: []
actions:
  - action: ai_task.generate_data
    data:
      task_name: read_plate
      instructions: >-
        List any clearly readable NZ licence plates in this image (confidence
        90 %+), comma-separated. Valid plates are up to 6 alphanumeric characters.
      attachments:
        media_content_id: media-source://camera/camera.perimeter
        media_content_type: image/jpeg
      structure:
        plates:
          selector:
            text:
    response_variable: result
  - action: input_text.set_value
    data:
      value: "{{ result.data.plates }}"
    target:
      entity_id: input_text.licenseplates
mode: single
```

### 11.3 Guest mode (optional)

A convenience for supervised visits: dims the grow lights and lowers fans / music,
then auto-resets after an hour. Two automations: enable, and reset.

```yaml
alias: Growroom - Guest mode - Enable
description: Dim lights and soften the room for a supervised visitor.
triggers:
  - trigger: state
    entity_id: input_boolean.growroom_guest_mode
    from: "off"
    to: "on"
conditions: []
actions:
  - action: light.turn_on
    data:
      transition: 5
      brightness_pct: 20
    target:
      entity_id: light.growroom_fs
  - action: fan.set_percentage
    data:
      percentage: 40
    target:
      entity_id: fan.growroom_circulation
mode: restart
```

```yaml
alias: Growroom - Guest mode - Reset after 1 hour
description: Restore normal light / fan levels an hour after guest mode was enabled.
triggers:
  - trigger: state
    entity_id: input_boolean.growroom_guest_mode
    to: "on"
    for:
      hours: 1
  - trigger: state
    entity_id: input_boolean.growroom_guest_mode
    from: "on"
    to: "off"
conditions: []
actions:
  - action: input_boolean.turn_off
    target: { entity_id: input_boolean.growroom_guest_mode }
  - action: light.turn_on
    data:
      transition: 5
      brightness_pct: "{{ states('input_number.growroom_light_target') | int(100) }}"
    target:
      entity_id: light.growroom_fs
  - action: fan.set_percentage
    data:
      percentage: 70
    target:
      entity_id: fan.growroom_circulation
mode: restart
```

---

## Appendix: Generic entity names

Substitute these placeholders with your real entity IDs. Suffix per room where you
run more than one (`_gr1`, `_gr2`, …).

| Placeholder | Meaning |
| --- | --- |
| `light.growroom_fs` | Full-spectrum grow light (dimmable) |
| `light.growroom_room` | Room / work light used for alarms |
| `switch.growroom_undercanopy` | Undercanopy LED relay |
| `sensor.growroom_co2` | Canopy CO2 (SCD40) |
| `sensor.growroom_vpd_canopy` / `_top` | VPD at / above canopy (computed in ESPHome) |
| `switch.growroom_co2_solenoid` | CO2 solenoid relay |
| `switch.growroom_humidifier` | Humidifier relay / SSR |
| `switch.growroom_irrigation_pump` | Fertigation pump relay |
| `switch.growroom_solenoid_fertigation` / `_recirc` / `_mainswater` | Fertigation / recirc / mains-water solenoids |
| `switch.growroom_doser_motor_1..4` | Auto Batch Doser channels (1 cleanse, 2 balance, 3 grow / bloom, 4 core / fade) |
| `sensor.growroom_reservoir_level` | Batch tank level (ultrasonic) |
| `sensor.growroom_substrate_vwc` / `_pwec` | Substrate moisture / pore-water EC (THC-S) |
| `climate.growroom_ac_1` / `_2` | AC units |
| `fan.growroom_circulation` | Circulation / extraction fan |
| `switch.growroom_siren` | Room siren |
| `lock.growroom_door`, `lock.gate` | Door / gate locks |
| `binary_sensor.growroom_door_opening`, `binary_sensor.antechamber_door_opening` | Door contact sensors |
| `binary_sensor.duress_button` | Duress / panic button |
| `media_player.growroom_speaker` | Room speaker for TTS alerts |
| `notify.notify` | Your notification service(s) to responsible persons |

---

## Changelog

* v3.1 updates. The sensor table now uses an SHT45 for canopy temperature / humidity / VPD, in line with the Site Design Guidelines, and the calibration cross-reference now points at the Security Policies & Procedures §10. The Introduction now notes these are not GACP or GMP SOPs.

* v3.0.1 version alignment with the suite release. No changes to this document's content.

* v3.0 unified release. The original combined document was split into three parts, plus an additional Automations Guide.
