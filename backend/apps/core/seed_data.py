"""DEVELOPMENT SEED DATA — not for production use.

Rules followed here:
- Only headline specifications that follow directly from the manufacturer part-number
  scheme or the part's defining function are filled in (e.g. STM32F411VET6 → 512 KB flash).
- Every seeded real-world part carries SEED_NOTE telling users to verify against the datasheet.
- Generic passives are internal parts *defined* by their values, so their specs are not claims
  about a third-party product.
"""

SEED_NOTE = "[DEV SEED DATA] Specifications NOT verified against the datasheet. Verify before design use."

MANUFACTURERS = [
    {"name": "Texas Instruments", "short_name": "TI", "website": "https://www.ti.com", "country": "USA"},
    {"name": "STMicroelectronics", "short_name": "ST", "website": "https://www.st.com", "country": "Switzerland"},
    {"name": "NXP Semiconductors", "short_name": "NXP", "website": "https://www.nxp.com", "country": "Netherlands"},
    {"name": "Infineon Technologies", "short_name": "Infineon", "website": "https://www.infineon.com", "country": "Germany"},
    {"name": "Avia Semiconductor", "short_name": "Avia", "website": "", "country": "China"},
    {"name": "Trinamic (Analog Devices)", "short_name": "ADI Trinamic", "website": "https://www.analog.com", "country": "Germany"},
]

PACKAGES = [
    {"name": "0603", "mounting_type": "SMD", "pin_count": 2},
    {"name": "0805", "mounting_type": "SMD", "pin_count": 2},
    {"name": "1206", "mounting_type": "SMD", "pin_count": 2},
    {"name": "SOIC-8", "mounting_type": "SMD", "pin_count": 8},
    {"name": "SOP-16", "mounting_type": "SMD", "pin_count": 16},
    {"name": "VSSOP-10", "mounting_type": "SMD", "pin_count": 10},
    {"name": "LQFP-100", "mounting_type": "SMD", "pin_count": 100},
    {"name": "LQFP-144", "mounting_type": "SMD", "pin_count": 144},
    {"name": "TO-263-7", "mounting_type": "SMD", "pin_count": 7},
]

# (code, name, parent_code, [spec definitions])
SPEC = dict  # readability alias
CATEGORIES = [
    ("PAS", "Passives", None, []),
    ("CAP", "Capacitors", "PAS", [
        SPEC(key="capacitance", name="Capacitance", data_type="DECIMAL", unit="F", use_si_prefix=True, is_required=True, sort_order=1),
        SPEC(key="voltage_rating", name="Voltage rating", data_type="DECIMAL", unit="V", use_si_prefix=True, sort_order=2),
        SPEC(key="tolerance", name="Tolerance", data_type="DECIMAL", unit="%", sort_order=3),
        SPEC(key="dielectric", name="Dielectric", data_type="ENUM", sort_order=4,
             enum_choices=["C0G/NP0", "X5R", "X7R", "X7S", "Y5V", "Aluminium electrolytic", "Tantalum", "Polymer"]),
        SPEC(key="temperature_range", name="Temperature range", data_type="STRING", sort_order=5, help_text="e.g. -55 to 125 °C"),
    ]),
    ("RES", "Resistors", "PAS", [
        SPEC(key="resistance", name="Resistance", data_type="DECIMAL", unit="Ω", use_si_prefix=True, is_required=True, sort_order=1),
        SPEC(key="tolerance", name="Tolerance", data_type="DECIMAL", unit="%", sort_order=2),
        SPEC(key="power_rating", name="Power rating", data_type="DECIMAL", unit="W", use_si_prefix=True, sort_order=3),
        SPEC(key="voltage_rating", name="Voltage rating", data_type="DECIMAL", unit="V", use_si_prefix=True, sort_order=4),
        SPEC(key="tempco", name="Temperature coefficient", data_type="INTEGER", unit="ppm/°C", sort_order=5),
    ]),
    ("IC", "Integrated Circuits", None, [
        SPEC(key="automotive_qualified", name="Automotive qualified (AEC-Q100)", data_type="BOOLEAN", sort_order=90),
    ]),
    ("IC-MCU", "Microcontrollers", "IC", [
        SPEC(key="core", name="Core", data_type="STRING", sort_order=1),
        SPEC(key="flash", name="Flash", data_type="INTEGER", unit="KB", sort_order=2),
        SPEC(key="ram", name="RAM", data_type="INTEGER", unit="KB", sort_order=3),
        SPEC(key="gpio", name="GPIO", data_type="INTEGER", sort_order=4),
        SPEC(key="adc_channels", name="ADC channels", data_type="INTEGER", sort_order=5),
        SPEC(key="can", name="CAN", data_type="INTEGER", sort_order=6),
        SPEC(key="uart", name="UART", data_type="INTEGER", sort_order=7),
        SPEC(key="spi", name="SPI", data_type="INTEGER", sort_order=8),
        SPEC(key="i2c", name="I2C", data_type="INTEGER", sort_order=9),
    ]),
    ("IC-CAN", "CAN Transceivers", "IC", [
        SPEC(key="max_data_rate", name="Max data rate", data_type="DECIMAL", unit="bit/s", use_si_prefix=True, sort_order=1),
    ]),
    ("IC-ADC", "Data Converters", "IC", [
        SPEC(key="resolution", name="Resolution", data_type="INTEGER", unit="bit", sort_order=1),
        SPEC(key="channels", name="Channels", data_type="INTEGER", sort_order=2),
        SPEC(key="interface", name="Interface", data_type="ENUM", enum_choices=["I2C", "SPI", "Serial (proprietary)", "Parallel"], sort_order=3),
    ]),
    ("IC-AMP", "Amplifiers", "IC", [
        SPEC(key="channels", name="Channels", data_type="INTEGER", sort_order=1),
        SPEC(key="gbw", name="Gain bandwidth", data_type="DECIMAL", unit="Hz", use_si_prefix=True, sort_order=2),
    ]),
    ("IC-LED", "LED / PWM Drivers", "IC", [
        SPEC(key="channels", name="Channels", data_type="INTEGER", sort_order=1),
        SPEC(key="pwm_resolution", name="PWM resolution", data_type="INTEGER", unit="bit", sort_order=2),
        SPEC(key="interface", name="Interface", data_type="ENUM", enum_choices=["I2C", "SPI"], sort_order=3),
    ]),
    ("IC-MOT", "Motor Drivers", "IC", [
        SPEC(key="driver_type", name="Driver type", data_type="ENUM", enum_choices=["Half-bridge", "Full-bridge", "Stepper", "BLDC"], sort_order=1),
    ]),
    ("IC-PWR", "Power Management", "IC", [
        SPEC(key="function", name="Function", data_type="STRING", sort_order=1),
    ]),
]

# Real parts. specs: {key: value} — only what is implied by the part number / defining function.
COMPONENTS = [
    dict(mpn="TCAN1042HGVDRQ1", name="CAN Transceiver", manufacturer="Texas Instruments", category="IC-CAN",
         package="SOIC-8", description="CAN transceiver", lifecycle_status="ACTIVE",
         aliases=[("TCAN1042", "KICAD_VALUE")]),
    dict(mpn="STM32F411VET6", name="MCU ARM Cortex-M4 512KB Flash", manufacturer="STMicroelectronics",
         category="IC-MCU", package="LQFP-100", description="32-bit microcontroller",
         specs={"core": "ARM Cortex-M4", "flash": 512, "ram": 128}, aliases=[("STM32F411VETx", "KICAD_VALUE")]),
    dict(mpn="STM32H743ZIT6", name="MCU ARM Cortex-M7 2MB Flash", manufacturer="STMicroelectronics",
         category="IC-MCU", package="LQFP-144", description="32-bit microcontroller",
         specs={"core": "ARM Cortex-M7", "flash": 2048, "ram": 1024}, aliases=[("STM32H743ZITx", "KICAD_VALUE")]),
    dict(mpn="ADS1115IDGSR", name="16-bit ADC, 4-ch, I2C", manufacturer="Texas Instruments", category="IC-ADC",
         package="VSSOP-10", description="Delta-sigma ADC with I2C interface",
         specs={"resolution": 16, "channels": 4, "interface": "I2C"}, aliases=[("ADS1115", "KICAD_VALUE")]),
    dict(mpn="PCA9685", name="16-channel 12-bit PWM LED controller", manufacturer="NXP Semiconductors",
         category="IC-LED", description="I2C PWM controller. Base part number — orderable package suffix not selected.",
         specs={"channels": 16, "pwm_resolution": 12, "interface": "I2C"}),
    dict(mpn="BTN8982TA", name="High-current half-bridge", manufacturer="Infineon Technologies", category="IC-MOT",
         package="TO-263-7", description="Integrated half-bridge motor driver", specs={"driver_type": "Half-bridge"}),
    dict(mpn="HX711", name="24-bit ADC for weigh scales", manufacturer="Avia Semiconductor", category="IC-ADC",
         package="SOP-16", description="Load-cell ADC", specs={"resolution": 24, "interface": "Serial (proprietary)"}),
    dict(mpn="TMC2209", name="Stepper motor driver", manufacturer="Trinamic (Analog Devices)", category="IC-MOT",
         description="Stepper driver. Base part number — orderable suffix not selected.", specs={"driver_type": "Stepper"}),
    dict(mpn="LM358", name="Dual operational amplifier", manufacturer="Texas Instruments", category="IC-AMP",
         description="General purpose dual op-amp. Base part number — package suffix not selected.", specs={"channels": 2}),
    dict(mpn="TLV9042", name="Dual operational amplifier", manufacturer="Texas Instruments", category="IC-AMP",
         description="Dual op-amp. Base part number — package suffix not selected.", specs={"channels": 2}),
    dict(mpn="LM74700", name="Ideal diode controller", manufacturer="Texas Instruments", category="IC-PWR",
         description="Ideal diode controller. Base part number.", specs={"function": "Ideal diode controller"}),
    dict(mpn="LM74701", name="Ideal diode controller", manufacturer="Texas Instruments", category="IC-PWR",
         description="Ideal diode controller. Base part number.", specs={"function": "Ideal diode controller"}),
]

# Internal generic parts, defined by their values.
GENERIC_PARTS = [
    dict(name="Capacitor 100nF 50V X7R 0603", category="CAP", package="0603",
         specs={"capacitance": "100n", "voltage_rating": "50", "tolerance": "10", "dielectric": "X7R"}),
    dict(name="Capacitor 10uF 25V X5R 0805", category="CAP", package="0805",
         specs={"capacitance": "10u", "voltage_rating": "25", "tolerance": "10", "dielectric": "X5R"}),
    dict(name="Capacitor 22uF 25V X5R 1206", category="CAP", package="1206",
         specs={"capacitance": "22u", "voltage_rating": "25", "tolerance": "20", "dielectric": "X5R"}),
    dict(name="Resistor 10k 1% 0603", category="RES", package="0603",
         specs={"resistance": "10k", "tolerance": "1", "power_rating": "100m"}),
    dict(name="Resistor 4k7 1% 0603", category="RES", package="0603",
         specs={"resistance": "4k7", "tolerance": "1", "power_rating": "100m"}),
]

# (email, first, last, role)
USERS = [
    ("admin@electava.local", "System", "Admin", "SUPER_ADMIN"),
    ("ops.admin@electava.local", "Ops", "Admin", "ADMIN"),
    ("hw.engineer@electava.local", "Hardware", "Engineer", "HARDWARE_ENGINEER"),
    ("pcb.engineer@electava.local", "PCB", "Engineer", "PCB_ENGINEER"),
    ("purchase@electava.local", "Purchase", "Team", "PURCHASE"),
    ("store@electava.local", "Store", "Keeper", "STORE"),
    ("production@electava.local", "Production", "Lead", "PRODUCTION"),
    ("viewer@electava.local", "Read", "Only", "VIEWER"),
]
