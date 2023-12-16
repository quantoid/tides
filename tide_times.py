"""
Processed tide data that include safer driving times.
"""
import streamlit as st
import pandas as pd

import willy_weather


cache_expiry = 24 * 60 * 60


@st.cache_data(ttl=cache_expiry, show_spinner="Holding back the tide...")
def safe_periods(where: int, when: pd.Timestamp, days: int, margin: int) -> dict:
    """
    Get forecast that includes safer driving periods.

    :param where: location ID for Willy Weather
    :param when: first day of forecast
    :param days: number of days in forecast
    :param margin: safer hours either side of low tide
    :returns: data for location, sun, and tides
    """
    forecast = willy_weather.forecast(
        station=where,
        start=when,
        days=days,
    )
    forecast['tides'] = add_driving(forecast, margin)
    return forecast


def add_driving(forecast: dict, margin: int) -> pd.DataFrame:
    """
    Enhance tides for given forecast with additional details we need:

    - Interpolated height every minute over period covered by given tide times.
    - Dawn and dusk times on each date.
    - Whether time is in safe period.
    - Earliest and latest times of each safe period.

    Trims data to between the earliest dusk and latest dawn.
    """
    sun = forecast['sun']
    tides = forecast['tides'].copy()
    # Add column that says which times are safe.
    tides = add_safety(tides, sun, margin)
    tides = add_limits(tides)
    # Include tide times between the earliest dusk and latest dawn.
    return tides[(tides['time'] > sun['dusk'].min()) & (tides['time'] < sun['dawn'].max())]


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
    # Add dawn, noon, and dusk times for each date.
    days = sun.copy()
    days['day'] = days['dawn'].dt.date
    tides['day'] = tides['time'].dt.date
    tides = tides.merge(days, how="left", on='day')
    tides['noon'] = tides['dawn'].dt.floor('D') + pd.Timedelta(12, unit='h')
    # Add whether 3 hours either side of low tide.
    low_tide = (tides['type'] != "high") & (abs(tides['low'] - tides['time']) < pd.Timedelta(hours=margin))
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
