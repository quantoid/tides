"""
Access to tide data from Willy Weather.
https://tides.willyweather.com.au/
https://www.willyweather.com.au/info/api.html
"""
import streamlit as st
import pandas as pd
import requests
import math

host = "https://api.willyweather.com.au"
version = "v2"
key = st.secrets.willy.key
url = f"{host}/{version}/{key}"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def search(query: str) -> dict:
    return get("search", query=query)


def location(code: str) -> dict:
    return get(f"locations/{code}")


def forecast(station: int, start: pd.Timestamp, days: int) -> dict:
    """
    Get forecast for sun and tides from given date for given days.
    Result has sun and tides as DataFrames.
    """
    weather = get(
        f"locations/{station}/weather",
        forecasts="tides,sunrisesunset",
        startDate=start,
        days=days,
    )
    zone = weather['location']['timeZone']
    return dict(
        location=weather['location'],
        sun=sun_times(weather['forecasts']['sunrisesunset'], zone),
        tides=tide_times(weather['forecasts']['tides'], zone),
    )


def get(path: str, **kwargs) -> dict:
    """
    Send GET request to Willy Weather REST API and return decoded response.
    """
    # Cannot use slumber because URLs have .json suffix.
    response = requests.get("/".join((url, f"{path}.json")), params=kwargs, headers=headers)
    response.raise_for_status()
    return response.json()


def sun_times(sun: dict, zone: str) -> pd.DataFrame:
    """
    Get sun forecast as dawn and dusk times in given time-zone.
    """
    return pd.DataFrame([
        dict(
            dawn=pd.Timestamp(d['entries'][0]['firstLightDateTime']).tz_localize(zone),
            dusk=pd.Timestamp(d['entries'][0]['lastLightDateTime']).tz_localize(zone),
        ) for d in sun['days']
    ])


def tide_times(tides: dict, zone: str) -> pd.DataFrame:
    """
    Tides forecast as time, height, units, and type.

    Type is one of:

    - low = low tide
    - high = high tide
    - calc = calculated intermediate height from interpolation
    """
    units = tides['units']['height']
    results = []
    for tide in tides['days']:
        for entry in tide['entries']:
            results.append(dict(
                time=pd.Timestamp(entry['dateTime']).tz_localize(zone),
                height=entry['height'],
                units=units,
                type=entry['type'],
            ))
    return interpolate_heights(extremes=pd.DataFrame(results))


def interpolate_heights(extremes: pd.DataFrame) -> pd.DataFrame:
    # Add intermediate heights between low and high tides.
    added = []
    last = None
    for index, this in extremes.iterrows():
        if last is None:
            last = this
        else:
            minutes = int((this['time'] - last['time']).total_seconds() / 60)
            for minute in range(minutes):
                if minute:
                    time = last['time'] + pd.Timedelta(minutes=minute)
                    added.append(dict(
                        day=time.date(),
                        time=time,
                        height=height_at(
                            t=time,
                            t1=last['time'],
                            h1=last['height'],
                            t2=this['time'],
                            h2=this['height'],
                        ),
                        type="calc",
                    ))
            last = this
    return pd.concat((extremes, pd.DataFrame(added))).sort_values('time').reset_index()


def height_at(t, t1, h1, t2, h2):
    """
    Calculate height at time t based on heights before and after t.
    Reference: www.linz.govt.nz/sites/default/files/cust/
    hydro_almanac_method-to-find-times-or-heights-BETWEEN-high-and-low-waters_202223.pdf
    """
    a = math.pi * ((t - t1) / (t2 - t1) + 1)
    return h1 + (h2 - h1) * ((math.cos(a) + 1) / 2)
