import json

from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaECO,
    IntelliClimaECOCustomProgram,
    IntelliClimaECODefaultProgram,
    IntelliClimaModelType,
)


def test_default_program_roundtrip():
    prog = IntelliClimaECODefaultProgram(w=(1, 2, 3), s=(4, 5, 6))
    s = prog.to_formatted_str()
    loaded = json.loads(s)
    assert tuple(loaded["w"]) == (1, 2, 3)
    assert tuple(loaded["s"]) == (4, 5, 6)


def test_custom_program_roundtrip():
    prog = IntelliClimaECOCustomProgram(name="P1", graph=(1, 2, 3))
    s = prog.to_formatted_str()
    loaded = json.loads(s)
    assert loaded["name"] == "P1"
    assert tuple(loaded["graph"]) == (1, 2, 3)


def test_intelliclima_devices_helpers():
    devices = IntelliClimaDevices(ecocomfort2_devices={}, c800_devices={})
    assert devices.num_devices == 0
    empty = IntelliClimaDevices.empty()
    assert isinstance(empty, IntelliClimaDevices)
    assert empty.num_devices == 0


def test_ecocomfort_post_init_pcustom_list_to_str():
    model = IntelliClimaModelType(modello="ECO", tipo="ECOCOMFORT")
    p1 = IntelliClimaECOCustomProgram(name="A", graph=(1, 2))
    p2 = IntelliClimaECOCustomProgram(name="B", graph=(3, 4))

    eco = IntelliClimaECO(
        id="10",
        crono_sn="SN",
        status="1",
        online="1",
        command="",
        model=model,
        name="Device",
        houses_id="1",
        mode_set="00",
        mode_state="00",
        speed_set="00",
        speed_state="00",
        last_online="",
        creation_date="",
        fw="",
        mac="",
        macwifi="",
        conn_num="",
        conn_state="",
        role="1",
        rh_thrs="",
        lux_thrs="",
        voc_thrs="",
        slv_rot="",
        slv_addr="",
        offset_temp="",
        offset_hum="",
        year="",
        month="",
        day="",
        dow="",
        hour="",
        minute="",
        second="",
        dst="",
        mode_prev=None,
        dir_state="",
        auto_cycle="",
        tamb="",
        rh="",
        voc_state="",
        plun=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pmar=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pmer=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pgio=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pven=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        psab=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pdom=IntelliClimaECODefaultProgram(w=(0,), s=(0,)),
        pcustom=[p1, p2],
        sfondo="",
        tperc=None,
        fcool="",
        ws="",
        filter_from="",
        filter_active="",
        timezone=None,
        co2=None,
        sanification=None,
        rssi=None,
        aqi=None,
        co2_thrs=None,
        dev_state=None,
        online_status=True,
        online_status_debug="",
    )

    assert isinstance(eco.pcustom, str)
    assert " " not in eco.pcustom
    assert "A" in eco.pcustom
    assert "B" in eco.pcustom
