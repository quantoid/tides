"""
Access to tide data from Willy Weather.
https://tides.willyweather.com.au/
https://www.willyweather.com.au/info/api.html
"""
import streamlit as st
import pandas as pd
import requests
import math

day = 24 * 60 * 60

host = "https://api.willyweather.com.au"
version = "v2"
key = st.secrets.willy.key
url = f"{host}/{version}/{key}"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


@st.cache_data(ttl=day, show_spinner="Fetching locations...")
def search(query):
    return get("search", query=query)


@st.cache_data(ttl=day, show_spinner="Fetching location...")
def location(code):
    return get(f"locations/{code}")


@st.cache_data(ttl=day, show_spinner="Fetching tides...")
def forecast(where, when, days, margin):
    station = where['id'] if type(where) is dict else where
    weather = get(
        f"locations/{station}/weather",
        forecasts="tides,sunrisesunset",
        days=days,
        startDate=when,
    )
    zone = weather['location']['timeZone']
    sun = sun_times(weather['forecasts']['sunrisesunset'], zone)
    tides = tide_times(weather['forecasts']['tides'], sun, margin, zone)
    return dict(where=weather['location'], zone=zone, sun=sun, tides=tides)


def get(path, **kwargs):
    # Cannot use slumber because URLs have .json suffix.
    response = requests.get("/".join((url, f"{path}.json")), params=kwargs, headers=headers)
    response.raise_for_status()
    return response.json()


def sun_times(sun, zone):
    return pd.DataFrame([
        dict(
            dawn=pd.Timestamp(d['entries'][0]['firstLightDateTime']).tz_localize(zone),
            dusk=pd.Timestamp(d['entries'][0]['lastLightDateTime']).tz_localize(zone),
        ) for d in sun['days']
    ])


def tide_times(tides, sun, margin, zone):
    """
    Interpolated height every minute over period covered by given tide times.

    :param pd.DataFrame tides: low/high tide times (type=low|high)
    :param str zone: time-zone name provided with data
    :return pd.DataFrame: tides plus interpolated tide times (type=calc)
    """
    if not tides:
        return None
    units = tides['units']['height']
    assert units == "m"
    results = []
    for tide in tides['days']:
        for entry in tide['entries']:
            results.append(dict(
                time=pd.Timestamp(entry['dateTime']).tz_localize(zone),
                height=entry['height'],
                type=entry['type'],
            ))
    df = interpolate_heights(pd.DataFrame(results))
    # Add column that says which times are safe.
    df = add_safety(df, sun, margin)
    df = add_limits(df)
    # Include tide times between the earliest dusk and latest dawn.
    return df[(df['time'] > sun['dusk'].min()) & (df['time'] < sun['dawn'].max())]


def interpolate_heights(tides):
    # Add intermediate heights between low and high tides.
    added = dict(day=[], time=[], height=[], type=[])
    last = None
    for index, this in tides.iterrows():
        if last is None:
            last = this
        else:
            minutes = int((this['time'] - last['time']).total_seconds() / 60)
            for minute in range(minutes):
                if minute:
                    time = last['time'] + pd.Timedelta(minutes=minute)
                    new = dict(
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
                    )
                    for k, v in new.items():
                        added[k].append(v)
            last = this
    return pd.concat((tides, pd.DataFrame(added))).sort_values('time')


def height_at(t, t1, h1, t2, h2):
    """
    Calculate height at time t based on heights before and after t.
    Reference: www.linz.govt.nz/sites/default/files/cust/
    hydro_almanac_method-to-find-times-or-heights-BETWEEN-high-and-low-waters_202223.pdf
    """
    a = math.pi * ((t - t1) / (t2 - t1) + 1)
    return h1 + (h2 - h1) * ((math.cos(a) + 1) / 2)


def add_safety(tides, sun, margin):
    # Add a column with time of nearest low tide.
    tides['low'] = tides['time']
    high = low = None
    for index, this in tides[tides['type'] != "calc"].iterrows():
        if this['type'] == "high":
            # Remember this high tide time.
            high = this['time']
            if low:
                # Fill rows since last low tide with that time.
                interval = (tides['time'] > low) & (tides['time'] < high)
                tides.loc[interval, 'low'] = low
        elif this['type'] == "low":
            # Remember this low tide time.
            low = this['time']
            if high:
                # Fill rows since last high tide with this time.
                interval = (tides['time'] > high) & (tides['time'] < low)
                tides.loc[interval, 'low'] = low
    # Add dawn and dusk times for each date.
    days = sun.copy()
    days['day'] = days['dawn'].dt.date
    tides['day'] = tides['time'].dt.date
    tides = tides.merge(days, how="left", on='day')
    # Add whether 3 hours either side of low tide.
    low_tide = (tides['type'] != "high") & (abs(tides['low'] - tides['time']) < margin)
    in_daylight = (tides['time'] >= tides['dawn']) & (tides['time'] <= tides['dusk'])
    tides['safe'] = low_tide & in_daylight
    return tides


def add_limits(tides):
    # Add the earliest and latest safe times for each low tide.
    limits = tides[tides['safe']].groupby('low', as_index=False).agg(
        earliest=('time', "min"),
        latest=('time', "max"),
    )
    # Round to nearest 5 minutes (from=up, to=down).
    limits['earliest'] = limits['earliest'].transform(lambda t: t.ceil(freq='5T'))
    limits['latest'] = limits['latest'].transform(lambda t: t.floor(freq='5T'))
    return tides.merge(limits, how="left", on='low')
